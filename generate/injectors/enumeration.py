"""V01 PAN/CVV enumeration and V02 BIN attack."""

import numpy as np
import pandas as pd

from generate.injectors.base import (
    LIVE_PAN_HIT_RATE,
    Campaign,
    amount_in_band,
    cadence_timestamps,
    campaign_subgraph,
    finalise,
    hex_token,
    log_uniform,
    spread_timestamps,
    synth_pan,
    to_inr_array,
)
from generate.population import Population
from runtime.errors import InjectorProducedNothing
from runtime.seeding import seeded_uuid
from runtime.timewindows import TimeWindow

PROBE_EVENT_LIMIT: int = 6_000
BIN_ATTACK_EVENT_LIMIT: int = 8_000
VALIDATION_AMOUNT_JITTER: float = 2.5
# Card testing is distributed: a single device probing thousands of PANs is caught by a
# velocity rule on the first afternoon, which is why the observed behaviour spreads the
# work across a fleet and stays under the per-device limits.
ATTACKER_DEVICE_POOL: int = 48
# Not every non-hit returns invalid-card. Issuers answer a probe against a PAN that exists
# but fails another check with the ordinary decline codes, and that mixture is what makes
# the signal statistical rather than a lookup.
ENUMERATION_DECLINE_MIX: tuple[tuple[str, float], ...] = (
    ("14", 0.62),
    ("05", 0.18),
    ("51", 0.11),
    ("82", 0.06),
    ("54", 0.03),
)


def _probe_rows(
    timestamps: pd.DatetimeIndex,
    merchants: pd.DataFrame,
    devices: list[dict[str, str]],
    bin_prefix: str,
    amounts: np.ndarray,
    hits: np.ndarray,
    pans: list[str],
    payers: pd.DataFrame,
    rng: np.random.Generator,
) -> list[dict]:
    size = len(timestamps)
    merchant_pick = rng.integers(0, len(merchants), size=size)
    merchant_ids = merchants["entity_id"].to_numpy()[merchant_pick]
    device_pick = rng.integers(0, len(devices), size=size)
    codes = [code for code, _ in ENUMERATION_DECLINE_MIX]
    weights = [weight for _, weight in ENUMERATION_DECLINE_MIX]
    declines = rng.choice(codes, size=size, p=weights)
    rows = []
    for position in range(size):
        merchant = merchant_pick[position]
        device = devices[int(device_pick[position])]
        payer = payers.iloc[position % len(payers)]
        rows.append(
            {
                "event_id": str(seeded_uuid(f"{bin_prefix}:{device['device_id']}:probe", position)),
                "event_ts": timestamps[position],
                "rail": "CARD_CNP",
                "amount": float(amounts[position]),
                "currency": str(payer["currency"]),
                "amount_inr": float(amounts[position]),
                "payer_entity_id": str(payer["entity_id"]),
                "payee_entity_id": str(merchant_ids[position]),
                "payer_country": str(payer["home_country"]),
                "payee_country": str(merchants["home_country"].to_numpy()[merchant]),
                "cross_border": str(payer["home_country"])
                != str(merchants["home_country"].to_numpy()[merchant]),
                "payer_kyc_level": "NONE",
                "payer_balance_band": "LOW",
                "pan_token": f"tok_{pans[position][-16:]}",
                "bin": bin_prefix,
                "issuer_id": f"ISS_{int(rng.integers(0, 40)):03d}",
                "acquirer_id": str(merchants["acquirer_id"].to_numpy()[merchant]),
                "merchant_id": str(merchant_ids[position]),
                "mcc": str(merchants["mcc"].to_numpy()[merchant]),
                "pos_entry_mode": "812",
                "processing_code": "000000",
                "mti": "0100",
                "response_code": "00" if hits[position] else str(declines[position]),
                "avs_result": "N",
                "cvv_result": "M" if hits[position] else "N",
                "terminal_id": str(merchants["terminal_id"].to_numpy()[merchant]),
                "merchant_country": str(merchants["home_country"].to_numpy()[merchant]),
                "threeds_version": "2.2.0",
                "threeds_flow": "none",
                "card_network": "VISA",
                "eci": "07",
                "eci_semantic": "not_authenticated",
                "cavv_present": False,
                "threeds_method_completed": False,
                "device_fingerprint_id": f"fp_{hex_token(rng, 16)}",
                "browser_screen_res": "1920x1080",
                "browser_tz_offset": 0,
                "browser_lang": "en-US",
                "device_id": device["device_id"],
                "device_os": device["device_os"],
                "device_first_seen_ts": timestamps[0],
                "ip": device["ip"],
                "ip_asn": device["ip_asn"],
                "ip_country": device["ip_country"],
                "ip_proxy_flag": True,
                "user_agent_hash": hex_token(rng, 64),
            }
        )
    return rows


