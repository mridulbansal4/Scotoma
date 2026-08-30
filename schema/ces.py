"""The Canonical Event Schema. One table, superset of six rails. Everything writes CES."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from runtime.config import load_config
from runtime.errors import FeatureLeakage, SchemaViolation
from schema.mappings.iso8583 import DE39_CODES, MTI_CODES, POS_ENTRY_MODES

# Static table so amount_inr is comparable across rails without a network call.
FX_RATE_TABLE: dict[str, float] = {
    "INR": 1.0,
    "USD": 83.14,
    "EUR": 90.42,
    "GBP": 105.71,
    "SGD": 61.83,
    "AED": 22.63,
}

RAILS: tuple[str, ...] = ("CARD_CNP", "CARD_CP", "UPI", "SEPA_INST", "ACH", "AGENTIC")

# Rail ceilings used by the constraint validator and by amount clipping in the simulator.
RAIL_LIMITS: dict[str, float] = {
    "CARD_CNP": 500_000.0,
    "CARD_CP": 500_000.0,
    "UPI": 100_000.0,
    "SEPA_INST": 1_000_000.0,
    "ACH": 1_000_000.0,
    "AGENTIC": 500_000.0,
}

AVS_RESULTS: frozenset[str] = frozenset({"Y", "A", "Z", "N", "U", "S", "G"})
CVV_RESULTS: frozenset[str] = frozenset({"M", "N", "P", "U", "S"})

# ECI is network-specific and effectively swapped between schemes, so features read
# eci_semantic and never the raw integer.
ECI_SEMANTICS: dict[str, dict[str, str]] = {
    "VISA": {"05": "authenticated", "06": "attempted", "07": "not_authenticated"},
    "MASTERCARD": {"02": "authenticated", "01": "attempted", "00": "not_authenticated"},
}

LABEL_COLUMNS = frozenset(
    {
        "is_fraud",
        "vector_id",
        "campaign_id",
        "red_team_round",
        "mutation_lineage",
        "label_available_ts",
    }
)
IDENTIFIER_COLUMNS = frozenset(
    {
        "event_id",
        "payer_entity_id",
        "payee_entity_id",
        "pan_token",
        "device_id",
        "ip",
        "merchant_id",
        "vpa_payer",
        "vpa_payee",
        "agent_id",
        "terminal_id",
        "device_fingerprint_id",
        "user_agent_hash",
        "uetr",
        "payer_name_hash",
        "intent_mandate_id",
        "cart_mandate_id",
        "payment_mandate_id",
        "mandate_id",
    }
)

MAX_REPORTED_VIOLATIONS: int = 10

DATETIME_COLUMNS: tuple[str, ...] = (
    "event_ts",
    "device_first_seen_ts",
    "beneficiary_first_seen_ts",
    "settlement_ts",
    "mandate_expiry_ts",
    "label_available_ts",
)
NUMERIC_CES_COLUMNS: tuple[str, ...] = (
    "amount",
    "amount_inr",
    "mandate_amount_max",
    "browser_tz_offset",
)


class CanonicalEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: UUID
    event_ts: datetime
    rail: Literal["CARD_CNP", "CARD_CP", "UPI", "SEPA_INST", "ACH", "AGENTIC"]
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency: str = Field(min_length=3, max_length=3)
    amount_inr: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    payer_entity_id: str = Field(pattern=r"^(CH|AC)_\d{6}$")
    payee_entity_id: str = Field(pattern=r"^(MR|AC)_\d{5,6}$")
    payer_country: str = Field(min_length=2, max_length=2)
    payee_country: str = Field(min_length=2, max_length=2)
    cross_border: bool
    payer_name_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    payer_kyc_level: Literal["FULL", "MIN", "NONE"] | None = None
    payer_balance_band: Literal["LOW", "MID", "HIGH"] | None = None

    pan_token: str | None = Field(default=None, max_length=24)
    bin: str | None = Field(default=None, pattern=r"^\d{8}$")
    issuer_id: str | None = Field(default=None, pattern=r"^ISS_\d{3}$")
    acquirer_id: str | None = Field(default=None, pattern=r"^ACQ_\d{3}$")
    merchant_id: str | None = Field(default=None, pattern=r"^MR_\d{5}$")
    mcc: str | None = Field(default=None, pattern=r"^\d{4}$")
    pos_entry_mode: str | None = None
    processing_code: str | None = Field(default=None, pattern=r"^\d{6}$")
    mti: str | None = None
    response_code: str | None = None
    avs_result: str | None = None
    cvv_result: str | None = None
    terminal_id: str | None = Field(default=None, max_length=12)
    merchant_country: str | None = Field(default=None, min_length=2, max_length=2)

    threeds_version: str | None = Field(default=None, pattern=r"^2\.[12]\.\d$")
    threeds_flow: Literal["frictionless", "challenge", "none"] | None = None
    eci: str | None = None
    eci_semantic: Literal["authenticated", "attempted", "not_authenticated"] | None = None
    card_network: Literal["VISA", "MASTERCARD"] | None = None
    cavv_present: bool | None = None
    threeds_method_completed: bool | None = None
    device_fingerprint_id: str | None = Field(default=None, pattern=r"^fp_[0-9a-f]{16}$")
    browser_screen_res: str | None = Field(default=None, pattern=r"^\d{3,4}x\d{3,4}$")
    browser_tz_offset: int | None = Field(default=None, ge=-720, le=840)
    browser_lang: str | None = None
    sca_exempt_reason: (
        Literal["low_value", "tra", "trusted_beneficiary", "recurring", "corporate"] | None
    ) = None

    device_id: str | None = Field(default=None, pattern=r"^DV_[A-Z0-9_]{4,12}$")
    device_os: Literal["ANDROID", "IOS", "WINDOWS", "MACOS", "LINUX"] | None = None
    device_first_seen_ts: datetime | None = None
    ip: str | None = None
    ip_asn: str | None = Field(default=None, pattern=r"^AS\d{3,6}$")
    ip_country: str | None = Field(default=None, min_length=2, max_length=2)
    ip_proxy_flag: bool | None = None
    user_agent_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    vpa_payer: str | None = Field(default=None, pattern=r"^[a-z0-9._-]+@[a-z]+$")
    vpa_payee: str | None = Field(default=None, pattern=r"^[a-z0-9._-]+@[a-z]+$")
    upi_txn_type: Literal["push", "collect"] | None = None
    mandate_id: UUID | None = None
    payee_name_match: bool | None = None
    beneficiary_first_seen_ts: datetime | None = None
    device_binding_id: str | None = Field(default=None, pattern=r"^DB_[0-9a-f]{12}$")

    uetr: UUID | None = None
    debtor_agent_bic: str | None = None
    creditor_agent_bic: str | None = None
    settlement_ts: datetime | None = None
    remittance_ref: str | None = Field(default=None, max_length=140)
    return_code: str | None = None

    agent_id: str | None = Field(default=None, pattern=r"^AG_\d{5}$")
    agent_operator: str | None = Field(default=None, max_length=64)
    protocol: Literal["AP2", "ACP", "x402", "TAP"] | None = None
    agent_attestation_valid: bool | None = None
    intent_mandate_id: UUID | None = None
    cart_mandate_id: UUID | None = None
    payment_mandate_id: UUID | None = None
    human_present_flag: bool | None = None
    mandate_amount_max: Decimal | None = Field(default=None, gt=0)
    mandate_merchant_allowlist: list[str] | None = None
    mandate_expiry_ts: datetime | None = None
    mandate_signature_valid: bool | None = None
    mandate_nonce: str | None = Field(default=None, pattern=r"^n_[0-9a-f]{10}$")
    cart_hash_at_intent: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    cart_hash_at_settle: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    payee_at_intent: str | None = Field(default=None, pattern=r"^MR_\d{5}$")
    payee_at_settle: str | None = Field(default=None, pattern=r"^MR_\d{5}$")

    is_fraud: bool
    vector_id: str | None = Field(default=None, pattern=r"^V\d{2}$")
    campaign_id: UUID | None = None
    red_team_round: int | None = None
    mutation_lineage: list[str] = Field(default_factory=list)
    label_available_ts: datetime | None = None

    @field_validator("event_ts", "device_first_seen_ts", "mandate_expiry_ts")
    @classmethod
    def _require_tz(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("timestamps must carry tzinfo (UTC)")
        return value

    @field_validator("currency", "payer_country", "payee_country")
    @classmethod
    def _upper(cls, value: str) -> str:
        if value != value.upper():
            raise ValueError("ISO codes must be uppercase")
        return value

    @model_validator(mode="after")
    def _domain_rules(self) -> "CanonicalEvent":
        if self.cross_border != (self.payer_country != self.payee_country):
            raise ValueError("cross_border must equal payer_country != payee_country")
        if self.pos_entry_mode is not None and self.pos_entry_mode not in POS_ENTRY_MODES:
            raise ValueError(f"unknown pos_entry_mode {self.pos_entry_mode}")
        if self.mti is not None and self.mti not in MTI_CODES:
            raise ValueError(f"unknown mti {self.mti}")
        if self.response_code is not None and self.response_code not in DE39_CODES:
            raise ValueError(f"unknown DE39 response_code {self.response_code}")
        if self.avs_result is not None and self.avs_result not in AVS_RESULTS:
            raise ValueError(f"unknown avs_result {self.avs_result}")
        if self.cvv_result is not None and self.cvv_result not in CVV_RESULTS:
            raise ValueError(f"unknown cvv_result {self.cvv_result}")
        if self.pan_token is not None and not self.pan_token.startswith("tok_"):
            raise ValueError("pan_token must carry the tok_ prefix")
        if self.eci is not None and self.card_network is not None:
            expected = ECI_SEMANTICS[self.card_network].get(self.eci)
            if expected is None:
                raise ValueError(f"eci {self.eci} is not valid for {self.card_network}")
            if self.eci_semantic is not None and self.eci_semantic != expected:
                raise ValueError("eci_semantic inconsistent with eci and card_network")
        if self.protocol == "AP2" and self.payment_mandate_id is None:
            raise ValueError("AP2 events require a payment_mandate_id")
        if self.payment_mandate_id is not None and self.human_present_flag is None:
            raise ValueError("human_present_flag is required when a payment mandate is present")
        if self.is_fraud and self.vector_id is None:
            raise ValueError("fraud events must carry a vector_id")
        return self


CES_COLUMNS: tuple[str, ...] = tuple(CanonicalEvent.model_fields.keys())


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, list):
        return False
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def validate_frame(frame: pd.DataFrame, strict: bool = True) -> pd.DataFrame:
    """Row-wise CES validation. strict=True raises listing at most 10 offending rows."""
    violations: list[str] = []
    keep: list[int] = []
    for position, record in enumerate(frame.to_dict(orient="records")):
        payload = {k: v for k, v in record.items() if not _is_missing(v)}
        try:
            CanonicalEvent.model_validate(payload)
            keep.append(position)
        except ValueError as exc:
            violations.append(f"row {position}: {exc}")
    if violations and strict:
        head = "\n".join(violations[:MAX_REPORTED_VIOLATIONS])
        raise SchemaViolation(f"{len(violations)} invalid CES rows\n{head}")
    if violations:
        return frame.iloc[keep].reset_index(drop=True)
    return frame


def feature_columns(frame: pd.DataFrame) -> list[str]:
    """Raw identifiers are legal as aggregation keys and illegal as features."""
    banned = LABEL_COLUMNS | IDENTIFIER_COLUMNS
    selected = [c for c in frame.columns if c not in banned]
    leaked = set(selected) & banned
    if leaked:
        raise FeatureLeakage(f"label or raw identifier in feature set: {sorted(leaked)}")
    return selected


def apply_label_embargo(frame: pd.DataFrame, cutoff_ts: datetime) -> pd.DataFrame:
    """A label reaches training only once event_ts + embargo has elapsed."""
    if "label_available_ts" not in frame.columns:
        return frame
    available = pd.to_datetime(frame["label_available_ts"], utc=True, errors="coerce")
    return frame[available <= pd.Timestamp(cutoff_ts)].reset_index(drop=True)


def label_available_ts_for(event_ts: datetime) -> datetime:
    return event_ts + timedelta(days=load_config().label_embargo_days)


def to_inr(amount: float, currency: str) -> float:
    return round(amount * FX_RATE_TABLE.get(currency, 1.0), 2)


def utc_now() -> datetime:
    return datetime.now(UTC)


def coerce_dtypes(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalise CES column dtypes so frames from different producers concatenate cleanly."""
    working = frame.copy()
    for column in DATETIME_COLUMNS:
        if column in working.columns:
            working[column] = pd.to_datetime(working[column], utc=True, errors="coerce")
    for column in NUMERIC_CES_COLUMNS:
        if column in working.columns:
            working[column] = pd.to_numeric(working[column], errors="coerce")
    if "cross_border" in working.columns:
        working["cross_border"] = working["cross_border"].astype(bool)
    if "is_fraud" in working.columns:
        working["is_fraud"] = working["is_fraud"].astype(bool)
    if "mutation_lineage" not in working.columns:
        working["mutation_lineage"] = [[] for _ in range(len(working))]
    return working
