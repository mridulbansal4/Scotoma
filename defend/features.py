"""Point-in-time feature computation. Every aggregate is strictly historical."""

import hmac
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from defend.windows import rolling_by_key, rolling_category_counts, rolling_distinct

VELOCITY_KEYS: tuple[str, ...] = (
    "pan_token",
    "device_id",
    "ip",
    "merchant_id",
    "payee_entity_id",
    "agent_id",
)
VELOCITY_WINDOWS: tuple[str, ...] = ("60s", "10min", "1h", "24h", "7d")
VELOCITY_AGGREGATIONS: tuple[str, ...] = ("cnt", "sum", "declrate", "amtstd")

PERSONAL_DEVIATION_FEATURES: tuple[str, ...] = (
    "amount_z_vs_entity_history",
    "circadian_loglik",
    "mcc_novelty_for_entity",
    "impossible_travel_kmh",
)
STRUCTURAL_FEATURES: tuple[str, ...] = (
    "first_time_payee",
    "payee_age_hours",
    "device_age_hours",
    "cross_border",
    "sca_exempt_flag",
    "bin_seq_entropy",
    "merchant_benford_dev_24h",
    "merchant_control_strength",
    "terminal_age_days",
    "distinct_pan_per_device_10m",
)
GRAPH_FEATURES: tuple[str, ...] = (
    "fanin_payee_24h",
    "fanout_payer_24h",
    "payee_bank_degree",
    "payer_pagerank",
    "payee_pagerank",
    "component_size",
)
AGENTIC_FEATURES: tuple[str, ...] = (
    "mandate_scope_breach",
    "cart_hash_mismatch",
    "attestation_invalid",
    "nonce_reused",
    "settle_vs_intent_amount_delta",
    "human_present_flag_num",
)
RAIL_FEATURES: tuple[str, ...] = (
    "eci_semantic_code",
    "threeds_flow_code",
    "pos_entry_mode_code",
    "payee_name_match_num",
    "upi_txn_type_code",
)


def _velocity_names() -> tuple[str, ...]:
    return tuple(
        f"{agg}_{key}_{window}"
        for key in VELOCITY_KEYS
        for window in VELOCITY_WINDOWS
        for agg in VELOCITY_AGGREGATIONS
    )


VELOCITY_FEATURE_NAMES: tuple[str, ...] = _velocity_names()

FEATURE_NAMES: tuple[str, ...] = (
    VELOCITY_FEATURE_NAMES
    + PERSONAL_DEVIATION_FEATURES
    + STRUCTURAL_FEATURES
    + GRAPH_FEATURES
    + AGENTIC_FEATURES
    + RAIL_FEATURES
)

ECI_SEMANTIC_CODES: dict[str, int] = {
    "authenticated": 2,
    "attempted": 1,
    "not_authenticated": 0,
}
THREEDS_FLOW_CODES: dict[str, int] = {"none": 0, "challenge": 1, "frictionless": 2}
POS_ENTRY_MODE_CODES: dict[str, int] = {"812": 0, "051": 1, "071": 2, "901": 3}
UPI_TXN_TYPE_CODES: dict[str, int] = {"push": 0, "collect": 1}

BENFORD_EXPECTED: np.ndarray = np.log10(1.0 + 1.0 / np.arange(1, 10))
EARTH_RADIUS_KM: float = 6371.0088
PAN_TAIL_DIGITS: int = 10
MIN_STD_FOR_Z: float = 1e-6
DEFAULT_CIRCADIAN_KAPPA: float = 2.0


@dataclass
class FeatureContext:
    """Entity attributes and graph statistics the point-in-time features read."""

    circadian_mu: pd.Series = field(default_factory=lambda: pd.Series(dtype="float64"))
    circadian_kappa: pd.Series = field(default_factory=lambda: pd.Series(dtype="float64"))
    merchant_control_strength: pd.Series = field(default_factory=lambda: pd.Series(dtype="float64"))
    merchant_lat: pd.Series = field(default_factory=lambda: pd.Series(dtype="float64"))
    merchant_lon: pd.Series = field(default_factory=lambda: pd.Series(dtype="float64"))
    entity_first_seen: pd.Series = field(
        default_factory=lambda: pd.Series(dtype="datetime64[ns, UTC]")
    )
    pagerank: pd.Series = field(default_factory=lambda: pd.Series(dtype="float64"))
    component_size: pd.Series = field(default_factory=lambda: pd.Series(dtype="float64"))

    def lookup(self, series: pd.Series, keys: pd.Series, default: float) -> np.ndarray:
        if series.empty:
            return np.full(len(keys), default, dtype="float64")
        mapped = keys.map(series)
        return pd.to_numeric(mapped, errors="coerce").fillna(default).to_numpy("float64")