class EnumerationCampaign:
    vector_id = "V01"
    param_schema = {
        "type": "object",
        "properties": {
            "probes_per_min": {"type": "number", "minimum": 0.5, "maximum": 240},
            "n_merchants": {"type": "integer", "minimum": 1, "maximum": 400},
            "amount_band": {
                "type": "array",
                "items": {"type": "number"},
                "minItems": 2,
                "maxItems": 2,
            },
            "bin_stride": {"type": "integer", "minimum": 1, "maximum": 64},
            "dwell_s": {"type": "number", "minimum": 0, "maximum": 3600},
        },
        "required": ["probes_per_min", "n_merchants", "amount_band"],
        "additionalProperties": False,
    }

    def inject(
        self, population: Population, params: dict, window: TimeWindow, rng: np.random.Generator
    ) -> Campaign:
        campaign_id = seeded_uuid("V01", int(window.start.timestamp()))
        devices = [population.new_attacker_device(rng) for _ in range(ATTACKER_DEVICE_POOL)]
        bin_prefix = population.sample_weak_bin(rng)
        merchants = population.sample_merchants(
            params["n_merchants"], weight_by="inverse_control_strength", rng=rng
        )
        timestamps = cadence_timestamps(
            window, params["probes_per_min"], params.get("dwell_s", 0.0), PROBE_EVENT_LIMIT, rng
        )
        if len(timestamps) == 0:
            raise InjectorProducedNothing("V01 produced no probes in this window")

        stride = int(params.get("bin_stride", 1))
        pans = [synth_pan(bin_prefix, stride, index, rng) for index in range(len(timestamps))]
        amounts = amount_in_band(params["amount_band"], len(timestamps), rng, "CARD_CNP")
        hits = rng.random(len(timestamps)) < LIVE_PAN_HIT_RATE
        payers = population.sample_cardholders(min(24, population.n_cardholders), rng)

        rows = _probe_rows(
            timestamps, merchants, devices, bin_prefix, amounts, hits, pans, payers, rng
        )
        events = finalise(rows, self.vector_id, campaign_id, params.get("_lineage", []))
        events["amount_inr"] = to_inr_array(
            events["amount"].to_numpy("float64"), events["currency"].to_numpy()
        )
        return Campaign(
            campaign_id=campaign_id,
            vector_id=self.vector_id,
            params=params,
            events=events,
            subgraph=campaign_subgraph(events),
            rationale=params.get("_rationale", ""),
        )


class BinAttackCampaign:
    vector_id = "V02"
    param_schema = {
        "type": "object",
        "properties": {
            "bin_prefix_count": {"type": "integer", "minimum": 1, "maximum": 8},
            "pans_per_bin": {"type": "integer", "minimum": 10, "maximum": 5000},
            "validation_amount": {"type": "number", "minimum": 0.5, "maximum": 3.0},
        },
        "required": ["bin_prefix_count", "pans_per_bin"],
        "additionalProperties": False,
    }

    def inject(
        self, population: Population, params: dict, window: TimeWindow, rng: np.random.Generator
    ) -> Campaign:
        campaign_id = seeded_uuid("V02", int(window.start.timestamp()))
        devices = [population.new_attacker_device(rng) for _ in range(ATTACKER_DEVICE_POOL)]
        merchants = population.sample_merchants(24, weight_by="inverse_control_strength", rng=rng)
        payers = population.sample_cardholders(min(12, population.n_cardholders), rng)
        amount = float(params.get("validation_amount", 1.0))

        rows: list[dict] = []
        for _ in range(int(params["bin_prefix_count"])):
            bin_prefix = population.sample_weak_bin(rng)
            count = min(int(params["pans_per_bin"]), BIN_ATTACK_EVENT_LIMIT - len(rows))
            if count <= 0:
                break
            timestamps = spread_timestamps(window, count, rng)
            pans = [synth_pan(bin_prefix, 1, index, rng) for index in range(count)]
            # A single fixed validation amount is a Benford failure on its own, so the
            # probe amount is jittered around the requested value.
            amounts = log_uniform(
                amount / VALIDATION_AMOUNT_JITTER, amount * VALIDATION_AMOUNT_JITTER, rng, count
            )
            hits = rng.random(count) < LIVE_PAN_HIT_RATE
            rows.extend(
                _probe_rows(
                    timestamps, merchants, devices, bin_prefix, amounts, hits, pans, payers, rng
                )
            )
        if not rows:
            raise InjectorProducedNothing("V02 produced no validation attempts")
        events = finalise(rows, self.vector_id, campaign_id, params.get("_lineage", []))
        events["amount_inr"] = to_inr_array(
            events["amount"].to_numpy("float64"), events["currency"].to_numpy()
        )
        return Campaign(
            campaign_id=campaign_id,
            vector_id=self.vector_id,
            params=params,
            events=events,
            subgraph=campaign_subgraph(events),
            rationale=params.get("_rationale", ""),
        )
