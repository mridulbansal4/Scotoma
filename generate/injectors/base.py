"""Injector protocol, Campaign container, and the helpers every injector shares."""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Protocol
from uuid import UUID

import networkx as nx
import numpy as np
import pandas as pd

from generate.population import Population
from runtime.config import load_config
from runtime.seeding import seeded_uuid
from runtime.timewindows import TimeWindow
from schema.ces import CES_COLUMNS, FX_RATE_TABLE, RAIL_LIMITS, coerce_dtypes

# PANs are synthesised inside designated test BIN ranges only. Real PANs never appear,
# which is also what keeps the whole simulator outside PCI scope.
TEST_BIN_RANGES: tuple[tuple[int, int], ...] = ((41111100, 41111199), (52223000, 52223099))

# Share of enumeration probes that land on a live PAN, from published card-testing telemetry.
LIVE_PAN_HIT_RATE: float = 0.06

LUHN_MODULUS: int = 10
PAN_LENGTH: int = 16
MAX_CAMPAIGN_EVENTS: int = 60_000
EVENTS_PER_BURST: int = 14
BURST_SCALE_SECONDS: float = 900.0
CADENCE_SIGMA: float = 1.1


@dataclass
class Campaign:
    campaign_id: UUID
    vector_id: str
    params: dict
    events: pd.DataFrame
    subgraph: nx.MultiDiGraph
    rationale: str = ""
    mutation_lineage: list[str] = field(default_factory=list)


class Injector(Protocol):
    vector_id: str
    param_schema: dict

    def inject(
        self,
        population: Population,
        params: dict,
        window: TimeWindow,
        rng: np.random.Generator,
    ) -> Campaign: ...


def _luhn_check_digit(body: str) -> int:
    total = 0
    for position, character in enumerate(reversed(body)):
        digit = int(character)
        if position % 2 == 0:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return (LUHN_MODULUS - total % LUHN_MODULUS) % LUHN_MODULUS


def synth_pan(
    bin_prefix: str, stride: int, index: int, rng: np.random.Generator, luhn_valid: bool = True
) -> str:
    """PANs are generated inside designated test BIN ranges only. Real PANs never appear,
    which is also what keeps the whole simulator outside PCI scope."""
    prefix_value = int(bin_prefix)
    if not any(low <= prefix_value <= high for low, high in TEST_BIN_RANGES):
        raise ValueError(f"bin prefix {bin_prefix} falls outside TEST_BIN_RANGES")
    account_digits = PAN_LENGTH - len(bin_prefix) - 1
    account = (index * max(stride, 1) + int(rng.integers(0, 10))) % (10**account_digits)
    body = f"{bin_prefix}{account:0{account_digits}d}"
    check = _luhn_check_digit(body) if luhn_valid else (int(rng.integers(0, 10)))
    return f"{body}{check}"


