"""Entity factory. Entities are persistent objects with profiles; rows are emitted by
processes against them and never sampled independently."""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd

from backend.runtime.config import PayLoopConfig, load_config
from backend.runtime.seeding import rng_for

N_CARDHOLDERS: int = 50_000
N_MERCHANTS: int = 4_000
N_DEVICES: int = 65_000
N_IPS: int = 12_000
N_ACCOUNTS: int = 50_000
N_AGENTS: int = 800

DIRICHLET_ALPHA: float = 0.40
BLIND_COHORT_DIRICHLET_ALPHA: float = 0.25
BLIND_COHORT_MU_OFFSET: float = 0.35
ZIPF_S: float = 1.10
LOGNORMAL_MU_DEFAULT: float = 3.50
LOGNORMAL_SIGMA_DEFAULT: float = 1.10
DEVICE_SHARING_RATE: float = 0.08
IP_PROXY_RATE: float = 0.04
# Attackers reach for anonymising infrastructure far more often than ordinary users do.
# That is a behavioural signal the detector may legitimately learn.
ATTACKER_PROXY_RATE: float = 0.55
MERCHANT_CONTROL_BETA: tuple[float, float] = (2.0, 2.0)

N_ISSUERS: int = 40
N_ACQUIRERS: int = 30
PRIMARY_ISSUER_ID: str = "ISS_007"
PRIMARY_ACQUIRER_ID: str = "ACQ_014"
ISSUER_CONCENTRATION: float = 0.18
ACQUIRER_CONCENTRATION: float = 0.16
AFFINITY_MERCHANTS_PER_HOLDER: int = 12
PREFERENTIAL_ATTACHMENT_EXPONENT: float = 0.85
LAMBDA_BASE_MU: float = -1.35
LAMBDA_BASE_SIGMA: float = 0.55
CIRCADIAN_KAPPA_RANGE: tuple[float, float] = (1.2, 4.0)
SIM_START: datetime = datetime(2026, 1, 1, tzinfo=UTC)
ENTITY_HISTORY_DAYS: int = 900

MCC_UNIVERSE: tuple[str, ...] = (
    "5411",
    "5812",
    "5814",
    "5541",
    "5912",
    "5999",
    "4121",
    "4899",
    "5732",
    "5691",
    "7011",
    "4511",
    "5967",
    "7995",
    "6011",
    "5661",
    "8099",
    "5945",
    "5310",
    "7372",
)

# Countries the population is drawn from, with the share of cardholders in each.
COUNTRY_SHARES: dict[str, float] = {
    "IN": 0.62,
    "US": 0.14,
    "GB": 0.07,
    "DE": 0.05,
    "FR": 0.04,
    "SG": 0.04,
    "AE": 0.04,
}
COUNTRY_CENTROIDS: dict[str, tuple[float, float]] = {
    "IN": (20.59, 78.96),
    "US": (39.83, -98.58),
    "GB": (54.00, -2.00),
    "DE": (51.17, 10.45),
    "FR": (46.60, 2.35),
    "SG": (1.35, 103.82),
    "AE": (24.00, 54.00),
    "NL": (52.13, 5.29),
}
COUNTRY_JITTER_DEGREES: float = 4.0

RAIL_MIX_BY_COUNTRY: dict[str, dict[str, float]] = {
    "IN": {"CARD_CNP": 0.28, "CARD_CP": 0.20, "UPI": 0.40, "ACH": 0.08, "AGENTIC": 0.04},
    "US": {"CARD_CNP": 0.38, "CARD_CP": 0.28, "ACH": 0.28, "AGENTIC": 0.06},
    "GB": {"CARD_CNP": 0.38, "CARD_CP": 0.26, "SEPA_INST": 0.30, "AGENTIC": 0.06},
    "DE": {"CARD_CNP": 0.32, "CARD_CP": 0.24, "SEPA_INST": 0.38, "AGENTIC": 0.06},
    "FR": {"CARD_CNP": 0.32, "CARD_CP": 0.24, "SEPA_INST": 0.38, "AGENTIC": 0.06},
    "SG": {"CARD_CNP": 0.38, "CARD_CP": 0.26, "ACH": 0.30, "AGENTIC": 0.06},
    "AE": {"CARD_CNP": 0.38, "CARD_CP": 0.26, "ACH": 0.30, "AGENTIC": 0.06},
}
CURRENCY_BY_COUNTRY: dict[str, str] = {
    "IN": "INR",
    "US": "USD",
    "GB": "GBP",
    "DE": "EUR",
    "FR": "EUR",
    "SG": "SGD",
    "AE": "AED",
}

