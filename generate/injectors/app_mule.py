"""V05 authorised push payment scam, V06 UPI collect abuse, V28 mule-network orchestration."""

import numpy as np
import pandas as pd

from generate.injectors.base import (
    Campaign,
    campaign_subgraph,
    finalise,
    hex_token,
    log_uniform,
    spread_timestamps,
    to_inr_array,
)
from generate.population import CURRENCY_BY_COUNTRY, Population
from runtime.errors import InjectorProducedNothing
from runtime.seeding import seeded_uuid
from runtime.timewindows import TimeWindow

SCAM_RAIL: str = "UPI"
MULE_RAILS: tuple[str, ...] = ("SEPA_INST", "ACH")
SCAM_CURRENCY: str = "INR"
LADDER_JITTER: float = 1.35
MIN_CYCLE_MINUTES: float = 30.0
DEFAULT_AMOUNT_LADDER: tuple[float, ...] = (4800.0, 9600.0, 14400.0)
NEW_BENEFICIARY_AGE_HOURS: int = 3
MULE_EVENT_LIMIT: int = 20_000
SCAM_EVENT_LIMIT: int = 12_000
COLLECT_EVENT_LIMIT: int = 12_000
ESCALATION_STEPS: int = 4
BASE_SCAM_AMOUNT: float = 8_000.0


def _transfer_row(
    event_key: str,
    index: int,
    timestamp: pd.Timestamp,
    rail: str,
    currency: str,
    amount: float,
    payer_id: str,
    payee_id: str,
    payer_country: str,
    payee_country: str,
    rng: np.random.Generator,
    beneficiary_first_seen: pd.Timestamp | None = None,
    upi_txn_type: str | None = None,
    payee_name_match: bool | None = None,
    kyc_level: str = "FULL",
    balance_band: str = "MID",
) -> dict:
    row = {
        "event_id": str(seeded_uuid(event_key, index)),
        "event_ts": timestamp,
        "rail": rail,
        "amount": round(float(amount), 2),
        "currency": currency,
        "amount_inr": round(float(amount), 2),
        "payer_entity_id": payer_id,
        "payee_entity_id": payee_id,
        "payer_country": payer_country,
        "payee_country": payee_country,
        "cross_border": payer_country != payee_country,
        "payer_kyc_level": kyc_level,
        "payer_balance_band": balance_band,
        "response_code": "00",
    }
    if rail == "UPI":
        row.update(
            {
                "vpa_payer": f"{payer_id.lower().replace('_', '')}@payloop",
                "vpa_payee": f"{payee_id.lower().replace('_', '')}@payloop",
                "upi_txn_type": upi_txn_type or "push",
                "payee_name_match": payee_name_match if payee_name_match is not None else False,
                "beneficiary_first_seen_ts": beneficiary_first_seen,
                "device_binding_id": f"DB_{hex_token(rng, 12)}",
            }
        )
    else:
        row.update(
            {
                "uetr": str(seeded_uuid(f"{event_key}:uetr", index)),
                "debtor_agent_bic": "PAYLDE01XXX",
                "creditor_agent_bic": "PAYLNL02XXX",
                "settlement_ts": timestamp + pd.Timedelta(seconds=10),
                "remittance_ref": "INVOICE-SETTLEMENT",
            }
        )
    return row


