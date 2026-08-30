"""V18 delegated mandate scope breach."""

import numpy as np
import pandas as pd

from backend.generate.injectors.base import (
    Campaign,
    agentic_row,
    campaign_subgraph,
    finalise,
    log_uniform,
    spread_timestamps,
)
from backend.generate.population import Population
from backend.runtime.errors import InjectorProducedNothing
from backend.runtime.seeding import seeded_uuid
from backend.runtime.timewindows import TimeWindow

SCOPE_BREACH_EVENT_COUNT: int = 800


class MandateScopeBreachCampaign:
    vector_id = "V18"
    param_schema = {
        "type": "object",
        "properties": {
            "overspend_ratio": {"type": "number", "minimum": 1.0, "maximum": 5.0},
            "off_allowlist_rate": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "expiry_margin_s": {"type": "number", "minimum": 0, "maximum": 86400},
        },
        "required": ["overspend_ratio", "off_allowlist_rate"],
        "additionalProperties": False,
    }

    def inject(
        self, population: Population, params: dict, window: TimeWindow, rng: np.random.Generator
    ) -> Campaign:
        campaign_id = seeded_uuid("V18", int(window.start.timestamp()))
        payers = population.sample_cardholders(min(300, population.n_cardholders), rng)
        merchants = population.sample_merchants(60, weight_by="popularity", rng=rng)
        agents = population.sample_agents(min(40, len(population.agents)), rng)
        if payers.empty or merchants.empty or agents.empty:
            raise InjectorProducedNothing("V18 has no payers, merchants or agents")

        timestamps = spread_timestamps(window, SCOPE_BREACH_EVENT_COUNT, rng)
        off_list = rng.random(SCOPE_BREACH_EVENT_COUNT) < float(params["off_allowlist_rate"])
        overspend = float(params["overspend_ratio"])
        margin = float(params.get("expiry_margin_s", 0.0))

        rows = []
        for index in range(SCOPE_BREACH_EVENT_COUNT):
            payer = payers.iloc[index % len(payers)]
            merchant = merchants.iloc[index % len(merchants)]
            agent = agents.iloc[index % len(agents)]
            ceiling = float(log_uniform(60.0, 400.0, rng))
            row = agentic_row(
                f"V18:{campaign_id}",
                index,
                timestamps[index],
                payer,
                str(merchant["entity_id"]),
                str(merchant["home_country"]),
                ceiling * overspend,
                agent,
                rng,
                currency=str(payer["currency"]),
                population=population,
            )
            row.pop("_line_items")
            row["mandate_amount_max"] = round(ceiling, 2)
            # A positive margin means the mandate had already expired by this many seconds
            # when the payment settled; the validator rejects negative margins outright.
            row["mandate_expiry_ts"] = timestamps[index] - pd.Timedelta(seconds=margin)
            if off_list[index]:
                allowed = merchants.iloc[(index + 3) % len(merchants)]
                row["mandate_merchant_allowlist"] = [str(allowed["entity_id"])]
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