# Designated test BIN ranges. Real PANs never appear, which keeps the simulator out of
# PCI scope; see generate/injectors/base.py for the assertion that enforces it.
CARD_BIN_PREFIXES: tuple[str, ...] = ("41111100", "41111101", "52223000", "52223001")

DOCUMENTATION_IP_BLOCKS: tuple[str, ...] = ("192.0.2", "198.51.100", "203.0.113")

# Written into the entities table's JSON attributes column, which is where anything not
# promoted to its own column belongs.
ATTRIBUTE_COLUMNS: tuple[str, ...] = (
    "mcc",
    "control_strength",
    "acquirer_id",
    "issuer_id",
    "card_network",
    "kyc_level",
    "balance_band",
    "device_os",
    "ip_asn",
    "proxy_flag",
    "bank_bic",
    "agent_operator",
    "protocol",
)


@dataclass
class Cardholder:
    entity_id: str
    home_country: str
    mcc_preferences: np.ndarray
    amount_mu: dict[str, float]
    amount_sigma: dict[str, float]
    lambda_base: float
    device_ids: list[str]
    rail_mix: dict[str, float]
    in_blind_cohort: bool


@dataclass
class Population:
    """Column-oriented entity store. Injectors and the behaviour engine read from here."""

    config: PayLoopConfig
    sim_start: datetime
    cardholders: pd.DataFrame
    merchants: pd.DataFrame
    devices: pd.DataFrame
    ips: pd.DataFrame
    accounts: pd.DataFrame
    agents: pd.DataFrame
    mcc_preferences: np.ndarray
    amount_mu: np.ndarray
    amount_sigma: np.ndarray
    affinity_merchants: np.ndarray
    merchant_popularity: np.ndarray
    attacker_device_counter: int = field(default=0)

    @property
    def n_cardholders(self) -> int:
        return len(self.cardholders)

    def cardholder(self, index: int) -> Cardholder:
        row = self.cardholders.iloc[index]
        return Cardholder(
            entity_id=str(row["entity_id"]),
            home_country=str(row["home_country"]),
            mcc_preferences=self.mcc_preferences[index],
            amount_mu=dict(zip(MCC_UNIVERSE, self.amount_mu[index], strict=True)),
            amount_sigma=dict(zip(MCC_UNIVERSE, self.amount_sigma[index], strict=True)),
            lambda_base=float(row["lambda_base"]),
            device_ids=[str(row["primary_device_id"])],
            rail_mix=RAIL_MIX_BY_COUNTRY[str(row["home_country"])],
            in_blind_cohort=bool(row["in_blind_cohort"]),
        )

    @property
    def pool_cardholders(self) -> pd.DataFrame:
        """Non-cohort holders. Every injector whose output joins the training pool draws
        from here, so the blind cohort never leaks in through an entity reference."""
        return self.cardholders[~self.cardholders["in_blind_cohort"].to_numpy(dtype=bool)]

    def account_count(self) -> int:
        return len(self.accounts)

    def device_position(self, device_id: str) -> int | None:
        """Position of a device in the device frame, cached so per-row lookups stay O(1)."""
        if getattr(self, "_device_positions", None) is None:
            self._device_positions = {
                str(value): position
                for position, value in enumerate(self.devices["entity_id"].to_numpy())
            }
        return self._device_positions.get(str(device_id))

    def new_attacker_device(self, rng: np.random.Generator) -> dict[str, str]:
        """A device the attacker controls, drawn from the ordinary population.

        Attacker hardware must be indistinguishable from everyone else's by identity alone.
        Minting devices in their own namespace, on one operating system, behind one country,
        hands the detector a label: it learns "this device shape is fraud" from the vectors
        it trains on and then recognises the held-out family for free, which makes the
        holdout measure nothing. What is left is behaviour, which is what the features are
        supposed to read. Proxy use stays elevated because that is a real signal rather than
        an identity giveaway."""
        self.attacker_device_counter += 1
        device = self.devices.iloc[int(rng.integers(0, len(self.devices)))]
        address = self.ips.iloc[int(rng.integers(0, len(self.ips)))]
        return {
            "device_id": str(device["entity_id"]),
            "device_os": str(device["device_os"]),
            "ip": str(address["entity_id"]),
            "ip_asn": str(address["ip_asn"]),
            "ip_country": str(address["ip_country"]),
            "ip_proxy_flag": bool(rng.random() < ATTACKER_PROXY_RATE),
        }

    def sample_weak_bin(self, rng: np.random.Generator) -> str:
        return str(rng.choice(CARD_BIN_PREFIXES))

    def sample_merchants(
        self, count: int, weight_by: str, rng: np.random.Generator
    ) -> pd.DataFrame:
        if weight_by == "inverse_control_strength":
            weights = 1.0 - self.merchants["control_strength"].to_numpy("float64")
        elif weight_by == "popularity":
            weights = self.merchant_popularity
        else:
            weights = np.ones(len(self.merchants))
        weights = np.clip(weights, 1e-9, None)
        weights = weights / weights.sum()
        size = min(count, len(self.merchants))
        chosen = rng.choice(len(self.merchants), size=size, replace=False, p=weights)
        return self.merchants.iloc[chosen].reset_index(drop=True)

    def sample_cardholders(
        self, count: int, rng: np.random.Generator, blind: bool = False
    ) -> pd.DataFrame:
        pool = self.cardholders[self.cardholders["in_blind_cohort"] == blind]
        size = min(count, len(pool))
        chosen = rng.choice(len(pool), size=size, replace=False)
        return pool.iloc[chosen].reset_index(drop=True)

    def sample_accounts(self, count: int, rng: np.random.Generator) -> pd.DataFrame:
        size = min(count, len(self.accounts))
        chosen = rng.choice(len(self.accounts), size=size, replace=False)
        return self.accounts.iloc[chosen].reset_index(drop=True)

    def sample_agents(self, count: int, rng: np.random.Generator) -> pd.DataFrame:
        size = min(count, len(self.agents))
        chosen = rng.choice(len(self.agents), size=size, replace=False)
        return self.agents.iloc[chosen].reset_index(drop=True)


