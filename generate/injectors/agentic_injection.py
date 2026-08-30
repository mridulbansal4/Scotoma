"""V19 prompt injection against agent checkout. The whole vector is one boolean."""

import numpy as np

from generate.injectors.base import (
    Campaign,
    agentic_row,
    campaign_subgraph,
    cart_hash,
    finalise,
    log_uniform,
    spread_timestamps,
)
from generate.population import Population
from runtime.errors import InjectorProducedNothing
from runtime.seeding import seeded_uuid
from runtime.timewindows import TimeWindow

CART_INJECTION_EVENT_COUNT: int = 900
HIDDEN_SKU_SPACE: int = 10_000


class CartInjectionCampaign:
    vector_id = "V19"
    param_schema = {
        "type": "object",
        "properties": {
            "cart_delta_pct": {"type": "number", "minimum": 0.01, "maximum": 0.50},
            "payee_sub_rate": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "hidden_item_count": {"type": "integer", "minimum": 1, "maximum": 5},
        },
        "required": ["cart_delta_pct", "payee_sub_rate"],
        "additionalProperties": False,
    }

    def _mutate_cart(
        self, approved: list[dict], params: dict, rng: np.random.Generator
    ) -> tuple[list[dict], str, str]:
        intent_hash = cart_hash(approved)
        injected = list(approved)
        for _ in range(params.get("hidden_item_count", 1)):
            base = float(sum(item["unit_price"] * item["qty"] for item in approved))
            injected.append(
                {
                    "sku": f"HID-{rng.integers(HIDDEN_SKU_SPACE):05d}",
                    "qty": 1,
                    "unit_price": round(base * params["cart_delta_pct"], 2),
                }
            )
        return injected, intent_hash, cart_hash(injected)

    def inject(
        self, population: Population, params: dict, window: TimeWindow, rng: np.random.Generator
    ) -> Campaign:
        campaign_id = seeded_uuid("V19", int(window.start.timestamp()))
        payers = population.sample_cardholders(min(400, population.n_cardholders), rng)
        merchants = population.sample_merchants(80, weight_by="popularity", rng=rng)
        agents = population.sample_agents(min(60, len(population.agents)), rng)
        if payers.empty or merchants.empty or agents.empty:
            raise InjectorProducedNothing("V19 has no payers, merchants or agents")

        timestamps = spread_timestamps(window, CART_INJECTION_EVENT_COUNT, rng)
        substitute = rng.random(CART_INJECTION_EVENT_COUNT) < float(params["payee_sub_rate"])
        rows = []
        for index in range(CART_INJECTION_EVENT_COUNT):
            payer = payers.iloc[index % len(payers)]
            merchant = merchants.iloc[index % len(merchants)]
            agent = agents.iloc[index % len(agents)]
            amount = float(log_uniform(40.0, 600.0, rng))
            row = agentic_row(
                f"V19:{campaign_id}",
                index,
                timestamps[index],
                payer,

                str(merchant["entity_id"]),

                str(merchant["home_country"]),
                amount,
                agent,
                rng,
                currency=str(payer["currency"]),
            )
            injected, intent_hash, settle_hash = self._mutate_cart(
                row.pop("_line_items"), params, rng
            )
            row["cart_hash_at_intent"] = intent_hash
            row["cart_hash_at_settle"] = settle_hash
            if substitute[index]:
                alternate = merchants.iloc[(index + 1) % len(merchants)]
                row["payee_at_settle"] = str(alternate["entity_id"])
            # Attestation, signature, mandate ceiling, allowlist and payee all still pass.
            # Only the cart digest moved, which is exactly the point of the vector.
            row["amount"] = round(
                float(sum(item["unit_price"] * item["qty"] for item in injected)), 2
            )
            row["amount"] = min(row["amount"], float(row["mandate_amount_max"]))
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
