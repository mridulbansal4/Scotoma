"""INJECTORS maps a vector id to its injector class. Eight modules, twelve classes."""

from generate.injectors.agentic_injection import CartInjectionCampaign
from generate.injectors.agentic_replay import AgentImpersonationCampaign, MandateReplayCampaign
from generate.injectors.agentic_scope import MandateScopeBreachCampaign
from generate.injectors.app_mule import (
    AppScamCampaign,
    CollectRequestAbuseCampaign,
    MuleNetworkCampaign,
)
from generate.injectors.base import Campaign, Injector
from generate.injectors.enumeration import BinAttackCampaign, EnumerationCampaign
from generate.injectors.evasion import ScorerEvasionCampaign
from generate.injectors.sca_gap import CrossBorderScaGapCampaign
from generate.injectors.synthetic_id import SyntheticIdentityRingCampaign

INJECTORS: dict[str, type] = {
    "V01": EnumerationCampaign,
    "V02": BinAttackCampaign,
    "V05": AppScamCampaign,
    "V06": CollectRequestAbuseCampaign,
    "V07": SyntheticIdentityRingCampaign,
    "V18": MandateScopeBreachCampaign,
    "V19": CartInjectionCampaign,
    "V20": AgentImpersonationCampaign,
    "V21": MandateReplayCampaign,
    "V22": ScorerEvasionCampaign,
    "V28": MuleNetworkCampaign,
    "V31": CrossBorderScaGapCampaign,
}

PARAM_SCHEMAS: dict[str, dict] = {
    vector_id: injector.param_schema for vector_id, injector in INJECTORS.items()
}

RAIL_OF_VECTOR: dict[str, str] = {
    "V01": "CARD_CNP",
    "V02": "CARD_CNP",
    "V05": "UPI",
    "V06": "UPI",
    "V07": "CARD_CNP",
    "V18": "AGENTIC",
    "V19": "AGENTIC",
    "V20": "AGENTIC",
    "V21": "AGENTIC",
    "V22": "CARD_CNP",
    "V28": "SEPA_INST",
    "V31": "CARD_CNP",
}

DEFAULT_PARAMS: dict[str, dict] = {
    "V01": {
        "probes_per_min": 6.0,
        "n_merchants": 220,
        "amount_band": [0.8, 3.0],
        "bin_stride": 7,
        "dwell_s": 45.0,
    },
    "V02": {"bin_prefix_count": 3, "pans_per_bin": 900, "validation_amount": 1.2},
    "V05": {
        "victim_count": 90,
        "grooming_days": 6.0,
        "first_payment_ratio": 0.35,
        "escalation_factor": 1.7,
    },
    "V06": {"collect_rate_per_hour": 8.0, "approval_rate": 0.12, "unknown_vpa_frac": 0.85},
    "V07": {"ring_size": 120, "device_share_factor": 6, "ramp_slope": 1.4, "thin_file_days": 45},
    "V18": {"overspend_ratio": 1.8, "off_allowlist_rate": 0.35, "expiry_margin_s": 900.0},
    "V19": {"cart_delta_pct": 0.14, "payee_sub_rate": 0.12, "hidden_item_count": 1},
    "V20": {"attestation_invalid_frac": 0.55, "spoofed_operator_count": 4},
    "V21": {"nonce_reuse_rate": 0.45, "replay_delay_s": 1800.0},
    "V22": {
        "target_feature": "cnt_pan_token_1h",
        "perturbation_budget": 0.25,
        "threshold_margin": 0.05,
    },
    "V28": {
        "fan_in_degree": 14,
        "hop_count": 3,
        "dwell_minutes": 22.0,
        "amount_ladder": [4800.0, 9600.0, 14400.0],
    },
    "V31": {"non_eea_routing_share": 0.72, "amount_band": [25.0, 380.0]},
}

INJECTOR_MODULE_COUNT: int = 8
INJECTOR_CLASS_COUNT: int = 12

__all__ = [
    "INJECTORS",
    "PARAM_SCHEMAS",
    "RAIL_OF_VECTOR",
    "DEFAULT_PARAMS",
    "INJECTOR_MODULE_COUNT",
    "INJECTOR_CLASS_COUNT",
    "Campaign",
    "Injector",
]
