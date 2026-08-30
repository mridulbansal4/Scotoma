"""V07 synthetic identity rings. This is the blind-holdout family: its output is written
only to the blind cohort and never appended to any training pool."""

import numpy as np
import pandas as pd

from backend.generate.injectors.base import (
    CAMPAIGN_APPROVAL_RATE,
    Campaign,
    campaign_response_code,
    campaign_subgraph,
    card_auth_fields,
    finalise,
    hex_token,
    to_inr_array,
)
from backend.generate.population import Population
from backend.runtime.errors import InjectorProducedNothing
from backend.runtime.seeding import seeded_uuid
from backend.runtime.timewindows import TimeWindow

RING_RAIL: str = "CARD_CNP"
RAMP_JITTER: float = 1.25
RING_EVENT_LIMIT: int = 14_000
RAMP_STEPS: int = 8
BASE_RAMP_AMOUNT: float = 900.0
THIN_FILE_MIN_DAYS: int = 7


def _ring_row(
    campaign_id,
    index: int,
    timestamp: pd.Timestamp,
    identity: pd.Series,
    merchant: pd.Series,
    device: dict[str, str],
    device_first_seen: pd.Timestamp,
    amount: float,
    rng: np.random.Generator,
) -> dict:
    """A ramp transaction from one fabricated identity, on a device the ring shares."""
    network = str(identity["card_network"])
    return {
        "event_id": str(seeded_uuid(f"V07:{campaign_id}", index)),
        "event_ts": timestamp,
        "rail": RING_RAIL,
        "amount": round(amount, 2),
        "currency": str(identity["currency"]),
        "amount_inr": round(amount, 2),
        "payer_entity_id": str(identity["entity_id"]),
        "payee_entity_id": str(merchant["entity_id"]),
        "payer_country": str(identity["home_country"]),
        "payee_country": str(merchant["home_country"]),
        "cross_border": str(identity["home_country"]) != str(merchant["home_country"]),
        "payer_kyc_level": str(identity["kyc_level"]),
        "payer_balance_band": str(identity["balance_band"]),
        "pan_token": str(identity["pan_token"]),
        "bin": str(identity["bin"]),
        "issuer_id": str(identity["issuer_id"]),
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
        "device_fingerprint_id": f"fp_{hex_token(rng, 16)}",
        "device_id": device["device_id"],
        "device_os": device["device_os"],
        "device_first_seen_ts": device_first_seen,
        "ip": device["ip"],
        "ip_asn": device["ip_asn"],
        "ip_country": device["ip_country"],
        "ip_proxy_flag": bool(device.get("ip_proxy_flag", False)),
        "user_agent_hash": hex_token(rng, 64),
    }


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

        devices = [
            population.new_attacker_device(rng) for _ in range(max(1, ring_size // share_factor))
        ]
        first_seen = pd.Series(
            population.devices["created_ts"].to_numpy(),
            index=population.devices["entity_id"].to_numpy(),
        )
        rows = self._ramp(
            identities, merchants, devices, first_seen, params, window, slope, thin_file_days, rng
        )
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

    def _ramp(
        self,
        identities: pd.DataFrame,
        merchants: pd.DataFrame,
        devices: list[dict[str, str]],
        device_first_seen: pd.Series,
        params: dict,
        window: TimeWindow,
        slope: float,
        thin_file_days: int,
        rng: np.random.Generator,
    ) -> list[dict]:
        """Dormancy, then an accelerating spend curve on a shared device."""
        campaign_id = seeded_uuid("V07", int(window.start.timestamp()))
        span_days = max(window.duration_seconds() / 86400.0, 1.0)
        rows: list[dict] = []
        index = 0
        for position in range(len(identities)):
            identity = identities.iloc[position]
            device = devices[position % len(devices)]
            start = pd.Timestamp(window.start) + pd.Timedelta(
                days=min(thin_file_days, span_days * 0.4)
            )
            amount = BASE_RAMP_AMOUNT
            for step in range(RAMP_STEPS):
                timestamp = start + pd.Timedelta(days=float(step) * span_days / (RAMP_STEPS * 2))
                if timestamp >= pd.Timestamp(window.end) or len(rows) >= RING_EVENT_LIMIT:
                    break
                merchant = merchants.iloc[(position + step) % len(merchants)]
                jitter = float(rng.uniform(1.0 / RAMP_JITTER, RAMP_JITTER))
                rows.append(
                    _ring_row(
                        campaign_id,
                        index,
                        timestamp,
                        identity,
                        merchant,
                        device,
                        device_first_seen.get(device["device_id"], timestamp),
                        amount * jitter,
                        rng,
                    )
                )
                amount *= 1.0 + slope * 0.35
                index += 1
        return rows
