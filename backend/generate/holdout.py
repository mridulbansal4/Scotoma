"""Blind cohort construction and the disjointness assertions that guard it.

The holdout is one attack family and one entity cohort, neither of which enters any
training pool. It is not an independently generated holdout, and the README says so.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from backend.generate.behavior import emit_legitimate
from backend.generate.population import Population
from backend.runtime.config import PayLoopConfig
from backend.runtime.errors import BlindHoldoutLeak
from backend.runtime.timewindows import TimeWindow

BLIND_HOLDOUT_ENTITY_FRAC: float = 0.10
BLIND_COHORT_TRAFFIC_SHARE: float = 0.10


@dataclass(frozen=True)
class BlindPartition:
    cohort_entity_ids: frozenset[str]
    pool_entity_ids: frozenset[str]
    blind_events: pd.DataFrame
    pool_events: pd.DataFrame


def cohort_mask(population: Population) -> np.ndarray:
    return population.cardholders["in_blind_cohort"].to_numpy(dtype=bool)


def cohort_entity_ids(population: Population) -> frozenset[str]:
    """Cohort cardholders plus every device, IP and account bound exclusively to them."""
    holders = population.cardholders
    mask = cohort_mask(population)
    ids = set(holders.loc[mask, "entity_id"].astype(str))

    cohort_devices = set(holders.loc[mask, "primary_device_id"].astype(str)) | set(
        holders.loc[mask, "secondary_device_id"].astype(str)
    )
    shared_devices = set(holders.loc[~mask, "primary_device_id"].astype(str)) | set(
        holders.loc[~mask, "secondary_device_id"].astype(str)
    )
    ids |= cohort_devices - shared_devices

    cohort_ips = set(holders.loc[mask, "home_ip"].astype(str))
    shared_ips = set(holders.loc[~mask, "home_ip"].astype(str))
    ids |= cohort_ips - shared_ips
    return frozenset(ids)


def partition_blind_cohort(
    population: Population, config: PayLoopConfig, window: TimeWindow
) -> BlindPartition:
    mask = cohort_mask(population)
    pool_events = emit_legitimate(
        population,
        window,
        target_events=int(config.target_events * (1.0 - BLIND_COHORT_TRAFFIC_SHARE)),
        holder_mask=~mask,
        purpose="behavior:arrivals",
    )
    blind_events = emit_legitimate(
        population,
        window,
        target_events=int(config.target_events * BLIND_COHORT_TRAFFIC_SHARE),
        holder_mask=mask,
        purpose="behavior:arrivals_blind",
    )
    cohort = cohort_entity_ids(population)
    pool = frozenset(population.cardholders.loc[~mask, "entity_id"].astype(str))
    assert_disjoint(blind_events, pool_events)
    return BlindPartition(
        cohort_entity_ids=cohort,
        pool_entity_ids=pool,
        blind_events=blind_events,
        pool_events=pool_events,
    )


def assert_disjoint(blind: pd.DataFrame, pool: pd.DataFrame) -> None:
    """Event-level and entity-level disjointness. A leak invalidates the headline claim,
    so this is fatal rather than logged."""
    if blind.empty or pool.empty:
        return
    shared_events = set(blind["event_id"].astype(str)) & set(pool["event_id"].astype(str))
    if shared_events:
        raise BlindHoldoutLeak(f"{len(shared_events)} event ids appear in both partitions")
    shared_payers = set(blind["payer_entity_id"].astype(str)) & set(
        pool["payer_entity_id"].astype(str)
    )
    if shared_payers:
        raise BlindHoldoutLeak(f"{len(shared_payers)} payer entities appear in both partitions")


def route_holdout_campaigns(
    partition: BlindPartition, campaign_events: pd.DataFrame, holdout_vectors: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split a campaign batch into the part that joins the pool and the part that is
    routed into the blind cohort file instead."""
    if campaign_events.empty:
        return campaign_events, campaign_events
    to_blind = campaign_events["vector_id"].isin(holdout_vectors)
    return campaign_events[~to_blind].reset_index(drop=True), campaign_events[to_blind].reset_index(
        drop=True
    )