def _country_draw(size: int, rng: np.random.Generator) -> np.ndarray:
    countries = list(COUNTRY_SHARES.keys())
    return rng.choice(countries, size=size, p=list(COUNTRY_SHARES.values()))


def _jitter_coordinates(
    countries: np.ndarray, rng: np.random.Generator
) -> tuple[np.ndarray, np.ndarray]:
    lat = np.array([COUNTRY_CENTROIDS[c][0] for c in countries], dtype="float64")
    lon = np.array([COUNTRY_CENTROIDS[c][1] for c in countries], dtype="float64")
    lat += rng.uniform(-COUNTRY_JITTER_DEGREES, COUNTRY_JITTER_DEGREES, size=lat.size)
    lon += rng.uniform(-COUNTRY_JITTER_DEGREES, COUNTRY_JITTER_DEGREES, size=lon.size)
    return lat, lon


def build_population(config: PayLoopConfig | None = None) -> Population:
    config = config or load_config()
    blind_start = int(config.n_cardholders * (1.0 - config.blind_holdout_entity_frac))

    merchants = _build_merchants(config)
    cardholders, preferences, amount_mu, amount_sigma = _build_cardholders(config, blind_start)
    devices = _build_devices(config, cardholders)
    ips = _build_ips(config)
    _attach_identity_columns(cardholders, devices, ips)
    accounts = _build_accounts(config, cardholders)
    agents = _build_agents(config)

    popularity = _zipf_popularity(len(merchants))
    affinity = _build_affinity(merchants, preferences, popularity, blind_start)

    return Population(
        config=config,
        sim_start=SIM_START,
        cardholders=cardholders,
        merchants=merchants,
        devices=devices,
        ips=ips,
        accounts=accounts,
        agents=agents,
        mcc_preferences=preferences,
        amount_mu=amount_mu,
        amount_sigma=amount_sigma,
        affinity_merchants=affinity,
        merchant_popularity=popularity,
    )


