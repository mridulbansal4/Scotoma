"""Party-scope projection: row restriction plus column mask. Declared once, here."""

from typing import Literal

import pandas as pd

SCOPE_ROW_FILTERS: dict[str, str | None] = {
    "ISSUER": "issuer_id == @party_id",
    "ACQUIRER": "acquirer_id == @party_id",
    "NETWORK": None,
}

SCOPE_NULLED_COLUMNS: dict[str, frozenset[str]] = {
    "ISSUER": frozenset(
        {
            "merchant_control_strength",
            "merchant_benford_dev_24h",
            "fanin_payee_24h",
            "payee_bank_degree",
            "terminal_age_days",
        }
    ),
    "ACQUIRER": frozenset(
        {
            "amount_z_vs_entity_history",
            "circadian_loglik",
            "mcc_novelty_for_entity",
            "impossible_travel_kmh",
            "payer_kyc_level",
            "payer_balance_band",
        }
    ),
    "NETWORK": frozenset({"payer_kyc_level", "payer_balance_band", "payer_name_hash"}),
}

DEFAULT_PARTY_IDS: dict[str, str] = {"ISSUER": "ISS_007", "ACQUIRER": "ACQ_014", "NETWORK": ""}

ScopeName = Literal["ISSUER", "ACQUIRER", "NETWORK"]


def masked_columns(scope: str) -> frozenset[str]:
    return SCOPE_NULLED_COLUMNS[scope]


def project_frame(
    frame: pd.DataFrame, scope: ScopeName, party_id: str | None = None
) -> pd.DataFrame:
    """Row restriction then column mask. Returns a copy; never mutates the input."""
    restriction = SCOPE_ROW_FILTERS[scope]
    working = frame
    if restriction is not None:
        column = restriction.split(" ==")[0]
        target = party_id or DEFAULT_PARTY_IDS[scope]
        working = frame[frame[column] == target]
    projected = working.copy()
    for column in masked_columns(scope):
        if column in projected.columns:
            projected[column] = pd.NA
    return projected.reset_index(drop=True)


def project_event(event: dict, scope: ScopeName) -> dict:
    projected = dict(event)
    for column in masked_columns(scope):
        if column in projected:
            projected[column] = None
    return projected
