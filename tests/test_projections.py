"""Scope masks null the right columns and restrict the right rows."""

import pandas as pd

from defend.features import compute_features
from defend.scopes import SCOPES, party_id_for
from schema.projections import SCOPE_NULLED_COLUMNS, masked_columns, project_event, project_frame
from tests import fixture_world


def _scoped_features(scope: str) -> pd.DataFrame:
    world = fixture_world()
    features = compute_features(world.pool.head(4_000))
    carried = world.pool.head(4_000)[
        ["issuer_id", "acquirer_id", "payer_kyc_level", "payer_balance_band"]
    ]
    return project_frame(
        pd.concat([features, carried.reset_index(drop=True)], axis=1),
        scope,
        party_id=party_id_for(scope, world.config),
    )


def test_issuer_scope_restricts_rows() -> None:
    world = fixture_world()
    party = world.config.party_issuer_id
    scoped = project_frame(world.pool, "ISSUER", party_id=party)
    assert not scoped.empty
    assert (scoped["issuer_id"] == party).all()


def test_acquirer_scope_nulls_cardholder_history() -> None:
    scoped = _scoped_features("ACQUIRER")
    for column in SCOPE_NULLED_COLUMNS["ACQUIRER"]:
        if column in scoped.columns:
            assert scoped[column].isna().all(), column


def test_network_scope_keeps_all_rows() -> None:
    world = fixture_world()
    scoped = project_frame(world.pool, "NETWORK")
    assert len(scoped) == len(world.pool)


def test_projection_does_not_mutate_input() -> None:
    world = fixture_world()
    before = world.pool["payer_kyc_level"].copy()
    project_frame(world.pool, "NETWORK")
    pd.testing.assert_series_equal(before, world.pool["payer_kyc_level"])


def test_every_scope_declares_a_mask() -> None:
    for scope in SCOPES:
        assert masked_columns(scope)


def test_project_event_matches_the_frame_mask() -> None:
    event = {column: 1.0 for column in SCOPE_NULLED_COLUMNS["NETWORK"]}
    event["amount"] = 10.0
    projected = project_event(event, "NETWORK")
    assert projected["amount"] == 10.0
    assert all(projected[column] is None for column in SCOPE_NULLED_COLUMNS["NETWORK"])