def velocity_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Every aggregate is computed strictly over events with ts < the current row's ts."""
    working = frame.copy()
    working["is_decline"] = (working["response_code"].fillna("00") != "00").astype("float32")
    columns: dict[str, np.ndarray] = {}
    for key in VELOCITY_KEYS:
        if key not in working.columns:
            for window in VELOCITY_WINDOWS:
                for agg in VELOCITY_AGGREGATIONS:
                    columns[f"{agg}_{key}_{window}"] = np.zeros(len(working), dtype="float32")
            continue
        for window in VELOCITY_WINDOWS:
            columns[f"cnt_{key}_{window}"] = rolling_by_key(
                working, key, window, "amount", "count"
            ).to_numpy()
            columns[f"sum_{key}_{window}"] = rolling_by_key(
                working, key, window, "amount", "sum"
            ).to_numpy()
            columns[f"declrate_{key}_{window}"] = rolling_by_key(
                working, key, window, "is_decline", "mean"
            ).to_numpy()
            columns[f"amtstd_{key}_{window}"] = rolling_by_key(
                working, key, window, "amount", "std"
            ).to_numpy()
    return pd.DataFrame(columns, index=frame.index).astype("float32")


def cart_hash_mismatch(frame: pd.DataFrame) -> pd.Series:
    """AP2 binds the cart hash into the Payment Mandate, so any post-approval mutation
    breaks it. Rows without an agentic cart are 0, not null, because LightGBM treats a
    missing value as informative and the absence of a cart is not evidence of anything."""
    intent = frame.get("cart_hash_at_intent", pd.Series(index=frame.index, dtype="object"))
    settle = frame.get("cart_hash_at_settle", pd.Series(index=frame.index, dtype="object"))
    both_present = intent.notna() & settle.notna()
    mismatch = both_present & (intent != settle)
    return mismatch.astype("int8")


def mandate_scope_breach(frame: pd.DataFrame) -> pd.Series:
    amount = pd.to_numeric(frame["amount"], errors="coerce")
    ceiling = pd.to_numeric(frame.get("mandate_amount_max"), errors="coerce")
    over_amount = (amount > ceiling).fillna(False)
    event_ts = pd.to_datetime(frame["event_ts"], utc=True)
    expiry = pd.to_datetime(frame.get("mandate_expiry_ts"), utc=True, errors="coerce")
    expired = (event_ts > expiry).fillna(False)
    allowlist = frame.get("mandate_merchant_allowlist")
    if allowlist is None:
        off_list = pd.Series(False, index=frame.index)
    else:
        payees = frame["payee_entity_id"]
        off_list = pd.Series(
            [
                bool(items is not None and len(items) > 0 and payee not in items)
                for items, payee in zip(allowlist, payees, strict=True)
            ],
            index=frame.index,
        )
    return (over_amount | expired | off_list).astype("int8")


def compare_cart_hashes(intent: str | None, settle: str | None) -> bool:
    """Constant-time on the hot path so the comparison cannot be probed by timing."""
    if intent is None or settle is None:
        return True
    return hmac.compare_digest(intent, settle)


def _pan_tail_digit(frame: pd.DataFrame) -> np.ndarray:
    # Tokens are hexadecimal and enumerated PANs are decimal, so the raw character is
    # folded rather than parsed; what the entropy measures is spread, not the digit itself.
    tail = frame.get("pan_token", pd.Series(index=frame.index, dtype="object"))
    characters = tail.astype("object").fillna("0").astype(str).str[-1]
    codes = characters.map(lambda c: ord(c) % PAN_TAIL_DIGITS if c else 0)
    return codes.astype("int64").to_numpy()