def cart_hash(line_items: list[dict]) -> str:
    """SHA-256 over the canonical JSON of the line items, as AP2 binds the cart into the
    Payment Mandate. Mutation after signing breaks the hash, which is the V19 signal."""
    canonical = json.dumps(line_items, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def blank_rows(count: int) -> dict[str, list]:
    return {column: [None] * count for column in CES_COLUMNS}


def hex_token(rng: np.random.Generator, width: int) -> str:
    return "".join(f"{int(d):x}" for d in rng.integers(0, 16, size=width))


def amount_in_band(band: list[float], size: int, rng: np.random.Generator, rail: str) -> np.ndarray:
    """Log-uniform over the band. A uniform draw piles leading digits onto whichever
    decade the band straddles and shows up immediately as a Benford failure; log-uniform
    is the maximum-entropy choice that conforms."""
    low, high = float(band[0]), float(band[1])
    high = min(high, RAIL_LIMITS[rail])
    low = max(min(low, high), 0.01)
    return np.round(np.exp(rng.uniform(np.log(low), np.log(max(high, low * 1.01)), size=size)), 2)


def log_uniform(low: float, high: float, rng: np.random.Generator, size: int | None = None):
    """Single-value or vector log-uniform draw, used wherever a campaign picks an amount."""
    drawn = np.exp(rng.uniform(np.log(max(low, 0.01)), np.log(max(high, low * 1.01)), size=size))
    return np.round(drawn, 2)


def currency_of(entity: pd.Series, fallback: str) -> str:
    """Campaigns settle in the payer's own currency; forcing one currency per vector breaks
    the country-to-currency association the joint fidelity layer measures."""
    value = entity.get("currency")
    return str(value) if isinstance(value, str) else fallback


def to_inr_array(amount: np.ndarray, currency: np.ndarray) -> np.ndarray:
    rates = np.array([FX_RATE_TABLE.get(str(c), 1.0) for c in currency])
    return np.round(amount * rates, 2)


def finalise(
    rows: list[dict], vector_id: str, campaign_id: UUID, lineage: list[str]
) -> pd.DataFrame:
    """Coerce a list of partial CES rows into a full, label-complete CES frame."""
    if not rows:
        return pd.DataFrame(columns=list(CES_COLUMNS))
    frame = pd.DataFrame(rows)
    frame["is_fraud"] = True
    frame["vector_id"] = vector_id
    frame["campaign_id"] = str(campaign_id)
    frame["mutation_lineage"] = [list(lineage) for _ in range(len(frame))]
    embargo = load_config().label_embargo_days
    frame["event_ts"] = pd.to_datetime(frame["event_ts"], utc=True)
    frame["label_available_ts"] = frame["event_ts"] + pd.Timedelta(days=embargo)
    for column in CES_COLUMNS:
        if column not in frame.columns:
            frame[column] = None
    frame = frame.sort_values("event_ts").reset_index(drop=True)
    return coerce_dtypes(frame[list(CES_COLUMNS)].head(MAX_CAMPAIGN_EVENTS))


def campaign_subgraph(frame: pd.DataFrame) -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph()
    if frame.empty:
        return graph
    for payer, payee in zip(frame["payer_entity_id"], frame["payee_entity_id"], strict=True):
        graph.add_edge(str(payer), str(payee), edge_type="pays")
    return graph


def spread_timestamps(window: TimeWindow, count: int, rng: np.random.Generator) -> pd.DatetimeIndex:
    """Campaign activity arrives in bursts separated by quiet stretches. A uniform spread
    would give an inter-event-time burstiness of about zero, which no real campaign has."""
    span = window.duration_seconds()
    bursts = max(int(count / EVENTS_PER_BURST), 1)
    centres = rng.random(bursts) * span
    assignment = rng.integers(0, bursts, size=count)
    within = rng.exponential(BURST_SCALE_SECONDS, size=count)
    offsets = np.clip(centres[assignment] + within, 0.0, span)
    return pd.Timestamp(window.start) + pd.to_timedelta(np.sort(offsets), unit="s")


def cadence_timestamps(
    window: TimeWindow, per_minute: float, dwell_seconds: float, limit: int,
    rng: np.random.Generator,
) -> pd.DatetimeIndex:
    step = 60.0 / max(per_minute, 1e-6) + max(dwell_seconds, 0.0)
    span = window.duration_seconds()
    count = min(int(span // step) + 1, limit)
    # A perfectly regular cadence is the one thing a rate limiter catches immediately, so
    # the gaps are drawn heavy-tailed around the requested rate instead.
    gaps = step * np.exp(rng.normal(-CADENCE_SIGMA**2 / 2.0, CADENCE_SIGMA, size=count))
    offsets = np.clip(np.cumsum(gaps), 0.0, span)
    return pd.Timestamp(window.start) + pd.to_timedelta(offsets, unit="s")


def window_days(window: TimeWindow) -> float:
    return window.duration_seconds() / timedelta(days=1).total_seconds()


AGENTIC_RAIL: str = "AGENTIC"
AGENTIC_CURRENCY: str = "USD"


def agentic_row(
    event_key: str,
    index: int,
    timestamp: pd.Timestamp,
    payer_id: str,
    payee_id: str,
    payer_country: str,
    payee_country: str,
    amount: float,
    agent: pd.Series,
    rng: np.random.Generator,
    currency: str = AGENTIC_CURRENCY,
) -> dict:
    """A settled agent-initiated payment with every mandate field populated and valid.
    Each agentic injector then breaks exactly one of them, which is what makes the
    resulting signal attributable to a single mechanism."""
    line_items = [{"sku": f"SKU-{index % 9999:04d}", "qty": 1, "unit_price": round(amount, 2)}]
    digest = cart_hash(line_items)
    return {
        "event_id": str(seeded_uuid(event_key, index)),
        "event_ts": timestamp,
        "rail": AGENTIC_RAIL,
        "amount": round(float(amount), 2),
        "currency": currency,
        "amount_inr": round(float(amount) * FX_RATE_TABLE.get(currency, 1.0), 2),
        "payer_entity_id": payer_id,
        "payee_entity_id": payee_id,
        "payer_country": payer_country,
        "payee_country": payee_country,
        "cross_border": payer_country != payee_country,
        "payer_kyc_level": "FULL",
        "payer_balance_band": "HIGH",
        "response_code": "00",
        "agent_id": str(agent["entity_id"]),
        "agent_operator": str(agent["agent_operator"]),
        "protocol": "AP2",
        "agent_attestation_valid": True,
        "intent_mandate_id": str(seeded_uuid(f"{event_key}:intent", index)),
        "cart_mandate_id": str(seeded_uuid(f"{event_key}:cart", index)),
        "payment_mandate_id": str(seeded_uuid(f"{event_key}:payment", index)),
        "human_present_flag": False,
        "mandate_amount_max": round(float(amount) * 1.25, 2),
        "mandate_merchant_allowlist": [payee_id],
        "mandate_expiry_ts": timestamp + pd.Timedelta(hours=12),
        "mandate_signature_valid": True,
        "mandate_nonce": f"n_{hex_token(rng, 10)}",
        "cart_hash_at_intent": digest,
        "cart_hash_at_settle": digest,
        "payee_at_intent": payee_id,
        "payee_at_settle": payee_id,
        "_line_items": line_items,
    }
