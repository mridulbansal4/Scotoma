"""V31 cross-border SCA-gap exploitation."""

import numpy as np
import pandas as pd

from generate.injectors.base import (
    Campaign,
    amount_in_band,
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
        eea = pool[pool["home_country"].isin(["DE", "FR", "GB"])]
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
            acceptance_country = (
                str(rng.choice(NON_EEA_COUNTRIES))
                if route_out[index]
                else str(holder["home_country"])
            )
            rows.append(
                {
                    "event_id": str(seeded_uuid(f"V31:{campaign_id}", index)),
                    "event_ts": timestamps[index],
                    "rail": "CARD_CNP",
                    "amount": float(amounts[index]),
                    "currency": str(holder["currency"]),
                    "amount_inr": float(amounts[index]),
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
                    # Routing outside the mandatory-SCA region is the whole mechanism:
                    # authentication is simply absent on a transaction that would have
                    # required it domestically.
                    "threeds_version": None if route_out[index] else "2.2.0",
                    "threeds_flow": "none" if route_out[index] else "frictionless",
                    "card_network": str(holder["card_network"]),
                    "eci": ("07" if str(holder["card_network"]) == "VISA" else "00")
                    if route_out[index]
                    else ("06" if str(holder["card_network"]) == "VISA" else "01"),
                    "eci_semantic": "not_authenticated" if route_out[index] else "attempted",
                    "cavv_present": not bool(route_out[index]),
                    "threeds_method_completed": not bool(route_out[index]),
                    "device_fingerprint_id": f"fp_{hex_token(rng, 16)}",
                    "browser_screen_res": "1440x900",
                    "browser_tz_offset": 60,
                    "browser_lang": "de-DE",
                    "sca_exempt_reason": "tra" if route_out[index] else None,
                    "device_id": str(holder["primary_device_id"]),
                    "device_os": "WINDOWS",
                    "device_first_seen_ts": pd.Timestamp(window.start),
                    "ip": str(holder["home_ip"]),
                    "ip_asn": "AS64512",
                    "ip_country": acceptance_country,
                    "ip_proxy_flag": bool(route_out[index]),
                    "user_agent_hash": hex_token(rng, 64),
                }
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
