"""Legitimate traffic. Arrivals come from a non-homogeneous Poisson process realised by
Lewis-Shedler thinning; amounts, merchants and declines come from the holder's profile."""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from generate.declines import sample_decline_codes
from generate.population import (
    CURRENCY_BY_COUNTRY,
    MCC_UNIVERSE,
    RAIL_MIX_BY_COUNTRY,
    Population,
)
from runtime.config import PayLoopConfig
from runtime.seeding import rng_for, seeded_uuid
from runtime.timewindows import TimeWindow
from schema.ces import CES_COLUMNS, FX_RATE_TABLE, RAIL_LIMITS, coerce_dtypes

# Hour-of-day intensity. The 02:00-05:00 trough sits far below the 19:00 peak, which is
# what realism assertion 2 checks.
HOUR_MULTIPLIER: np.ndarray = np.array(
    [
        0.35,
        0.22,
        0.14,
        0.10,
        0.10,
        0.14,
        0.30,
        0.55,
        0.85,
        1.05,
        1.20,
        1.35,
        1.45,
        1.35,
        1.25,
        1.20,
        1.25,
        1.40,
        1.60,
        1.75,
        1.65,
        1.30,
        0.85,
        0.55,
    ]
)
DOW_MULTIPLIER: np.ndarray = np.array([0.95, 0.95, 0.98, 1.02, 1.15, 1.20, 0.95])
MAX_INTENSITY_MULTIPLIER: float = float(HOUR_MULTIPLIER.max() * DOW_MULTIPLIER.max())

APPROVAL_RATE_BY_RAIL: dict[str, float] = {
    "CARD_CP": 0.95,
    "CARD_CNP": 0.85,
    "UPI": 0.94,
    "SEPA_INST": 0.98,
    "ACH": 0.98,
    "AGENTIC": 0.95,
}
RECURRING_APPROVAL_RATE: float = 0.85
THREEDS_FRICTIONLESS_RATE: float = 0.82
THREEDS_CHALLENGE_RATE: float = 0.15
SCA_EXEMPT_RATE: float = 0.22
CROSS_BORDER_RATE: float = 0.09
UPI_MERCHANT_SHARE: float = 0.60
UPI_COLLECT_SHARE: float = 0.12
PROXY_IP_ROTATION_RATE: float = 0.05
SECONDARY_DEVICE_RATE: float = 0.11
MIN_AMOUNT: float = 0.50
EMISSION_CHUNK_ROWS: int = 400_000
# A cardholder transacts in sessions: a basket split, a retry, a second item minutes later.
# Sessions are what give within-entity inter-event times their positive lag-1
# autocorrelation, which is the structure a row-independent generator cannot reproduce.
SESSION_RATE: float = 0.38
SESSION_EXTRA_MEAN: float = 3.2
SESSION_GAP_SECONDS: float = 220.0
SESSION_MAX_EXTRA: int = 9
# Spend intensity drifts from week to week: a busy stretch, then a quiet one. That slow
# persistence is what makes consecutive within-entity gaps similar in scale, and so is
# what puts the lag-1 inter-event-time autocorrelation above zero.
ACTIVITY_BLOCK_DAYS: float = 3.0
ACTIVITY_PERSISTENCE: float = 0.94
ACTIVITY_SIGMA: float = 0.9

SCA_EXEMPT_REASONS: tuple[str, ...] = (
    "low_value",
    "tra",
    "trusted_beneficiary",
    "recurring",
    "corporate",
)
CARD_CP_ENTRY_MODES: tuple[str, ...] = ("051", "071")
BROWSER_RESOLUTIONS: tuple[str, ...] = (
    "1170x2532",
    "1920x1080",
    "1440x900",
    "2340x1080",
    "1366x768",
)
BROWSER_LANGS: tuple[str, ...] = ("en-IN", "en-US", "en-GB", "de-DE", "fr-FR")
AGENT_PROTOCOL_COLUMN: str = "protocol"


