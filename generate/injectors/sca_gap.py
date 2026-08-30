"""V31 cross-border SCA-gap exploitation."""

import numpy as np
import pandas as pd

from generate.injectors.base import (
    Campaign,
    amount_in_band,
    browser_profile,
    campaign_subgraph,
    finalise,
    hex_token,
    spread_timestamps,
    to_inr_array,
)
from generate.population import Population
from runtime.errors import InjectorProducedNothing
from runtime.seeding import seeded_uuid
from runtime.timewindows import TimeWindow

SCA_GAP_EVENT_COUNT: int = 2_400
NON_EEA_COUNTRIES: tuple[str, ...] = ("SG", "AE", "US")
EEA_COUNTRIES: tuple[str, ...] = ("DE", "FR", "GB")


def _routed_row(
    campaign_id,
    index: int,
    timestamp: pd.Timestamp,
    holder: pd.Series,
    merchant: pd.Series,
    amount: float,
    acceptance_country: str,
    routed_out: bool,
    rng: np.random.Generator,
) -> dict:
    """One acceptance. Routing outside the mandatory-SCA region is the whole mechanism:
    authentication is simply absent on a transaction that would have required it at home."""
    network = str(holder["card_network"])
    unauthenticated = "07" if network == "VISA" else "00"
    attempted = "06" if network == "VISA" else "01"
    return {
        "event_id": str(seeded_uuid(f"V31:{campaign_id}", index)),
        "event_ts": timestamp,
        "rail": "CARD_CNP",
        "amount": float(amount),
        "currency": str(holder["currency"]),
        "amount_inr": float(amount),
        "payer_entity_id": str(holder["entity_id"]),
        "payee_entity_id": str(merchant["entity_id"]),
        "payer_country": str(holder["home_country"]),
        "payee_country": acceptance_country,
        "cross_border": str(holder["home_country"]) != acceptance_country,
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
        "response_code": "00",
        "avs_result": "U",
        "cvv_result": "M",
        "terminal_id": str(merchant["terminal_id"]),
        "merchant_country": acceptance_country,
        "threeds_version": None if routed_out else "2.2.0",
        "threeds_flow": "none" if routed_out else "frictionless",
        "card_network": network,
        "eci": unauthenticated if routed_out else attempted,
        "eci_semantic": "not_authenticated" if routed_out else "attempted",
        "cavv_present": not routed_out,
        "threeds_method_completed": not routed_out,
        "device_fingerprint_id": f"fp_{hex_token(rng, 16)}",
        **browser_profile(rng),
        "sca_exempt_reason": "tra" if routed_out else None,
        "device_id": str(holder["primary_device_id"]),
        "device_os": "WINDOWS",
        "device_first_seen_ts": timestamp,
        "ip": str(holder["home_ip"]),
        "ip_asn": "AS64512",
        "ip_country": acceptance_country,
        "ip_proxy_flag": routed_out,
        "user_agent_hash": hex_token(rng, 64),
    }


class CrossBorderScaGapCampaign:
    vector_id = "V31"
    param_schema = {
        "type": "object",
        "properties": {
            "non_eea_routing_share": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "amount_band": {
                "type": "array",
                "items": {"type": "number"},
                "minItems": 2,
                "maxItems": 2,
            },
        },
        "required": ["non_eea_routing_share", "amount_band"],
        "additionalProperties": False,
    }

    def inject(
        self, population: Population, params: dict, window: TimeWindow, rng: np.random.Generator
    ) -> Campaign:
        campaign_id = seeded_uuid("V31", int(window.start.timestamp()))
        pool = population.pool_cardholders
        eea = pool[pool["home_country"].isin(EEA_COUNTRIES)]
        holders = eea if not eea.empty else pool
        merchants = population.sample_merchants(120, weight_by="inverse_control_strength", rng=rng)
        if holders.empty or merchants.empty:
            raise InjectorProducedNothing("V31 has no EEA holders or merchants")

        timestamps = spread_timestamps(window, SCA_GAP_EVENT_COUNT, rng)
        amounts = amount_in_band(params["amount_band"], SCA_GAP_EVENT_COUNT, rng, "CARD_CNP")
        route_out = rng.random(SCA_GAP_EVENT_COUNT) < float(params["non_eea_routing_share"])
        holder_pick = rng.integers(0, len(holders), size=SCA_GAP_EVENT_COUNT)

        rows = []
        for index in range(SCA_GAP_EVENT_COUNT):
            holder = holders.iloc[int(holder_pick[index])]
            merchant = merchants.iloc[index % len(merchants)]
            routed_out = bool(route_out[index])
            acceptance = (
                str(rng.choice(NON_EEA_COUNTRIES)) if routed_out else str(holder["home_country"])
            )
            rows.append(
                _routed_row(
                    campaign_id,
                    index,
                    timestamps[index],
                    holder,
                    merchant,
                    float(amounts[index]),
                    acceptance,
                    routed_out,
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