def _hex_ids(purpose: str, count: int, width: int) -> np.ndarray:
    rng = rng_for(purpose)
    raw = rng.integers(0, 16, size=(count, width))
    digits = np.array(list("0123456789abcdef"))
    return np.array(["".join(row) for row in digits[raw]])


def _attach_identity_columns(
    cardholders: pd.DataFrame, devices: pd.DataFrame, ips: pd.DataFrame
) -> None:
    """Stable per-cardholder identifiers, assigned once so they persist across rounds."""
    rng = rng_for("population:identity")
    count = len(cardholders)
    device_ids = devices["entity_id"].to_numpy()
    ip_ids = ips["entity_id"].to_numpy()
    cardholders["primary_device_id"] = device_ids[np.arange(count) % device_ids.size]
    cardholders["secondary_device_id"] = device_ids[rng.integers(0, device_ids.size, size=count)]
    home_ip = rng.integers(0, ip_ids.size, size=count)
    cardholders["home_ip"] = ip_ids[home_ip]
    cardholders["home_ip_index"] = home_ip
    tails = _hex_ids("population:pan", count, 16)
    cardholders["pan_token"] = np.char.add("tok_", tails)
    cardholders["payer_name_hash"] = _hex_ids("population:name_hash", count, 64)
    cardholders["user_agent_hash"] = _hex_ids("population:user_agent", count, 64)
    cardholders["device_fingerprint_id"] = np.char.add(
        "fp_", _hex_ids("population:fingerprint", count, 16)
    )
    cardholders["device_binding_id"] = np.char.add(
        "DB_", _hex_ids("population:device_binding", count, 12)
    )
    cardholders["vpa"] = np.array([f"ch{i}@payloop" for i in range(count)])


def _zipf_popularity(n_merchants: int) -> np.ndarray:
    """Zipf with s = 1.10 puts the merchant degree tail exponent near 1.9, inside the
    1.5-3.0 band the Clauset-Shalizi-Newman fit is asserted against."""
    ranks = np.arange(1, n_merchants + 1, dtype="float64")
    weights = ranks ** (-ZIPF_S)
    return weights / weights.sum()


def _build_merchants(config: PayLoopConfig) -> pd.DataFrame:
    rng = rng_for("population:merchants")
    count = config.n_merchants
    countries = _country_draw(count, rng)
    lat, lon = _jitter_coordinates(countries, rng)
    created = SIM_START - pd.to_timedelta(
        rng.integers(30, ENTITY_HISTORY_DAYS, size=count), unit="D"
    )
    return pd.DataFrame(
        {
            "entity_id": [f"MR_{i:05d}" for i in range(count)],
            "mcc": rng.choice(MCC_UNIVERSE, size=count),
            "home_country": countries,
            "lat": lat,
            "lon": lon,
            "control_strength": rng.beta(*MERCHANT_CONTROL_BETA, size=count),
            "acquirer_id": _acquirer_assignment(count, rng),
            "terminal_id": [f"TRM_{i:05d}" for i in range(count)],
            "created_ts": created,
        }
    )


