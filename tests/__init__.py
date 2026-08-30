"""Shared fixtures. The suite builds one small world and reuses it across modules.

Overrides are passed as an explicit PayLoopConfig rather than through the environment, so
the single-config-read rule holds inside the tests as well.
"""

from dataclasses import dataclass
from functools import lru_cache

import pandas as pd

from generate.behavior import emit_legitimate, simulation_window
from generate.holdout import partition_blind_cohort
from generate.injectors import DEFAULT_PARAMS, INJECTORS
from generate.population import SIM_START, Population, build_population
from generate.prevalence import enforce_caps
from runtime.config import PayLoopConfig
from runtime.seeding import rng_for
from runtime.timewindows import TimeWindow

FIXTURE_CARDHOLDERS: int = 3_000
FIXTURE_MERCHANTS: int = 400
FIXTURE_EVENTS: int = 160_000


@dataclass(frozen=True)
class World:
    config: PayLoopConfig
    population: Population
    window: TimeWindow
    legit: pd.DataFrame
    blind_legit: pd.DataFrame
    pool: pd.DataFrame
    blind: pd.DataFrame


@lru_cache(maxsize=1)
def fixture_config() -> PayLoopConfig:
    return PayLoopConfig(
        run_id="pytest-fixture",
        n_cardholders=FIXTURE_CARDHOLDERS,
        n_merchants=FIXTURE_MERCHANTS,
        n_devices=FIXTURE_CARDHOLDERS + 500,
        n_ips=900,
        n_accounts=FIXTURE_CARDHOLDERS,
        n_agents=80,
        target_events=FIXTURE_EVENTS,
    )


@lru_cache(maxsize=1)
def fixture_world() -> World:
    from loop.controller import budgeted_campaign

    config = fixture_config()
    population = build_population(config)
    window = simulation_window(config, SIM_START)
    partition = partition_blind_cohort(population, config, window)

    pool_vectors = [v for v in INJECTORS if v not in config.blind_holdout_vector_ids]
    pool_parts = [partition.pool_events]
    for vector_id in pool_vectors:
        campaign = INJECTORS[vector_id]().inject(
            population, dict(DEFAULT_PARAMS[vector_id]), window, rng_for(f"pytest:{vector_id}")
        )
        pool_parts.append(
            budgeted_campaign(
                campaign, partition.pool_events, config, pool_vectors, f"pytest:{vector_id}"
            )
        )

    blind_vectors = list(config.blind_holdout_vector_ids)
    blind_parts = [partition.blind_events]
    for vector_id in blind_vectors:
        campaign = INJECTORS[vector_id]().inject(
            population, dict(DEFAULT_PARAMS[vector_id]), window, rng_for(f"pytest:blind:{vector_id}")
        )
        blind_parts.append(
            budgeted_campaign(
                campaign, partition.blind_events, config, blind_vectors, f"pytest:blind:{vector_id}"
            )
        )

    pool = enforce_caps(
        pd.concat(pool_parts, ignore_index=True).sort_values("event_ts").reset_index(drop=True),
        config,
    )
    blind = enforce_caps(
        pd.concat(blind_parts, ignore_index=True).sort_values("event_ts").reset_index(drop=True),
        config,
    )
    return World(
        config=config,
        population=population,
        window=window,
        legit=partition.pool_events,
        blind_legit=partition.blind_events,
        pool=pool,
        blind=blind,
    )


def campaign_for(vector_id: str, params: dict | None = None) -> pd.DataFrame:
    world = fixture_world()
    campaign = INJECTORS[vector_id]().inject(
        world.population,
        dict(params or DEFAULT_PARAMS[vector_id]),
        world.window,
        rng_for(f"pytest:one:{vector_id}"),
    )
    return campaign.events


def emit_reference(purpose: str = "pytest:reference") -> pd.DataFrame:
    world = fixture_world()
    return emit_legitimate(
        world.population, world.window, target_events=FIXTURE_EVENTS // 4, purpose=purpose
    )
