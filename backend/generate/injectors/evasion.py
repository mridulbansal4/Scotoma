"""V22 adversarial evasion of the fraud scorer."""

import numpy as np
import pandas as pd

from backend.defend.features import FEATURE_NAMES
from backend.generate.injectors.base import (
    CAMPAIGN_APPROVAL_RATE,
    Campaign,
    campaign_response_code,
    campaign_subgraph,
    card_auth_fields,
    finalise,
    holder_device_fields,
    spread_timestamps,
    to_inr_array,
)
from backend.generate.population import MCC_UNIVERSE, Population
from backend.runtime.errors import InjectorProducedNothing
from backend.runtime.seeding import seeded_uuid
from backend.runtime.timewindows import TimeWindow

EVASION_EVENT_COUNT: int = 2_000
# Amounts sit inside the holder's own spend band, scaled only by the perturbation budget,
# because the vector is defined by staying feasible rather than by being extreme.
BASE_EVASION_MULTIPLIER: float = 1.15
LOW_VALUE_EXEMPTION_BUDGET: float = 0.2
CONTROLLABLE_FEATURES: tuple[str, ...] = tuple(
    name
    for name in FEATURE_NAMES
    if name.startswith(("cnt_", "sum_", "declrate_", "amtstd_"))
    or name in {"amount_z_vs_entity_history", "cross_border", "sca_exempt_flag"}
)


def _evasion_row(
    campaign_id,
    index: int,
    timestamp: pd.Timestamp,
    holder: pd.Series,
    merchant: pd.Series,
    amount: float,
    budget: float,
    population: Population,
    rng: np.random.Generator,
) -> dict:
    """A transaction that stays inside every band the holder normally occupies."""
    network = str(holder["card_network"])
    return {
        "event_id": str(seeded_uuid(f"V22:{campaign_id}", index)),
        "event_ts": timestamp,
        "rail": "CARD_CNP",
        "amount": round(amount, 2),
        "currency": str(holder["currency"]),
        "amount_inr": round(amount, 2),
        "payer_entity_id": str(holder["entity_id"]),
        "payee_entity_id": str(merchant["entity_id"]),
        "payer_country": str(holder["home_country"]),
        "payee_country": str(merchant["home_country"]),
        "cross_border": str(holder["home_country"]) != str(merchant["home_country"]),
        "payer_kyc_level": str(holder["kyc_level"]),
        "payer_balance_band": str(holder["balance_band"]),
        "pan_token": str(holder["pan_token"]),
        "bin": str(holder["bin"]),
        "issuer_id": str(holder["issuer_id"]),
        "acquirer_id": str(merchant["acquirer_id"]),
        "merchant_id": str(merchant["entity_id"]),
        "mcc": str(merchant["mcc"]),
        "pos_entry_mode": "812",
        "processing_code": "000000",
        "mti": "0100",
        "response_code": campaign_response_code(rng, "GLOBAL", CAMPAIGN_APPROVAL_RATE),
        "terminal_id": str(merchant["terminal_id"]),
        "merchant_country": str(merchant["home_country"]),
        **card_auth_fields(network, rng),
        "device_fingerprint_id": str(holder["device_fingerprint_id"]),
        # Staying under the low-value exemption ceiling is how the vector avoids a
        # challenge; above it the campaign claims exemptions no differently from anyone.
        **({"sca_exempt_reason": "low_value"} if budget < LOW_VALUE_EXEMPTION_BUDGET else {}),
        **holder_device_fields(population, holder, rng),
    }


class ScorerEvasionCampaign:
    vector_id = "V22"
    param_schema = {
        "type": "object",
        "properties": {
            "target_feature": {"type": "string", "enum": list(CONTROLLABLE_FEATURES)},
            "perturbation_budget": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "threshold_margin": {"type": "number", "minimum": 0.0, "maximum": 0.2},
        },
        "required": ["target_feature", "perturbation_budget"],
        "additionalProperties": False,
    }

    def inject(
        self, population: Population, params: dict, window: TimeWindow, rng: np.random.Generator
    ) -> Campaign:
        campaign_id = seeded_uuid("V22", int(window.start.timestamp()))
        holders = population.sample_cardholders(min(600, population.n_cardholders), rng)
        merchants = population.sample_merchants(200, weight_by="popularity", rng=rng)
        if holders.empty or merchants.empty:
            raise InjectorProducedNothing("V22 has no holders or merchants")

        budget = float(params["perturbation_budget"])
        margin = float(params.get("threshold_margin", 0.05))
        target = str(params["target_feature"])
        timestamps = spread_timestamps(window, EVASION_EVENT_COUNT, rng)
        holder_pick = rng.integers(0, len(holders), size=EVASION_EVENT_COUNT)
        mcc_lookup = {mcc: position for position, mcc in enumerate(MCC_UNIVERSE)}

        rows = []
        for index in range(EVASION_EVENT_COUNT):
            holder = holders.iloc[int(holder_pick[index])]
            merchant = merchants.iloc[index % len(merchants)]
            amount = self._amount(
                population, holder, merchant, mcc_lookup, budget, margin, target, rng
            )
            rows.append(
                _evasion_row(
                    campaign_id,
                    index,
                    timestamps[index],
                    holder,
                    merchant,
                    amount,
                    budget,
                    population,
                    rng,
                )
            )

        events = finalise(rows, self.vector_id, campaign_id, params.get("_lineage", []))
        events["amount_inr"] = to_inr_array(
            events["amount"].to_numpy("float64"), events["currency"].to_numpy()
        )
        return Campaign(
            campaign_id,
            self.vector_id,
            params,
            events,
            campaign_subgraph(events),
            params.get("_rationale", ""),
        )

    def _amount(
        self,
        population: Population,
        holder: pd.Series,
        merchant: pd.Series,
        mcc_lookup: dict[str, int],
        budget: float,
        margin: float,
        target: str,
        rng: np.random.Generator,
    ) -> float:
        """Stay inside the holder's own band, then step only as far as the budget allows."""
        holder_index = int(str(holder["entity_id"]).split("_")[1])
        mcc_position = mcc_lookup[str(merchant["mcc"])]
        mu = float(population.amount_mu[holder_index, mcc_position])
        sigma = float(population.amount_sigma[holder_index, mcc_position])
        if target == "amount_z_vs_entity_history":
            return float(np.exp(mu)) * (1.0 + margin)
        return float(np.exp(mu + sigma * rng.normal(0.0, 0.5))) * (BASE_EVASION_MULTIPLIER + budget)