def _first_digit(values: np.ndarray) -> np.ndarray:
    scaled = np.abs(np.asarray(values, dtype="float64"))
    scaled = np.where(scaled > 0, scaled, np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        exponent = np.floor(np.log10(scaled))
    leading = np.floor(scaled / np.power(10.0, exponent))
    return np.nan_to_num(leading, nan=0.0).astype("int64")


def _windowed_category_share(
    frame: pd.DataFrame, key: str, window: str, codes: np.ndarray, n_categories: int
) -> np.ndarray:
    counts = rolling_category_counts(frame, key, window, codes, n_categories)
    totals = counts.sum(axis=1, keepdims=True)
    with np.errstate(invalid="ignore", divide="ignore"):
        shares = np.where(totals > 0, counts / totals, 0.0)
    return shares


def bin_sequence_entropy(frame: pd.DataFrame) -> np.ndarray:
    """Normalised entropy of trailing PAN digits seen on this device in the prior window.

    Enumeration walks a PAN space, so its trailing digits are close to uniform; a real
    cardholder's device sees one or two cards and almost no digit spread.
    """
    if "device_id" not in frame.columns:
        return np.zeros(len(frame), dtype="float64")
    shares = _windowed_category_share(
        frame, "device_id", "10min", _pan_tail_digit(frame), PAN_TAIL_DIGITS
    )
    with np.errstate(divide="ignore", invalid="ignore"):
        terms = np.where(shares > 0, -shares * np.log(shares), 0.0)
    return terms.sum(axis=1) / np.log(PAN_TAIL_DIGITS)


def merchant_benford_deviation(frame: pd.DataFrame) -> np.ndarray:
    """Mean absolute deviation of the merchant's recent first-digit distribution from Benford."""
    if "merchant_id" not in frame.columns:
        return np.zeros(len(frame), dtype="float64")
    digits = _first_digit(pd.to_numeric(frame["amount"], errors="coerce").to_numpy())
    codes = np.clip(digits - 1, 0, 8)
    shares = _windowed_category_share(frame, "merchant_id", "24h", codes, 9)
    return np.abs(shares - BENFORD_EXPECTED[None, :]).mean(axis=1)


def _haversine_kmh(frame: pd.DataFrame, lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    working = pd.DataFrame(
        {
            "payer_entity_id": frame["payer_entity_id"].to_numpy(),
            "event_ts": pd.to_datetime(frame["event_ts"], utc=True).to_numpy(),
            "lat": lat,
            "lon": lon,
        },
        index=frame.index,
    ).sort_values("event_ts", kind="mergesort")
    grouped = working.groupby("payer_entity_id", sort=False)
    prev_lat = np.radians(grouped["lat"].shift().to_numpy("float64"))
    prev_lon = np.radians(grouped["lon"].shift().to_numpy("float64"))
    hours = grouped["event_ts"].diff().dt.total_seconds().to_numpy("float64") / 3600.0
    cur_lat = np.radians(working["lat"].to_numpy("float64"))
    cur_lon = np.radians(working["lon"].to_numpy("float64"))
    dlat, dlon = cur_lat - prev_lat, cur_lon - prev_lon
    inner = np.sin(dlat / 2) ** 2 + np.cos(prev_lat) * np.cos(cur_lat) * np.sin(dlon / 2) ** 2
    distance = 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(inner, 0.0, 1.0)))
    with np.errstate(divide="ignore", invalid="ignore"):
        speed = np.where(hours > 0, distance / hours, 0.0)
    return pd.Series(np.nan_to_num(speed), index=working.index).reindex(frame.index).to_numpy()


def _von_mises_loglik(hours: np.ndarray, mu: np.ndarray, kappa: np.ndarray) -> np.ndarray:
    """A linear kernel treats 23:00 and 01:00 as far apart; the circular one does not."""
    from scipy.special import i0

    angle = 2.0 * np.pi * hours / 24.0
    return kappa * np.cos(angle - mu) - np.log(2.0 * np.pi * i0(kappa))