class AppScamCampaign:
    vector_id = "V05"
    param_schema = {
        "type": "object",
        "properties": {
            "victim_count": {"type": "integer", "minimum": 5, "maximum": 200},
            "grooming_days": {"type": "number", "minimum": 0, "maximum": 30},
            "first_payment_ratio": {"type": "number", "minimum": 0.1, "maximum": 1.0},
            "escalation_factor": {"type": "number", "minimum": 1.0, "maximum": 3.0},
        },
        "required": ["victim_count", "first_payment_ratio"],
        "additionalProperties": False,
    }

    def inject(
        self, population: Population, params: dict, window: TimeWindow, rng: np.random.Generator
    ) -> Campaign:
        campaign_id = seeded_uuid("V05", int(window.start.timestamp()))
        victims = population.sample_cardholders(int(params["victim_count"]), rng)
        mules = population.sample_accounts(max(4, int(params["victim_count"]) // 5), rng)
        if victims.empty or mules.empty:
            raise InjectorProducedNothing("V05 has no victims or no mule accounts")

        escalation = float(params.get("escalation_factor", 1.6))
        grooming = float(params.get("grooming_days", 7.0))
        rows: list[dict] = []
        index = 0
        for position in range(len(victims)):
            victim = victims.iloc[position]
            mule = mules.iloc[position % len(mules)]
            start = pd.Timestamp(window.start) + pd.Timedelta(
                days=min(grooming, max(0.0, window.duration_seconds() / 86400.0 - 1.0))
                * rng.random()
            )
            amount = BASE_SCAM_AMOUNT * float(params["first_payment_ratio"])
            for step in range(ESCALATION_STEPS):
                timestamp = start + pd.Timedelta(minutes=float(rng.integers(5, 240)) * (step + 1))
                if timestamp >= pd.Timestamp(window.end):
                    break
                rows.append(
                    _transfer_row(
                        f"V05:{campaign_id}",
                        index,
                        timestamp,
                        SCAM_RAIL,
                        SCAM_CURRENCY,
                        amount * float(rng.uniform(0.7, 1.4)),
                        str(victim["entity_id"]),
                        str(mule["entity_id"]),
                        str(victim["home_country"]),
                        str(mule["home_country"]),
                        rng,
                        beneficiary_first_seen=timestamp
                        - pd.Timedelta(hours=NEW_BENEFICIARY_AGE_HOURS),
                        payee_name_match=False,
                        kyc_level=str(victim["kyc_level"]),
                        balance_band=str(victim["balance_band"]),
                    )
                )
                amount *= escalation
                index += 1
                if len(rows) >= SCAM_EVENT_LIMIT:
                    break
        if not rows:
            raise InjectorProducedNothing("V05 produced no transfers")
        events = finalise(rows, self.vector_id, campaign_id, params.get("_lineage", []))
        return Campaign(
            campaign_id,
            self.vector_id,
            params,
            events,
            campaign_subgraph(events),
            params.get("_rationale", ""),
        )


class CollectRequestAbuseCampaign:
    vector_id = "V06"
    param_schema = {
        "type": "object",
        "properties": {
            "collect_rate_per_hour": {"type": "number", "minimum": 1, "maximum": 120},
            "approval_rate": {"type": "number", "minimum": 0.0, "maximum": 0.3},
            "unknown_vpa_frac": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        },
        "required": ["collect_rate_per_hour", "approval_rate"],
        "additionalProperties": False,
    }

    def inject(
        self, population: Population, params: dict, window: TimeWindow, rng: np.random.Generator
    ) -> Campaign:
        campaign_id = seeded_uuid("V06", int(window.start.timestamp()))
        hours = window.duration_seconds() / 3600.0
        count = min(int(params["collect_rate_per_hour"] * hours), COLLECT_EVENT_LIMIT)
        if count <= 0:
            raise InjectorProducedNothing("V06 produced no collect requests")
        victims = population.sample_cardholders(min(count, population.n_cardholders), rng)
        collectors = population.sample_accounts(max(2, count // 40), rng)
        timestamps = spread_timestamps(window, count, rng)
        approved = rng.random(count) < float(params["approval_rate"])
        unknown = rng.random(count) < float(params.get("unknown_vpa_frac", 0.8))

        rows = []
        for position in range(count):
            victim = victims.iloc[position % len(victims)]
            collector = collectors.iloc[position % len(collectors)]
            row = _transfer_row(
                f"V06:{campaign_id}",
                position,
                timestamps[position],
                SCAM_RAIL,
                SCAM_CURRENCY,
                float(log_uniform(200.0, 9000.0, rng)),
                str(victim["entity_id"]),
                str(collector["entity_id"]),
                str(victim["home_country"]),
                str(collector["home_country"]),
                rng,
                beneficiary_first_seen=timestamps[position] - pd.Timedelta(hours=1),
                upi_txn_type="collect",
                payee_name_match=not bool(unknown[position]),
                kyc_level=str(victim["kyc_level"]),
                balance_band=str(victim["balance_band"]),
            )
            row["response_code"] = "00" if approved[position] else "05"
            rows.append(row)
        events = finalise(rows, self.vector_id, campaign_id, params.get("_lineage", []))
        return Campaign(
            campaign_id,
            self.vector_id,
            params,
            events,
            campaign_subgraph(events),
            params.get("_rationale", ""),
        )


class MuleNetworkCampaign:
    vector_id = "V28"
    param_schema = {
        "type": "object",
        "properties": {
            "fan_in_degree": {"type": "integer", "minimum": 3, "maximum": 40},
            "hop_count": {"type": "integer", "minimum": 1, "maximum": 5},
            "dwell_minutes": {"type": "number", "minimum": 1, "maximum": 240},
            "amount_ladder": {
                "type": "array",
                "items": {"type": "number"},
                "minItems": 3,
                "maxItems": 8,
            },
        },
        "required": ["fan_in_degree", "hop_count", "dwell_minutes"],
        "additionalProperties": False,
    }

    def inject(
        self, population: Population, params: dict, window: TimeWindow, rng: np.random.Generator
    ) -> Campaign:
        campaign_id = seeded_uuid("V28", int(window.start.timestamp()))
        fan_in = int(params["fan_in_degree"])
        hops = int(params["hop_count"])
        needed = fan_in * hops + hops + 1
        accounts = population.sample_accounts(min(needed, population.account_count()), rng)
        if len(accounts) < fan_in + 2:
            raise InjectorProducedNothing("V28 has too few accounts for the requested fan-in")

        rows = self._layer(accounts, params, window, fan_in, hops, rng, campaign_id)
        if not rows:
            raise InjectorProducedNothing("V28 produced no layering legs")

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

    def _layer(
        self,
        accounts: pd.DataFrame,
        params: dict,
        window: TimeWindow,
        fan_in: int,
        hops: int,
        rng: np.random.Generator,
        campaign_id,
    ) -> list[dict]:
        """Fan-in onto a collector, then onward within the dwell window.

        The short dwell between receipt and onward transfer is the signature: money that
        sits is not being laundered."""
        dwell = float(params["dwell_minutes"])
        ladder = [float(value) for value in params.get("amount_ladder", DEFAULT_AMOUNT_LADDER)]
        collectors, sources = accounts.iloc[:hops], accounts.iloc[hops:]
        rows: list[dict] = []
        index = 0
        cursor = pd.Timestamp(window.start)
        while cursor < pd.Timestamp(window.end) and len(rows) < MULE_EVENT_LIMIT:
            for hop in range(hops):
                collector = collectors.iloc[hop]
                for leg in range(fan_in):
                    source = sources.iloc[(index + leg) % len(sources)]
                    timestamp = cursor + pd.Timedelta(minutes=float(rng.uniform(0.0, dwell)))
                    if timestamp >= pd.Timestamp(window.end):
                        break
                    jitter = float(rng.uniform(1.0 / LADDER_JITTER, LADDER_JITTER))
                    rows.append(
                        _transfer_row(
                            f"V28:{campaign_id}",
                            index,
                            timestamp,
                            MULE_RAILS[index % len(MULE_RAILS)],
                            CURRENCY_BY_COUNTRY[str(source["home_country"])],
                            ladder[leg % len(ladder)] * jitter,
                            str(source["entity_id"]),
                            str(collector["entity_id"]),
                            str(source["home_country"]),
                            str(collector["home_country"]),
                            rng,
                            kyc_level=str(source["kyc_level"]),
                            balance_band=str(source["balance_band"]),
                        )
                    )
                    index += 1
                if hop + 1 < hops:
                    onward = collectors.iloc[hop + 1]
                    forwarded = sum(ladder[: fan_in % len(ladder) + 1]) * float(
                        rng.uniform(1.0 / LADDER_JITTER, LADDER_JITTER)
                    )
                    rows.append(
                        _transfer_row(
                            f"V28:{campaign_id}",
                            index,
                            cursor + pd.Timedelta(minutes=dwell),
                            MULE_RAILS[index % len(MULE_RAILS)],
                            CURRENCY_BY_COUNTRY[str(collector["home_country"])],
                            forwarded,
                            str(collector["entity_id"]),
                            str(onward["entity_id"]),
                            str(collector["home_country"]),
                            str(onward["home_country"]),
                            rng,
                            kyc_level=str(collector["kyc_level"]),
                            balance_band=str(collector["balance_band"]),
                        )
                    )
                    index += 1
            cursor += pd.Timedelta(minutes=max(dwell * 2.0, MIN_CYCLE_MINUTES))
        return rows
