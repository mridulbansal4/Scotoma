"""Blind cohort disjointness at event and entity level."""

import pandas as pd
import pytest

from defend.ensemble import Detector
from generate.holdout import assert_disjoint, cohort_entity_ids, cohort_mask
from generate.population import SIM_START
from runtime.errors import BlindHoldoutLeak
from tests import campaign_for, fixture_world


def test_blind_pool_disjoint() -> None:
    world = fixture_world()
    assert set(world.blind["event_id"]).isdisjoint(set(world.pool["event_id"]))
    assert set(world.blind["payer_entity_id"]).isdisjoint(set(world.pool["payer_entity_id"]))


def test_cohort_is_the_configured_fraction() -> None:
    world = fixture_world()
    mask = cohort_mask(world.population)
    realised = float(mask.mean())
    assert realised == pytest.approx(world.config.blind_holdout_entity_frac, abs=0.01)


def test_cohort_carries_its_bound_entities() -> None:
    world = fixture_world()
    ids = cohort_entity_ids(world.population)
    holders = set(world.population.cardholders.loc[cohort_mask(world.population), "entity_id"])
    assert holders <= ids
    assert len(ids) > len(holders)


def test_holdout_family_stays_out_of_the_pool() -> None:
    world = fixture_world()
    held = set(world.config.blind_holdout_vector_ids)
    assert held
    assert set(world.pool["vector_id"].dropna()).isdisjoint(held)
    assert held <= set(world.blind["vector_id"].dropna())


def test_holdout_family_targets_cohort_entities() -> None:
    world = fixture_world()
    ring = campaign_for("V07")
    pool_payers = set(world.pool["payer_entity_id"])
    assert set(ring["payer_entity_id"]).isdisjoint(pool_payers)


def test_leak_is_fatal() -> None:
    world = fixture_world()
    leaked = pd.concat([world.blind, world.pool.head(50)], ignore_index=True)
    with pytest.raises(BlindHoldoutLeak):
        assert_disjoint(leaked, world.pool)


def test_fit_refuses_a_leaked_holdout() -> None:
    world = fixture_world()
    leaked = pd.concat([world.blind, world.pool.head(50)], ignore_index=True)
    with pytest.raises(BlindHoldoutLeak):
        Detector(world.config, sim_start=SIM_START).fit(world.pool, blind=leaked)
