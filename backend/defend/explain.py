"""Interventional TreeSHAP over the production GBDT, mapped to adverse-action reason codes."""

import numpy as np
import pandas as pd

REASON_DICTIONARY: dict[str, tuple[str, str]] = {
    "distinct_pan_per_device_10m": ("R014", "Unusual velocity on this device"),
    "declrate_ip_1h": ("R031", "Elevated decline rate on originating network"),
    "merchant_control_strength": ("R022", "Merchant risk profile above threshold"),
    "cart_hash_mismatch": ("R047", "Cart contents changed after user approval"),
    "mandate_scope_breach": ("R048", "Payment outside the authorised mandate scope"),
    "attestation_invalid": ("R049", "Agent attestation could not be verified"),
    "nonce_reused": ("R050", "Mandate credential presented more than once"),
    "first_time_payee": ("R011", "First payment to this beneficiary"),
    "payee_age_hours": ("R012", "Beneficiary account recently created"),
    "impossible_travel_kmh": ("R018", "Location change faster than physically possible"),
    "fanin_payee_24h": ("R033", "Many payers converging on one beneficiary"),
    "amount_z_vs_entity_history": ("R007", "Amount far outside this customer's normal range"),
}

# The default path-dependent expectation can attribute importance to features not used on
# a given path, which is the wrong basis for a reason code.
SHAP_PERTURBATION: str = "interventional"
SHAP_BACKGROUND_ROWS: int = 1000
DEFAULT_TOP_K: int = 3
GENERIC_REASON_CODE: str = "R000"
GENERIC_REASON_LABEL: str = "Model score driven by an unmapped feature"

# The twelve codes above are the specified dictionary and are not touched. These extend it
# so that a reason code is a sentence an adverse-action notice could carry, rather than an
# admission that the top feature was not in the table.
EXTENDED_REASON_DICTIONARY: dict[str, tuple[str, str]] = {
    "eci_semantic_code": ("R052", "Authentication outcome weaker than usual for this customer"),
    "threeds_flow_code": ("R053", "Payment did not complete a strong authentication challenge"),
    "pos_entry_mode_code": ("R054", "Entry mode unusual for this acceptance channel"),
    "device_age_hours": ("R055", "Device first seen very recently"),
    "circadian_loglik": ("R056", "Transaction time unusual for this customer"),
    "bin_seq_entropy": ("R057", "Card numbers seen on this device span an improbable range"),
    "cross_border": ("R058", "Payment crosses a border"),
    "sca_exempt_flag": ("R059", "Authentication exemption claimed"),
    "mcc_novelty_for_entity": ("R060", "First purchase in this merchant category"),
    "merchant_benford_dev_24h": ("R061", "Merchant amount distribution deviates from expectation"),
    "terminal_age_days": ("R062", "Terminal recently commissioned"),
    "payee_bank_degree": ("R063", "Beneficiary bank serves an unusual number of payers"),
    "fanout_payer_24h": ("R064", "Payer sending to many beneficiaries"),
    "component_size": ("R065", "Entity sits in an unusually large linked cluster"),
    "payer_pagerank": ("R066", "Payer central to a linked entity cluster"),
    "payee_pagerank": ("R067", "Beneficiary central to a linked entity cluster"),
    "settle_vs_intent_amount_delta": ("R068", "Settled amount differs from the authorised ceiling"),
    "human_present_flag_num": ("R069", "No human present at authorisation"),
    "payee_name_match_num": ("R070", "Beneficiary name did not match the account record"),
    "upi_txn_type_code": ("R071", "Collect request rather than a push payment"),
}

VELOCITY_AGGREGATION_LABELS: dict[str, str] = {
    "cnt": "Transaction count",
    "sum": "Transaction value",
    "declrate": "Decline rate",
    "amtstd": "Amount variability",
}
VELOCITY_KEY_LABELS: dict[str, str] = {
    "pan_token": "on this card",
    "device_id": "on this device",
    "ip": "on this network",
    "merchant_id": "at this merchant",
    "payee_entity_id": "to this beneficiary",
    "agent_id": "for this agent",
}
VELOCITY_REASON_CODE: str = "R080"


def background_sample(design: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    if design.shape[0] <= SHAP_BACKGROUND_ROWS:
        return design
    return design[rng.choice(design.shape[0], size=SHAP_BACKGROUND_ROWS, replace=False)]


def shap_values(booster, design: np.ndarray, background: np.ndarray) -> np.ndarray:
    """Attributions are returned in the model's margin space, where additivity holds."""
    import shap

    explainer = shap.TreeExplainer(
        booster, data=background, feature_perturbation=SHAP_PERTURBATION, model_output="raw"
    )
    values = explainer.shap_values(design, check_additivity=False)
    if isinstance(values, list):
        values = values[-1]
    return np.asarray(values)


def reason_for(feature: str) -> tuple[str, str]:
    if feature in REASON_DICTIONARY:
        return REASON_DICTIONARY[feature]
    if feature in EXTENDED_REASON_DICTIONARY:
        return EXTENDED_REASON_DICTIONARY[feature]
    velocity = _velocity_reason(feature)
    return velocity or (GENERIC_REASON_CODE, GENERIC_REASON_LABEL)


def _velocity_reason(feature: str) -> tuple[str, str] | None:
    """Velocity features are 120 of the 151, so they get a generated sentence rather than
    120 hand-written table rows that would say the same thing."""
    parts = feature.split("_")
    if len(parts) < 3:
        return None
    aggregation, window = parts[0], parts[-1]
    key = "_".join(parts[1:-1])
    if aggregation not in VELOCITY_AGGREGATION_LABELS or key not in VELOCITY_KEY_LABELS:
        return None
    label = (
        f"{VELOCITY_AGGREGATION_LABELS[aggregation]} {VELOCITY_KEY_LABELS[key]} "
        f"over the last {window}"
    )
    return VELOCITY_REASON_CODE, label


def top_reasons(
    shap_row: np.ndarray,
    feature_names: list[str],
    feature_values: pd.Series,
    k: int = DEFAULT_TOP_K,
) -> list[dict]:
    order = np.argsort(-np.abs(shap_row))[:k]
    reasons = []
    for position in order:
        feature = feature_names[int(position)]
        code, label = reason_for(feature)
        reasons.append(
            {
                "code": code,
                "label": label,
                "feature": feature,
                "value": float(feature_values.iloc[int(position)]),
                "shap": round(float(shap_row[int(position)]), 4),
            }
        )
    return reasons


def reason_dictionary_payload() -> dict:
    return {
        "perturbation": SHAP_PERTURBATION,
        "background_rows": SHAP_BACKGROUND_ROWS,
        "attribution_space": "log-odds margin",
        "codes": [
            {"code": code, "label": label, "feature": feature}
            for feature, (code, label) in sorted(
                {**REASON_DICTIONARY, **EXTENDED_REASON_DICTIONARY}.items()
            )
        ],
        "velocity_code": VELOCITY_REASON_CODE,
    }