def _acquirer_assignment(count: int, rng: np.random.Generator) -> list[str]:
    """Acquiring is concentrated, so one acquirer carries a large share of the estate.

    Without that concentration the acquirer scope sees too little fraud to fit a detector
    at all, and the party-scope comparison loses the column that makes it a comparison."""
    assigned = rng.integers(0, N_ACQUIRERS, size=count)
    concentrated = rng.random(count) < ACQUIRER_CONCENTRATION
    return [
        PRIMARY_ACQUIRER_ID if flag else f"ACQ_{int(value):03d}"
        for value, flag in zip(assigned, concentrated, strict=True)
    ]


def _build_cardholders(
    config: PayLoopConfig, blind_start: int
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray, np.ndarray]:
    rng = rng_for("population:cardholders")
    count = config.n_cardholders
    countries = _country_draw(count, rng)
    in_cohort = np.arange(count) >= blind_start

    alphas = np.where(in_cohort, BLIND_COHORT_DIRICHLET_ALPHA, DIRICHLET_ALPHA)
    preferences = np.empty((count, len(MCC_UNIVERSE)), dtype="float32")
    for alpha in (DIRICHLET_ALPHA, BLIND_COHORT_DIRICHLET_ALPHA):
        mask = alphas == alpha
        if mask.any():
            preferences[mask] = rng.dirichlet(
                np.full(len(MCC_UNIVERSE), alpha), size=int(mask.sum())
            )

    mu_offset = np.where(in_cohort, BLIND_COHORT_MU_OFFSET, 0.0)[:, None]
    amount_mu = (
        LOGNORMAL_MU_DEFAULT + rng.normal(0.0, 0.35, size=(count, len(MCC_UNIVERSE))) + mu_offset
    ).astype("float32")
    amount_sigma = np.clip(
        LOGNORMAL_SIGMA_DEFAULT + rng.normal(0.0, 0.12, size=(count, len(MCC_UNIVERSE))), 0.4, 2.0
    ).astype("float32")

    lat, lon = _jitter_coordinates(countries, rng)
    created = SIM_START - pd.to_timedelta(
        rng.integers(60, ENTITY_HISTORY_DAYS, size=count), unit="D"
    )
    frame = pd.DataFrame(
        {
            "entity_id": [f"CH_{i:06d}" for i in range(count)],
            "home_country": countries,
            "currency": [CURRENCY_BY_COUNTRY[c] for c in countries],
            "lat": lat,
            "lon": lon,
            "lambda_base": rng.lognormal(LAMBDA_BASE_MU, LAMBDA_BASE_SIGMA, size=count),
            "circadian_mu": rng.vonmises(np.pi * 0.75, 2.0, size=count) + np.pi,
            "circadian_kappa": rng.uniform(*CIRCADIAN_KAPPA_RANGE, size=count),
            "issuer_id": [f"ISS_{int(i):03d}" for i in rng.integers(0, N_ISSUERS, size=count)],
            "kyc_level": rng.choice(["FULL", "MIN", "NONE"], size=count, p=[0.82, 0.14, 0.04]),
            "balance_band": rng.choice(["LOW", "MID", "HIGH"], size=count, p=[0.34, 0.48, 0.18]),
            "bin": rng.choice(CARD_BIN_PREFIXES, size=count),
            "card_network": rng.choice(["VISA", "MASTERCARD"], size=count, p=[0.52, 0.48]),
            "in_blind_cohort": in_cohort,
            "created_ts": created,
        }
    )
    # The largest synthetic issuer, so the issuer scope holds a share worth measuring.
    boost = rng.random(count) < ISSUER_CONCENTRATION
    frame.loc[boost, "issuer_id"] = PRIMARY_ISSUER_ID
    return frame, preferences, amount_mu, amount_sigma