def _hours_since(frame: pd.DataFrame, column: str) -> np.ndarray:
    if column not in frame.columns:
        return np.zeros(len(frame), dtype="float64")
    reference = pd.to_datetime(frame[column], utc=True, errors="coerce")
    event_ts = pd.to_datetime(frame["event_ts"], utc=True)
    delta = (event_ts - reference).dt.total_seconds() / 3600.0
    return delta.fillna(0.0).clip(lower=0.0).to_numpy("float64")


def _first_occurrence(frame: pd.DataFrame, left: str, right: str) -> np.ndarray:
    pair = frame[left].astype(str) + "|" + frame[right].astype("object").fillna("").astype(str)
    ordered = pd.DataFrame({"pair": pair, "event_ts": pd.to_datetime(frame["event_ts"], utc=True)})
    ordered = ordered.sort_values("event_ts", kind="mergesort")
    first = ~ordered.duplicated("pair", keep="first")
    return first.reindex(frame.index).astype("int8").to_numpy()


def compute_features(frame: pd.DataFrame, context: FeatureContext | None = None) -> pd.DataFrame:
    """Every feature in FEATURE_NAMES, aligned to the input frame's index."""
    context = context or FeatureContext()
    features = velocity_features(frame)

    amount = pd.to_numeric(frame["amount"], errors="coerce").to_numpy("float64")
    event_ts = pd.to_datetime(frame["event_ts"], utc=True)

    history_mean = rolling_by_key(frame, "payer_entity_id", "7d", "amount", "mean").to_numpy()
    history_std = rolling_by_key(frame, "payer_entity_id", "7d", "amount", "std").to_numpy()
    denominator = np.where(
        np.isfinite(history_std) & (history_std > MIN_STD_FOR_Z), history_std, np.nan
    )
    features["amount_z_vs_entity_history"] = np.nan_to_num((amount - history_mean) / denominator)

    mu = context.lookup(context.circadian_mu, frame["payer_entity_id"], 0.0)
    kappa = context.lookup(
        context.circadian_kappa, frame["payer_entity_id"], DEFAULT_CIRCADIAN_KAPPA
    )
    features["circadian_loglik"] = _von_mises_loglik(
        event_ts.dt.hour.to_numpy("float64") + event_ts.dt.minute.to_numpy("float64") / 60.0,
        mu,
        kappa,
    )

    features["mcc_novelty_for_entity"] = _first_occurrence(frame, "payer_entity_id", "mcc")
    merchant_lat = context.lookup(context.merchant_lat, frame["payee_entity_id"], 0.0)
    merchant_lon = context.lookup(context.merchant_lon, frame["payee_entity_id"], 0.0)
    features["impossible_travel_kmh"] = _haversine_kmh(frame, merchant_lat, merchant_lon)

    features["first_time_payee"] = _first_occurrence(frame, "payer_entity_id", "payee_entity_id")
    payee_age = _entity_age_hours(frame, "payee_entity_id", context, event_ts)
    beneficiary = frame.get("beneficiary_first_seen_ts")
    if beneficiary is not None:
        payee_age = np.where(
            beneficiary.notna().to_numpy(),
            _hours_since(frame, "beneficiary_first_seen_ts"),
            payee_age,
        )
    features["payee_age_hours"] = payee_age
    features["device_age_hours"] = _hours_since(frame, "device_first_seen_ts")
    features["cross_border"] = frame["cross_border"].astype("int8")
    features["sca_exempt_flag"] = (
        frame.get("sca_exempt_reason", pd.Series(index=frame.index, dtype="object"))
        .notna()
        .astype("int8")
    )
    features["bin_seq_entropy"] = bin_sequence_entropy(frame)
    features["merchant_benford_dev_24h"] = merchant_benford_deviation(frame)
    features["merchant_control_strength"] = context.lookup(
        context.merchant_control_strength, frame["payee_entity_id"], 0.5
    )
    features["terminal_age_days"] = (
        _entity_age_hours(frame, "terminal_id", context, event_ts) / 24.0
        if "terminal_id" in frame.columns
        else np.zeros(len(frame))
    )
    features["distinct_pan_per_device_10m"] = (
        rolling_distinct(frame, "device_id", "pan_token", "10min").to_numpy()
        if {"device_id", "pan_token"} <= set(frame.columns)
        else np.zeros(len(frame))
    )

    features["fanin_payee_24h"] = rolling_distinct(
        frame, "payee_entity_id", "payer_entity_id", "24h"
    ).to_numpy()
    features["fanout_payer_24h"] = rolling_distinct(
        frame, "payer_entity_id", "payee_entity_id", "24h"
    ).to_numpy()
    features["payee_bank_degree"] = (
        rolling_distinct(frame, "payee_entity_id", "issuer_id", "7d").to_numpy()
        if "issuer_id" in frame.columns
        else np.zeros(len(frame))
    )
    features["payer_pagerank"] = context.lookup(context.pagerank, frame["payer_entity_id"], 0.0)
    features["payee_pagerank"] = context.lookup(context.pagerank, frame["payee_entity_id"], 0.0)
    features["component_size"] = context.lookup(
        context.component_size, frame["payer_entity_id"], 1.0
    )

    features["mandate_scope_breach"] = mandate_scope_breach(frame)
    features["cart_hash_mismatch"] = cart_hash_mismatch(frame)
    attestation = frame.get("agent_attestation_valid", pd.Series(index=frame.index, dtype="object"))
    features["attestation_invalid"] = attestation.eq(False).fillna(False).astype("int8")
    features["nonce_reused"] = _nonce_reused(frame)
    ceiling = pd.to_numeric(frame.get("mandate_amount_max"), errors="coerce").to_numpy("float64")
    features["settle_vs_intent_amount_delta"] = np.nan_to_num(
        np.where(np.isfinite(ceiling) & (ceiling > 0), (amount - ceiling) / ceiling, 0.0)
    )
    human_present = frame.get("human_present_flag", pd.Series(index=frame.index, dtype="object"))
    features["human_present_flag_num"] = (
        human_present.map({True: 1, False: 0}).fillna(-1).astype("int8")
    )

    features["eci_semantic_code"] = _code_map(frame, "eci_semantic", ECI_SEMANTIC_CODES)
    features["threeds_flow_code"] = _code_map(frame, "threeds_flow", THREEDS_FLOW_CODES)
    features["pos_entry_mode_code"] = _code_map(frame, "pos_entry_mode", POS_ENTRY_MODE_CODES)
    payee_name_match = frame.get("payee_name_match", pd.Series(index=frame.index, dtype="object"))
    features["payee_name_match_num"] = (
        payee_name_match.map({True: 1, False: 0}).fillna(-1).astype("int8")
    )
    features["upi_txn_type_code"] = _code_map(frame, "upi_txn_type", UPI_TXN_TYPE_CODES)

    return features[list(FEATURE_NAMES)].astype("float32").fillna(0.0)


