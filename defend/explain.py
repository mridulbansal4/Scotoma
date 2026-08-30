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
    return REASON_DICTIONARY.get(feature, (GENERIC_REASON_CODE, GENERIC_REASON_LABEL))


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
            for feature, (code, label) in sorted(REASON_DICTIONARY.items())
        ],
    }