def _build_devices(config: PayLoopConfig, cardholders: pd.DataFrame) -> pd.DataFrame:
    rng = rng_for("population:devices")
    count = max(config.n_devices, len(cardholders))
    created = SIM_START - pd.to_timedelta(
        rng.integers(1, ENTITY_HISTORY_DAYS, size=count), unit="D"
    )
    return pd.DataFrame(
        {
            "entity_id": [f"DV_{i:06d}" for i in range(count)],
            "device_os": rng.choice(
                ["ANDROID", "IOS", "WINDOWS", "MACOS", "LINUX"],
                size=count,
                p=[0.52, 0.26, 0.14, 0.06, 0.02],
            ),
            "shared": rng.random(count) < DEVICE_SHARING_RATE,
            "created_ts": created,
        }
    )


def _build_ips(config: PayLoopConfig) -> pd.DataFrame:
    """The three RFC 5737 documentation /24s hold 762 usable addresses between them.

    That is the whole address space available to a simulator that must never emit a
    routable IP, so the distinct-IP count is capped there and heavy address sharing becomes
    a structural property of the population rather than a modelling choice. It is also the
    realistic shape: consumer traffic arrives through carrier-grade NAT."""
    rng = rng_for("population:ips")
    addresses = [f"{block}.{host}" for block in DOCUMENTATION_IP_BLOCKS for host in range(1, 255)]
    count = min(config.n_ips, len(addresses))
    addresses = addresses[:count]
    countries = _country_draw(count, rng)
    return pd.DataFrame(
        {
            "entity_id": addresses,
            "ip_asn": [f"AS{int(value)}" for value in rng.integers(1000, 99999, size=count)],
            "ip_country": countries,
            "proxy_flag": rng.random(count) < IP_PROXY_RATE,
        }
    )


def _build_accounts(config: PayLoopConfig, cardholders: pd.DataFrame) -> pd.DataFrame:
    rng = rng_for("population:accounts")
    count = config.n_accounts
    countries = _country_draw(count, rng)
    created = SIM_START - pd.to_timedelta(
        rng.integers(1, ENTITY_HISTORY_DAYS, size=count), unit="D"
    )
    return pd.DataFrame(
        {
            "entity_id": [f"AC_{i:06d}" for i in range(count)],
            "home_country": countries,
            "bank_bic": [
                f"PAYL{c}{int(i):02d}XXX"
                for c, i in zip(countries, rng.integers(0, 40, size=count), strict=True)
            ],
            "vpa": [f"user{i}@payloop" for i in range(count)],
            "kyc_level": rng.choice(["FULL", "MIN", "NONE"], size=count, p=[0.78, 0.17, 0.05]),
            "balance_band": rng.choice(["LOW", "MID", "HIGH"], size=count, p=[0.40, 0.45, 0.15]),
            "created_ts": created,
        }
    )


def _build_agents(config: PayLoopConfig) -> pd.DataFrame:
    rng = rng_for("population:agents")
    count = config.n_agents
    operators = np.array(
        ["acme-shopping-agent", "vega-concierge", "mira-buyer", "northwind-assist", "kite-agent"]
    )
    return pd.DataFrame(
        {
            "entity_id": [f"AG_{i:05d}" for i in range(count)],
            "agent_operator": rng.choice(operators, size=count),
            "protocol": rng.choice(
                ["AP2", "ACP", "x402", "TAP"], size=count, p=[0.62, 0.18, 0.12, 0.08]
            ),
        }
    )


