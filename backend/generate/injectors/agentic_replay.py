"""V20 agent impersonation and V21 mandate replay or forgery."""

import numpy as np
import pandas as pd

from backend.generate.injectors.base import (
    Campaign,
    agentic_row,
    campaign_subgraph,
    finalise,
    hex_token,
    log_uniform,
    spread_timestamps,
)
from backend.generate.population import Population
from backend.runtime.errors import InjectorProducedNothing
from backend.runtime.seeding import seeded_uuid
from backend.runtime.timewindows import TimeWindow

IMPERSONATION_EVENT_COUNT: int = 700
REPLAY_EVENT_COUNT: int = 700
SPOOFED_OPERATOR_PREFIX: str = "unverified-"


def _agentic_context(population: Population, rng: np.random.Generator, payer_count: int):
    payers = population.sample_cardholders(min(payer_count, population.n_cardholders), rng)
    merchants = population.sample_merchants(50, weight_by="popularity", rng=rng)
    agents = population.sample_agents(min(40, len(population.agents)), rng)
    if payers.empty or merchants.empty or agents.empty:
        raise InjectorProducedNothing("agentic injector has no payers, merchants or agents")
    return payers, merchants, agents


class AgentImpersonationCampaign:
    vector_id = "V20"
    param_schema = {
        "type": "object",
        "properties": {
            "attestation_invalid_frac": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "spoofed_operator_count": {"type": "integer", "minimum": 1, "maximum": 20},
        },
        "required": ["attestation_invalid_frac"],
        "additionalProperties": False,
    }

    def inject(
        self, population: Population, params: dict, window: TimeWindow, rng: np.random.Generator
    ) -> Campaign:
        campaign_id = seeded_uuid("V20", int(window.start.timestamp()))
        payers, merchants, agents = _agentic_context(population, rng, 250)
        timestamps = spread_timestamps(window, IMPERSONATION_EVENT_COUNT, rng)
        invalid = rng.random(IMPERSONATION_EVENT_COUNT) < float(params["attestation_invalid_frac"])
        operators = [
            f"{SPOOFED_OPERATOR_PREFIX}{hex_token(rng, 6)}"
            for _ in range(int(params.get("spoofed_operator_count", 3)))
        ]

        rows = []
        for index in range(IMPERSONATION_EVENT_COUNT):
            payer = payers.iloc[index % len(payers)]
            merchant = merchants.iloc[index % len(merchants)]
            agent = agents.iloc[index % len(agents)]
            row = agentic_row(
                f"V20:{campaign_id}",
                index,
                timestamps[index],
                payer,
                str(merchant["entity_id"]),
                str(merchant["home_country"]),
                float(log_uniform(30.0, 900.0, rng)),
                agent,
                rng,
                currency=str(payer["currency"]),
                population=population,
            )
            row.pop("_line_items")
            row["agent_attestation_valid"] = not bool(invalid[index])
            row["agent_operator"] = operators[index % len(operators)]
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


class MandateReplayCampaign:
    vector_id = "V21"
    param_schema = {
        "type": "object",
        "properties": {
            "nonce_reuse_rate": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "replay_delay_s": {"type": "number", "minimum": 1, "maximum": 86400},
        },
        "required": ["nonce_reuse_rate", "replay_delay_s"],
        "additionalProperties": False,
    }

    def inject(
        self, population: Population, params: dict, window: TimeWindow, rng: np.random.Generator
    ) -> Campaign:
        campaign_id = seeded_uuid("V21", int(window.start.timestamp()))
        payers, merchants, agents = _agentic_context(population, rng, 250)
        timestamps = spread_timestamps(window, REPLAY_EVENT_COUNT, rng)
        reuse = rng.random(REPLAY_EVENT_COUNT) < float(params["nonce_reuse_rate"])
        delay = pd.Timedelta(seconds=float(params["replay_delay_s"]))

        rows: list[dict] = []
        previous_nonce: str | None = None
        for index in range(REPLAY_EVENT_COUNT):
            payer = payers.iloc[index % len(payers)]
            merchant = merchants.iloc[index % len(merchants)]
            agent = agents.iloc[index % len(agents)]
            row = agentic_row(
                f"V21:{campaign_id}",
                index,
                timestamps[index],
                payer,
                str(merchant["entity_id"]),
                str(merchant["home_country"]),
                float(log_uniform(25.0, 750.0, rng)),
                agent,
                rng,
                currency=str(payer["currency"]),
                population=population,
            )
            row.pop("_line_items")
            if reuse[index] and previous_nonce is not None:
                # The replayed settlement carries a nonce already spent, which is the
                # server-side ledger check that replay protection is supposed to make.
                row["mandate_nonce"] = previous_nonce
                row["event_ts"] = timestamps[index] + delay
                row["mandate_signature_valid"] = True
            else:
                previous_nonce = row["mandate_nonce"]
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