def _entity_age_hours(
    frame: pd.DataFrame, column: str, context: FeatureContext, event_ts: pd.Series
) -> np.ndarray:
    if column not in frame.columns or context.entity_first_seen.empty:
        return np.zeros(len(frame), dtype="float64")
    first_seen = pd.to_datetime(
        frame[column].map(context.entity_first_seen), utc=True, errors="coerce"
    )
    delta = (event_ts - first_seen).dt.total_seconds() / 3600.0
    return delta.fillna(0.0).clip(lower=0.0).to_numpy("float64")


def _nonce_reused(frame: pd.DataFrame) -> pd.Series:
    if "mandate_nonce" not in frame.columns:
        return pd.Series(0, index=frame.index, dtype="int8")
    nonce = frame["mandate_nonce"]
    ordered = pd.DataFrame(
        {"nonce": nonce, "event_ts": pd.to_datetime(frame["event_ts"], utc=True)}
    ).sort_values("event_ts", kind="mergesort")
    repeat = ordered["nonce"].notna() & ordered.duplicated("nonce", keep="first")
    return repeat.reindex(frame.index).fillna(False).astype("int8")


def _code_map(frame: pd.DataFrame, column: str, mapping: dict[str, int]) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(-1, index=frame.index, dtype="int8")
    return frame[column].map(mapping).fillna(-1).astype("int8")
