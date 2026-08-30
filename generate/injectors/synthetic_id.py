"""V07 synthetic identity rings. This is the blind-holdout family: its output is written
only to the blind cohort and never appended to any training pool."""

import numpy as np
import pandas as pd

from generate.injectors.base import (
    Campaign,
    campaign_subgraph,
    finalise,
    hex_token,
    to_inr_array,
)
from generate.population import Population
from runtime.errors import InjectorProducedNothing
from runtime.seeding import seeded_uuid
from runtime.timewindows import TimeWindow

RING_RAIL: str = "CARD_CNP"
RAMP_JITTER: float = 1.25
RING_EVENT_LIMIT: int = 14_000
RAMP_STEPS: int = 8
BASE_RAMP_AMOUNT: float = 900.0
THIN_FILE_MIN_DAYS: int = 7


class SyntheticIdentityRingCampaign:
    vector_id = "V07"
    param_schema = {
        "type": "object",
        "properties": {
            "ring_size": {"type": "integer", "minimum": 5, "maximum": 200},
            "device_share_factor": {"type": "integer", "minimum": 1, "maximum": 20},
            "ramp_slope": {"type": "number", "minimum": 0.1, "maximum": 5.0},
            "thin_file_days": {"type": "integer", "minimum": 7, "maximum": 365},
        },
        "required": ["ring_size", "device_share_factor", "ramp_slope"],
        "additionalProperties": False,
    }

    def inject(
        self, population: Population, params: dict, window: TimeWindow, rng: np.random.Generator
    ) -> Campaign:
        campaign_id = seeded_uuid("V07", int(window.start.timestamp()))
        ring_size = int(params["ring_size"])
        share_factor = max(1, int(params["device_share_factor"]))
        slope = float(params["ramp_slope"])
        thin_file_days = int(params.get("thin_file_days", 45))

        # The ring is built against blind-cohort holders so its output stays inside the
        # holdout partition, per the blind-holdout definition.
        identities = population.sample_cardholders(ring_size, rng, blind=True)
        if identities.empty:
            identities = population.sample_cardholders(ring_size, rng)
        merchants = population.sample_merchants(40, weight_by="inverse_control_strength", rng=rng)
        if identities.empty or merchants.empty:
            raise InjectorProducedNothing("V07 has no ring identities")

        shared_devices = [
            population.new_attacker_device(rng) for _ in range(max(1, ring_size // share_factor))
        ]

        rows: list[dict] = []
        index = 0
        span_days = max(window.duration_seconds() / 86400.0, 1.0)
        for position in range(len(identities)):
            identity = identities.iloc[position]
            device = shared_devices[position % len(shared_devices)]
            dormancy = min(thin_file_days, span_days * 0.4)
            start = pd.Timestamp(window.start) + pd.Timedelta(days=dormancy)
            amount = BASE_RAMP_AMOUNT
            for step in range(RAMP_STEPS):
                timestamp = start + pd.Timedelta(days=float(step) * span_days / (RAMP_STEPS * 2))
                if timestamp >= pd.Timestamp(window.end) or len(rows) >= RING_EVENT_LIMIT:
                    break
                merchant = merchants.iloc[(position + step) % len(merchants)]
                rows.append(
                    {
                        "event_id": str(seeded_uuid(f"V07:{campaign_id}", index)),
                        "event_ts": timestamp,
                        "rail": RING_RAIL,
                        "amount": round(
                            amount * float(rng.uniform(1.0 / RAMP_JITTER, RAMP_JITTER)), 2
                        ),
                        "currency": str(identity["currency"]),
                        "amount_inr": round(amount, 2),
                        "payer_entity_id": str(identity["entity_id"]),
                        "payee_entity_id": str(merchant["entity_id"]),
                        "payer_country": str(identity["home_country"]),
                        "payee_country": str(merchant["home_country"]),
                        "cross_border": str(identity["home_country"])
                        != str(merchant["home_country"]),
                        "payer_kyc_level": "MIN",
                        "payer_balance_band": "LOW",
                        "pan_token": str(identity["pan_token"]),
                        "bin": str(identity["bin"]),
                        "issuer_id": str(identity["issuer_id"]),
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
                        "merchant_country": str(merchant["home_country"]),
                        "threeds_version": "2.2.0",
                        "threeds_flow": "frictionless",
                        "card_network": str(identity["card_network"]),
                        "eci": "06" if str(identity["card_network"]) == "VISA" else "01",
                        "eci_semantic": "attempted",
                        "cavv_present": True,
                        "threeds_method_completed": True,
                        "device_fingerprint_id": f"fp_{hex_token(rng, 16)}",
                        "browser_screen_res": "1366x768",
                        "browser_tz_offset": 330,
                        "browser_lang": "en-IN",
                        "device_id": device["device_id"],
                        "device_os": device["device_os"],
                        "device_first_seen_ts": pd.Timestamp(window.start),
                        "ip": device["ip"],
                        "ip_asn": device["ip_asn"],
                        "ip_country": device["ip_country"],
                        "ip_proxy_flag": True,
                        "user_agent_hash": hex_token(rng, 64),
                    }
                )
                amount *= 1.0 + slope * 0.35
                index += 1
        if not rows:
            raise InjectorProducedNothing("V07 produced no ring activity")
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
