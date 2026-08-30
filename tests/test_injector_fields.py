"""No injector may label its output by pinning or omitting a field.

A campaign that holds a column constant while legitimate traffic varies it, or leaves a
column empty that every legitimate row on the same rail fills, hands the detector a
separator that has nothing to do with the typology. The model then scores the campaign
perfectly and generalises to nothing -- which is exactly what the blind holdout exists to
expose, and exactly what makes the number it reports worthless.

Fields that are constant *because that is the mechanism* are listed in MECHANISM_CONSTANTS
with the reason. Anything else constant or absent is a defect.
"""

import numpy as np
import pytest

from backend.generate.behavior import emit_legitimate, simulation_window
from backend.generate.injectors import DEFAULT_PARAMS, INJECTORS, RAIL_OF_VECTOR
from backend.generate.population import SIM_START, build_population
from backend.runtime.config import PayLoopConfig
from backend.runtime.seeding import rng_for

# Identifiers, hashes, amounts and per-event tokens are unique by construction, so a
# constancy test on them measures nothing.
IDENTITY_COLUMNS: frozenset[str] = frozenset(
    {
        "event_id",
        "event_ts",
        "is_fraud",
        "vector_id",
        "campaign_id",
        "red_team_round",
        "mutation_lineage",
        "label_available_ts",
        "amount",
        "amount_inr",
        "payer_entity_id",
        "payee_entity_id",
        "pan_token",
        "uetr",
        "mandate_id",
        "intent_mandate_id",
        "cart_mandate_id",
        "payment_mandate_id",
        "mandate_nonce",
        "cart_hash_at_intent",
        "cart_hash_at_settle",
        "remittance_ref",
        "mandate_merchant_allowlist",
        "settlement_ts",
        "mandate_expiry_ts",
        "beneficiary_first_seen_ts",
        "device_fingerprint_id",
        "user_agent_hash",
        "payer_name_hash",
        "terminal_id",
        "merchant_id",
        "device_id",
        "ip",
        "vpa_payer",
        "vpa_payee",
        "agent_id",
        "device_binding_id",
    }
)

MECHANISM_CONSTANTS: dict[str, dict[str, str]] = {
    "V01": {"bin": "enumeration walks one issuer range; a varying BIN is a different vector"},
}

REFERENCE_VARIETY: int = 2


@pytest.fixture(scope="module")
def sample():
    config = PayLoopConfig(
        n_cardholders=2500,
        n_merchants=300,
        n_devices=3000,
        n_ips=700,
        n_accounts=2500,
        n_agents=80,
        target_events=60_000,
    )
    population = build_population(config)
    window = simulation_window(config, SIM_START)
    return population, window, emit_legitimate(population, window)


@pytest.mark.parametrize("vector_id", sorted(INJECTORS))
def test_injector_matches_the_shape_of_legitimate_traffic(vector_id, sample):
    population, window, legitimate = sample
    reference = legitimate[legitimate["rail"] == RAIL_OF_VECTOR[vector_id]]
    campaign = (
        INJECTORS[vector_id]()
        .inject(population, dict(DEFAULT_PARAMS[vector_id]), window, rng_for(f"fields:{vector_id}"))
        .events
    )
    allowed = MECHANISM_CONSTANTS.get(vector_id, {})

    defects: list[str] = []
    for column in campaign.columns:
        if column in IDENTITY_COLUMNS or column in allowed:
            continue
        campaign_values = campaign[column].dropna()
        reference_values = reference[column].dropna()
        if len(reference_values) == 0 or reference_values.nunique() <= REFERENCE_VARIETY:
            continue
        if len(campaign_values) == 0:
            defects.append(f"{column} absent (legitimate rows on this rail all fill it)")
        elif campaign_values.nunique() == 1:
            defects.append(f"{column} pinned to {campaign_values.iloc[0]!r}")

    assert not defects, (
        f"{vector_id} is separable on fields unrelated to its mechanism: "
        + "; ".join(defects)
        + ". Draw them from the population, or record the reason in MECHANISM_CONSTANTS."
    )


def test_mechanism_constants_are_documented():
    for vector_id, columns in MECHANISM_CONSTANTS.items():
        assert vector_id in INJECTORS
        for column, reason in columns.items():
            assert (
                isinstance(column, str) and len(reason) > 20
            ), f"{vector_id}.{column} needs a reason, not a waiver"


def test_attacker_devices_are_drawn_from_the_population(sample):
    """Attacker hardware must be indistinguishable from anyone else's by identity alone."""
    population, _, _ = sample
    rng = np.random.default_rng(7)
    drawn = [population.new_attacker_device(rng) for _ in range(200)]
    known = set(population.devices["entity_id"].astype(str))
    assert all(device["device_id"] in known for device in drawn)
    assert len({device["device_os"] for device in drawn}) > 1
    assert len({device["ip_country"] for device in drawn}) > 1