def _build_affinity(
    merchants: pd.DataFrame, preferences: np.ndarray, popularity: np.ndarray, blind_start: int
) -> np.ndarray:
    """Personal merchant sets, drawn from the holder's Dirichlet MCC preference and then
    weighted by merchant popularity. Cohort holders skip the preferential-attachment
    weighting, so their graph degree distribution differs from the training population."""
    rng = rng_for("population:affinity")
    count = preferences.shape[0]
    cumulative = np.cumsum(preferences.astype("float64"), axis=1)
    cumulative /= cumulative[:, -1:]
    draws = rng.random((count, AFFINITY_MERCHANTS_PER_HOLDER))
    mcc_index = np.array(
        [np.searchsorted(cumulative[i], draws[i]) for i in range(count)], dtype="int32"
    )
    mcc_index = np.clip(mcc_index, 0, len(MCC_UNIVERSE) - 1)

    merchant_mcc = merchants["mcc"].to_numpy()
    by_mcc = {mcc: np.flatnonzero(merchant_mcc == mcc) for mcc in MCC_UNIVERSE}
    attachment = popularity**PREFERENTIAL_ATTACHMENT_EXPONENT

    affinity = np.empty_like(mcc_index)
    holder_index = np.repeat(np.arange(count), AFFINITY_MERCHANTS_PER_HOLDER)
    flat_mcc = mcc_index.reshape(-1)
    flat_out = np.empty(flat_mcc.size, dtype="int32")
    in_cohort = holder_index >= blind_start
    for position, mcc in enumerate(MCC_UNIVERSE):
        candidates = by_mcc[mcc]
        if candidates.size == 0:
            candidates = np.arange(len(merchants))
        selector = flat_mcc == position
        if not selector.any():
            continue
        weights = attachment[candidates]
        weights = weights / weights.sum()
        cohort_slice = selector & in_cohort
        pool_slice = selector & ~in_cohort
        if pool_slice.any():
            flat_out[pool_slice] = candidates[
                rng.choice(candidates.size, size=int(pool_slice.sum()), p=weights)
            ]
        if cohort_slice.any():
            flat_out[cohort_slice] = candidates[
                rng.integers(0, candidates.size, size=int(cohort_slice.sum()))
            ]
    affinity = flat_out.reshape(count, AFFINITY_MERCHANTS_PER_HOLDER)
    return affinity


def entities_frame(population: Population) -> pd.DataFrame:
    """The flat entity table written to data/entities.parquet and the DuckDB entities table."""
    parts = []
    for entity_type, frame in (
        ("cardholder", population.cardholders),
        ("merchant", population.merchants),
        ("device", population.devices),
        ("ip", population.ips),
        ("account", population.accounts),
        ("agent", population.agents),
    ):
        present = [key for key in ATTRIBUTE_COLUMNS if key in frame.columns]
        attributes = (
            frame[present].astype(str).to_dict(orient="records")
            if present
            else [{}] * len(frame)
        )
        attributes = [json.dumps(record, sort_keys=True) for record in attributes]
        block = pd.DataFrame(
            {
                "entity_id": frame["entity_id"].to_numpy(),
                "entity_type": entity_type,
                "created_ts": (
                    frame["created_ts"].to_numpy()
                    if "created_ts" in frame.columns
                    else pd.Timestamp(SIM_START)
                ),
                "home_country": (
                    frame["home_country"].to_numpy() if "home_country" in frame.columns else "IN"
                ),
                "in_blind_cohort": (
                    frame["in_blind_cohort"].to_numpy()
                    if "in_blind_cohort" in frame.columns
                    else False
                ),
                "attributes": attributes,
            }
        )
        parts.append(block)
    return pd.concat(parts, ignore_index=True)


def next_arrival(holder: Cardholder, current: datetime, rng: np.random.Generator) -> datetime:
    """Lewis-Shedler thinning, single-arrival form. lam_max must bound lambda(t) everywhere
    or the arrivals are silently biased, so the bound is asserted rather than assumed.
    generate/behavior.py runs the identical acceptance rule in batch for bulk emission."""
    from backend.generate.behavior import MAX_INTENSITY_MULTIPLIER, intensity_multiplier

    lam_max = holder.lambda_base * MAX_INTENSITY_MULTIPLIER
    if lam_max <= 0.0:
        raise ValueError("lambda upper bound must be positive")
    candidate = current
    while True:
        candidate = candidate + timedelta(hours=float(rng.exponential(1.0 / lam_max)))
        intensity = holder.lambda_base * intensity_multiplier(candidate.hour, candidate.weekday())
        if intensity > lam_max:
            raise ValueError("lambda(t) exceeded its upper bound; the thinning bound is wrong")
        if rng.random() < intensity / lam_max:
            return candidate