def intensity_multiplier(hour: int, weekday: int) -> float:
    return float(HOUR_MULTIPLIER[hour] * DOW_MULTIPLIER[weekday])


def activity_factors(
    n_holders: int, n_blocks: int, rng: np.random.Generator
) -> np.ndarray:
    """Per-holder weekly activity multipliers from a persistent AR(1) in log space."""
    innovation = ACTIVITY_SIGMA * np.sqrt(1.0 - ACTIVITY_PERSISTENCE**2)
    levels = np.empty((n_holders, n_blocks), dtype="float64")
    levels[:, 0] = rng.normal(0.0, ACTIVITY_SIGMA, size=n_holders)
    for block in range(1, n_blocks):
        levels[:, block] = ACTIVITY_PERSISTENCE * levels[:, block - 1] + rng.normal(
            0.0, innovation, size=n_holders
        )
    factors = np.exp(levels)
    return factors / factors.max(axis=1, keepdims=True)


def _thinned_arrivals(
    rates_per_hour: np.ndarray,
    window: TimeWindow,
    rng: np.random.Generator,
    activity: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Batched Lewis-Shedler thinning: homogeneous candidates at lam_max, accepted with
    probability lambda(t)/lam_max. Identical acceptance rule to population.next_arrival."""
    span_hours = window.duration_seconds() / 3600.0
    expected = rates_per_hour * MAX_INTENSITY_MULTIPLIER * span_hours
    counts = rng.poisson(expected)
    total = int(counts.sum())
    if total == 0:
        return np.empty(0, dtype="int64"), np.empty(0, dtype="float64")
    holder_index = np.repeat(np.arange(rates_per_hour.size), counts)
    offsets = rng.random(total) * span_hours

    start = pd.Timestamp(window.start)
    absolute = start + pd.to_timedelta(offsets, unit="h")
    multiplier = (
        HOUR_MULTIPLIER[absolute.hour.to_numpy()] * DOW_MULTIPLIER[absolute.dayofweek.to_numpy()]
    )
    block = np.minimum(
        (offsets / (24.0 * ACTIVITY_BLOCK_DAYS)).astype("int64"), activity.shape[1] - 1
    )
    intensity = (multiplier / MAX_INTENSITY_MULTIPLIER) * activity[holder_index, block]
    accepted = rng.random(total) < intensity
    return holder_index[accepted], offsets[accepted]


def _expand_sessions(
    holder_index: np.ndarray,
    offsets: np.ndarray,
    window: TimeWindow,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """Turn a share of arrivals into short sessions of follow-on events by the same holder."""
    seeds = rng.random(holder_index.size) < SESSION_RATE
    extra_counts = np.where(
        seeds,
        np.minimum(1 + rng.poisson(SESSION_EXTRA_MEAN, holder_index.size), SESSION_MAX_EXTRA),
        0,
    )
    total_extra = int(extra_counts.sum())
    if total_extra == 0:
        return holder_index, offsets

    parents = np.repeat(np.arange(holder_index.size), extra_counts)
    gaps = rng.exponential(SESSION_GAP_SECONDS, size=total_extra) / 3600.0
    running = np.cumsum(gaps)
    session_sizes = extra_counts[extra_counts > 0]
    session_starts = np.concatenate([[0], np.cumsum(session_sizes)[:-1]])
    baseline = np.repeat(running[session_starts] - gaps[session_starts], session_sizes)
    session_offsets = offsets[parents] + (running - baseline)

    keep = session_offsets < window.duration_seconds() / 3600.0
    return (
        np.concatenate([holder_index, holder_index[parents][keep]]),
        np.concatenate([offsets, session_offsets[keep]]),
    )


def _calibrated_rates(
    population: Population,
    window: TimeWindow,
    target_events: int,
    holder_mask: np.ndarray | None = None,
    activity_mean: float = 1.0,
) -> np.ndarray:
    """Relative arrival rates are a population property; the absolute scale is set so the
    selected holders emit the requested event budget."""
    relative = population.cardholders["lambda_base"].to_numpy("float64")
    if holder_mask is not None:
        relative = np.where(holder_mask, relative, 0.0)
    span_hours = window.duration_seconds() / 3600.0
    mean_multiplier = float(HOUR_MULTIPLIER.mean() * DOW_MULTIPLIER.mean())
    expected = relative.sum() * span_hours * mean_multiplier * activity_mean
    if expected <= 0:
        raise ValueError("selected arrival rates sum to zero")
    return relative * (target_events / expected)


def _choose_rails(
    population: Population, holder_index: np.ndarray, rng: np.random.Generator
) -> np.ndarray:
    countries = population.cardholders["home_country"].to_numpy()[holder_index]
    rails = np.empty(holder_index.size, dtype=object)
    for country, mix in RAIL_MIX_BY_COUNTRY.items():
        selector = countries == country
        if not selector.any():
            continue
        rails[selector] = rng.choice(
            list(mix.keys()), size=int(selector.sum()), p=list(mix.values())
        )
    return rails


def emit_legitimate(
    population: Population,
    window: TimeWindow,
    target_events: int | None = None,
    holder_mask: np.ndarray | None = None,
    purpose: str = "behavior:arrivals",
) -> pd.DataFrame:
    """Legitimate CES events for the holders selected by holder_mask over the window."""
    config = population.config
    rng = rng_for(purpose)
    n_blocks = max(int(window.duration_seconds() / (86400.0 * ACTIVITY_BLOCK_DAYS)) + 1, 1)
    activity = activity_factors(
        len(population.cardholders), n_blocks, rng_for(f"{purpose}:activity")
    )
    budget = target_events or config.target_events
    expansion = 1.0 + SESSION_RATE * min(1.0 + SESSION_EXTRA_MEAN, float(SESSION_MAX_EXTRA))
    rates = _calibrated_rates(
        population, window, int(budget / expansion), holder_mask, float(activity.mean())
    )

    holder_index, offsets = _thinned_arrivals(rates, window, rng, activity)
    if holder_index.size == 0:
        return pd.DataFrame(columns=list(CES_COLUMNS))
    holder_index, offsets = _expand_sessions(holder_index, offsets, window, rng)

    order = np.argsort(offsets, kind="stable")
    holder_index, offsets = holder_index[order], offsets[order]
    timestamps = pd.Timestamp(window.start) + pd.to_timedelta(offsets, unit="h")

    frames = [
        _build_block(
            population,
            holder_index[start : start + EMISSION_CHUNK_ROWS],
            timestamps[start : start + EMISSION_CHUNK_ROWS],
            rng,
            purpose,
            start,
        )
        for start in range(0, holder_index.size, EMISSION_CHUNK_ROWS)
    ]
    return pd.concat(frames, ignore_index=True)


def _build_block(
    population: Population,
    holder_index: np.ndarray,
    timestamps: pd.DatetimeIndex,
    rng: np.random.Generator,
    purpose: str,
    offset: int,
) -> pd.DataFrame:
    size = holder_index.size
    holders = population.cardholders
    merchants = population.merchants

    rails = _choose_rails(population, holder_index, rng)
    affinity = population.affinity_merchants[holder_index]
    merchant_index = affinity[np.arange(size), rng.integers(0, affinity.shape[1], size=size)]
    merchant_mcc = merchants["mcc"].to_numpy()[merchant_index]
    mcc_lookup = {mcc: position for position, mcc in enumerate(MCC_UNIVERSE)}
    mcc_position = np.array([mcc_lookup[m] for m in merchant_mcc], dtype="int64")

    mu = population.amount_mu[holder_index, mcc_position].astype("float64")
    sigma = population.amount_sigma[holder_index, mcc_position].astype("float64")
    amount = np.exp(rng.normal(mu, sigma))

    countries = holders["home_country"].to_numpy()[holder_index]
    currency = np.array([CURRENCY_BY_COUNTRY[c] for c in countries])
    rail_limit = np.array([RAIL_LIMITS[r] for r in rails])
    amount = np.clip(np.round(amount, 2), MIN_AMOUNT, rail_limit)
    fx = np.array([FX_RATE_TABLE[c] for c in currency])
    amount_inr = np.round(amount * fx, 2)

    is_card = np.isin(rails, ["CARD_CNP", "CARD_CP"])
    is_cnp = rails == "CARD_CNP"
    is_cp = rails == "CARD_CP"
    is_upi = rails == "UPI"
    is_rtp = np.isin(rails, ["SEPA_INST", "ACH"])
    is_agentic = rails == "AGENTIC"

    account_ids = population.accounts["entity_id"].to_numpy()
    account_pick = rng.integers(0, account_ids.size, size=size)
    merchant_ids = merchants["entity_id"].to_numpy()[merchant_index]
    upi_to_merchant = rng.random(size) < UPI_MERCHANT_SHARE
    payee_is_merchant = is_card | is_agentic | (is_upi & upi_to_merchant)
    payee = np.where(payee_is_merchant, merchant_ids, account_ids[account_pick])

    merchant_country = merchants["home_country"].to_numpy()[merchant_index]
    cross_border_draw = rng.random(size) < CROSS_BORDER_RATE
    payee_country = np.where(cross_border_draw, merchant_country, countries)
    cross_border = payee_country != countries

    approval_base = np.array([APPROVAL_RATE_BY_RAIL[r] for r in rails])
    control = merchants["control_strength"].to_numpy()[merchant_index]
    approval_probability = np.clip(approval_base + 0.03 * (control - 0.5), 0.60, 0.995)
    approved = rng.random(size) < approval_probability
    decline_codes = sample_decline_codes(population.config.decline_mix_region, size, rng)
    response_code = np.where(approved, "00", decline_codes)

    event_ids = [str(seeded_uuid(f"{purpose}:event", offset + i)) for i in range(size)]
    label_available = timestamps + pd.Timedelta(days=population.config.label_embargo_days)

    frame = pd.DataFrame(
        {
            "event_id": event_ids,
            "event_ts": timestamps,
            "rail": rails,
            "amount": amount,
            "currency": currency,
            "amount_inr": amount_inr,
            "payer_entity_id": holders["entity_id"].to_numpy()[holder_index],
            "payee_entity_id": payee,
            "payer_country": countries,
            "payee_country": payee_country,
            "cross_border": cross_border,
            "payer_name_hash": holders["payer_name_hash"].to_numpy()[holder_index],
            "payer_kyc_level": holders["kyc_level"].to_numpy()[holder_index],
            "payer_balance_band": holders["balance_band"].to_numpy()[holder_index],
            "is_fraud": False,
            "vector_id": None,
            "campaign_id": None,
            "red_team_round": None,
            "label_available_ts": label_available,
        }
    )
    frame["mutation_lineage"] = [[] for _ in range(size)]

    _attach_card_block(
        frame, population, holder_index, merchant_index, is_card, is_cp, response_code, rng
    )
    _attach_threeds_block(frame, population, holder_index, is_cnp, rng)
    _attach_device_block(frame, population, holder_index, rng)
    _attach_upi_block(frame, population, holder_index, is_upi, timestamps, rng)
    _attach_rtp_block(frame, population, is_rtp, timestamps, account_pick, rng)
    _attach_agent_block(
        frame, population, holder_index, is_agentic, merchant_ids, timestamps, amount, rng
    )

    frame["response_code"] = response_code
    for column in CES_COLUMNS:
        if column not in frame.columns:
            frame[column] = None
    return coerce_dtypes(frame[list(CES_COLUMNS)])


def _attach_card_block(
    frame: pd.DataFrame,
    population: Population,
    holder_index: np.ndarray,
    merchant_index: np.ndarray,
    is_card: np.ndarray,
    is_cp: np.ndarray,
    response_code: np.ndarray,
    rng: np.random.Generator,
) -> None:
    size = holder_index.size
    holders = population.cardholders
    merchants = population.merchants
    entry_mode = np.where(is_cp, rng.choice(CARD_CP_ENTRY_MODES, size=size), "812")
    frame["pan_token"] = np.where(is_card, holders["pan_token"].to_numpy()[holder_index], None)
    frame["bin"] = np.where(is_card, holders["bin"].to_numpy()[holder_index], None)
    frame["issuer_id"] = np.where(is_card, holders["issuer_id"].to_numpy()[holder_index], None)
    frame["acquirer_id"] = np.where(
        is_card, merchants["acquirer_id"].to_numpy()[merchant_index], None
    )
    frame["merchant_id"] = np.where(
        is_card, merchants["entity_id"].to_numpy()[merchant_index], None
    )
    frame["mcc"] = np.where(is_card, merchants["mcc"].to_numpy()[merchant_index], None)
    frame["pos_entry_mode"] = np.where(is_card, entry_mode, None)
    frame["processing_code"] = np.where(is_card, "000000", None)
    frame["mti"] = np.where(is_card, "0100", None)
    frame["response_code"] = np.where(is_card, response_code, None)
    frame["avs_result"] = np.where(
        is_card,
        rng.choice(["Y", "A", "Z", "N", "U"], size=size, p=[0.72, 0.08, 0.06, 0.08, 0.06]),
        None,
    )
    frame["cvv_result"] = np.where(
        is_card, rng.choice(["M", "N", "P", "U"], size=size, p=[0.88, 0.05, 0.04, 0.03]), None
    )
    frame["terminal_id"] = np.where(
        is_card, merchants["terminal_id"].to_numpy()[merchant_index], None
    )
    frame["merchant_country"] = np.where(
        is_card, merchants["home_country"].to_numpy()[merchant_index], None
    )


def _attach_threeds_block(
    frame: pd.DataFrame,
    population: Population,
    holder_index: np.ndarray,
    is_cnp: np.ndarray,
    rng: np.random.Generator,
) -> None:
    from schema.ces import ECI_SEMANTICS

    size = holder_index.size
    holders = population.cardholders
    network = holders["card_network"].to_numpy()[holder_index]
    flow = rng.choice(
        ["frictionless", "challenge", "none"],
        size=size,
        p=[
            THREEDS_FRICTIONLESS_RATE,
            THREEDS_CHALLENGE_RATE,
            1.0 - THREEDS_FRICTIONLESS_RATE - THREEDS_CHALLENGE_RATE,
        ],
    )
    semantic = np.where(
        flow == "none",
        "not_authenticated",
        np.where(flow == "challenge", "authenticated", "attempted"),
    )
    semantic = np.where(
        (flow == "frictionless") & (rng.random(size) < 0.72), "authenticated", semantic
    )
    # ECI is network-specific, so the code is looked up from the semantic and the scheme.
    reverse = {
        net: {meaning: code for code, meaning in table.items()}
        for net, table in ECI_SEMANTICS.items()
    }
    eci = np.array([reverse[net][meaning] for net, meaning in zip(network, semantic, strict=True)])

    frame["threeds_version"] = np.where(is_cnp, "2.2.0", None)
    frame["threeds_flow"] = np.where(is_cnp, flow, None)
    frame["card_network"] = np.where(is_cnp, network, None)
    frame["eci"] = np.where(is_cnp, eci, None)
    frame["eci_semantic"] = np.where(is_cnp, semantic, None)
    frame["cavv_present"] = np.where(is_cnp, semantic != "not_authenticated", None)
    frame["threeds_method_completed"] = np.where(is_cnp, rng.random(size) < 0.78, None)
    frame["device_fingerprint_id"] = np.where(
        is_cnp, holders["device_fingerprint_id"].to_numpy()[holder_index], None
    )
    frame["browser_screen_res"] = np.where(is_cnp, rng.choice(BROWSER_RESOLUTIONS, size=size), None)
    frame["browser_tz_offset"] = np.where(
        is_cnp, rng.choice([330, 0, 60, -300, 480], size=size), None
    )
    frame["browser_lang"] = np.where(is_cnp, rng.choice(BROWSER_LANGS, size=size), None)
    exempt = rng.random(size) < SCA_EXEMPT_RATE
    frame["sca_exempt_reason"] = np.where(
        is_cnp & exempt, rng.choice(SCA_EXEMPT_REASONS, size=size), None
    )


def _attach_device_block(
    frame: pd.DataFrame, population: Population, holder_index: np.ndarray, rng: np.random.Generator
) -> None:
    size = holder_index.size
    holders = population.cardholders
    devices = population.devices
    ips = population.ips
    use_secondary = rng.random(size) < SECONDARY_DEVICE_RATE
    device_id = np.where(
        use_secondary,
        holders["secondary_device_id"].to_numpy()[holder_index],
        holders["primary_device_id"].to_numpy()[holder_index],
    )
    device_lookup = pd.Series(
        devices["device_os"].to_numpy(), index=devices["entity_id"].to_numpy()
    )
    created_lookup = pd.Series(
        devices["created_ts"].to_numpy(), index=devices["entity_id"].to_numpy()
    )

    rotate = rng.random(size) < PROXY_IP_ROTATION_RATE
    ip_index = np.where(
        rotate,
        rng.integers(0, len(ips), size=size),
        holders["home_ip_index"].to_numpy()[holder_index],
    )
    frame["device_id"] = device_id
    frame["device_os"] = device_lookup.reindex(device_id).to_numpy()
    frame["device_first_seen_ts"] = pd.to_datetime(
        created_lookup.reindex(device_id).to_numpy(), utc=True
    )
    frame["ip"] = ips["entity_id"].to_numpy()[ip_index]
    frame["ip_asn"] = ips["ip_asn"].to_numpy()[ip_index]
    frame["ip_country"] = ips["ip_country"].to_numpy()[ip_index]
    frame["ip_proxy_flag"] = ips["proxy_flag"].to_numpy()[ip_index]
    frame["user_agent_hash"] = holders["user_agent_hash"].to_numpy()[holder_index]


def _attach_upi_block(
    frame: pd.DataFrame,
    population: Population,
    holder_index: np.ndarray,
    is_upi: np.ndarray,
    timestamps: pd.DatetimeIndex,
    rng: np.random.Generator,
) -> None:
    size = holder_index.size
    holders = population.cardholders
    payee_vpa = np.array(
        [f"{str(p).lower().replace('_', '')}@payloop" for p in frame["payee_entity_id"]]
    )
    frame["vpa_payer"] = np.where(is_upi, holders["vpa"].to_numpy()[holder_index], None)
    frame["vpa_payee"] = np.where(is_upi, payee_vpa, None)
    frame["upi_txn_type"] = np.where(
        is_upi, np.where(rng.random(size) < UPI_COLLECT_SHARE, "collect", "push"), None
    )
    frame["payee_name_match"] = np.where(is_upi, rng.random(size) < 0.97, None)
    frame["device_binding_id"] = np.where(
        is_upi, holders["device_binding_id"].to_numpy()[holder_index], None
    )
    age_days = rng.integers(1, 720, size=size)
    beneficiary = pd.Series(timestamps - pd.to_timedelta(age_days, unit="D"), index=frame.index)
    frame["beneficiary_first_seen_ts"] = beneficiary.where(pd.Series(is_upi, index=frame.index))


def _attach_rtp_block(
    frame: pd.DataFrame,
    population: Population,
    is_rtp: np.ndarray,
    timestamps: pd.DatetimeIndex,
    account_pick: np.ndarray,
    rng: np.random.Generator,
) -> None:
    size = is_rtp.size
    accounts = population.accounts
    frame["uetr"] = np.where(
        is_rtp, [str(seeded_uuid("behavior:uetr", i)) for i in range(size)], None
    )
    frame["debtor_agent_bic"] = np.where(
        is_rtp, accounts["bank_bic"].to_numpy()[account_pick], None
    )
    frame["creditor_agent_bic"] = np.where(
        is_rtp, accounts["bank_bic"].to_numpy()[(account_pick + 1) % len(accounts)], None
    )
    settlement = pd.Series(timestamps + pd.Timedelta(seconds=10), index=frame.index)
    frame["settlement_ts"] = settlement.where(pd.Series(is_rtp, index=frame.index))
    frame["remittance_ref"] = np.where(is_rtp, "PAYLOOP-SIM", None)


def _attach_agent_block(
    frame: pd.DataFrame,
    population: Population,
    holder_index: np.ndarray,
    is_agentic: np.ndarray,
    merchant_ids: np.ndarray,
    timestamps: pd.DatetimeIndex,
    amount: np.ndarray,
    rng: np.random.Generator,
) -> None:
    from generate.injectors.base import cart_hash

    size = holder_index.size
    agents = population.agents
    pick = rng.integers(0, len(agents), size=size)
    hashes = np.array(
        [
            cart_hash([{"sku": f"SKU-{int(i) % 9999:04d}", "qty": 1, "unit_price": float(a)}])
            for i, a in zip(np.arange(size), amount, strict=True)
        ]
    )
    nonce_tail = rng.integers(0, 16, size=(size, 10))
    digits = np.array(list("0123456789abcdef"))
    nonces = np.array(["n_" + "".join(row) for row in digits[nonce_tail]])

    frame["agent_id"] = np.where(is_agentic, agents["entity_id"].to_numpy()[pick], None)
    frame["agent_operator"] = np.where(is_agentic, agents["agent_operator"].to_numpy()[pick], None)
    frame["protocol"] = np.where(is_agentic, agents[AGENT_PROTOCOL_COLUMN].to_numpy()[pick], None)
    frame["agent_attestation_valid"] = np.where(is_agentic, True, None)
    frame["intent_mandate_id"] = np.where(
        is_agentic, [str(seeded_uuid("behavior:intent", i)) for i in range(size)], None
    )
    frame["cart_mandate_id"] = np.where(
        is_agentic, [str(seeded_uuid("behavior:cart", i)) for i in range(size)], None
    )
    frame["payment_mandate_id"] = np.where(
        is_agentic, [str(seeded_uuid("behavior:payment", i)) for i in range(size)], None
    )
    frame["human_present_flag"] = np.where(is_agentic, rng.random(size) < 0.35, None)
    frame["mandate_amount_max"] = np.where(
        is_agentic, np.round(amount * rng.uniform(1.05, 2.5, size=size), 2), None
    )
    expiry = pd.Series(timestamps + pd.Timedelta(days=1), index=frame.index)
    frame["mandate_expiry_ts"] = expiry.where(pd.Series(is_agentic, index=frame.index))
    frame["mandate_signature_valid"] = np.where(is_agentic, True, None)
    frame["mandate_nonce"] = np.where(is_agentic, nonces, None)
    frame["cart_hash_at_intent"] = np.where(is_agentic, hashes, None)
    frame["cart_hash_at_settle"] = np.where(is_agentic, hashes, None)
    frame["payee_at_intent"] = np.where(is_agentic, merchant_ids, None)
    frame["payee_at_settle"] = np.where(is_agentic, merchant_ids, None)
    allowlist = [
        [str(m)] if flag else None for m, flag in zip(merchant_ids, is_agentic, strict=True)
    ]
    frame["mandate_merchant_allowlist"] = allowlist


def simulation_window(config: PayLoopConfig, sim_start: datetime) -> TimeWindow:
    return TimeWindow(start=sim_start, end=sim_start + timedelta(days=config.sim_days))
