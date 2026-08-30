"""Gate composition, the required ablation, and the failure modes the gate must catch."""

import numpy as np
import pandas as pd
import pytest

from fidelity.ablation import run_ablation
from fidelity.behavioral import STRUCTURAL_FAILURE_MULTIPLE
from fidelity.gate import ROTATED_LAYERS, run_gate
from fidelity.privacy import INSUFFICIENT_DATA, evaluate as privacy_evaluate
from loop.controller import _carrier_entities, _split_reference_and_carrier
from runtime.seeding import rng_for
from tests import fixture_world

CARRIER_MULTIPLIER: float = 24.0
NOISE_SIGMA: float = 0.5
SMALL_BATCH_ROWS: int = 1_000
DUPLICATE_FRACTION: float = 0.05
GEOMETRIC_MEAN_TOLERANCE: float = 0.05


def _partitions():
    world = fixture_world()
    legit = world.pool[~world.pool["is_fraud"]].reset_index(drop=True)
    return world, *_split_reference_and_carrier(legit)


def _clean_batch():
    world, reference, carrier = _partitions()
    fraud = world.pool[world.pool["is_fraud"]].reset_index(drop=True)
    size = min(len(carrier), int(len(fraud) * CARRIER_MULTIPLIER))
    carried = _carrier_entities(carrier, size, rng_for("pytest:carrier"))
    batch = (
        pd.concat([carried, fraud], ignore_index=True).sort_values("event_ts").reset_index(drop=True)
    )
    return world, batch, reference


def test_gate_passes_own_simulator_output() -> None:
    world, batch, reference = _clean_batch()
    gate = run_gate(batch, reference, 0, world.config)
    load_bearing = {"behavioral", "utility", "adversarial", "privacy", "marginal"}
    failed = {name for name, layer in gate.layers.items() if not layer.passed}
    assert failed.isdisjoint(load_bearing), gate.layers


def test_gaussian_copula_ablation_fails_behavioral() -> None:
    """The ablation. Utility transfers; behaviour does not."""
    _, reference, carrier = _partitions()
    result, payload = run_ablation(carrier, reference)
    assert payload["layers"]["utility"]["passed"] is True, payload["layers"]["utility"]
    assert payload["layers"]["behavioral"]["passed"] is False, payload["layers"]["behavioral"]
    assert result.passed is False


def test_noised_data_fails_marginal() -> None:
    world, batch, reference = _clean_batch()
    rng = rng_for("pytest:noise")
    noised = batch.copy()
    noised["amount"] = (
        noised["amount"].to_numpy("float64")
        * (1.0 + rng.normal(0.0, NOISE_SIGMA, size=len(noised))).clip(0.05, None)
    ).round(2)
    gate = run_gate(noised, reference, 1, world.config)
    assert gate.layers["marginal"].passed is False


def test_duplicated_row_fails_privacy() -> None:
    world, _, reference = _partitions()
    rng = rng_for("pytest:duplicates")
    carrier = world.pool[~world.pool["is_fraud"]].reset_index(drop=True)
    copies = reference.iloc[rng.choice(len(reference), size=int(len(reference) * DUPLICATE_FRACTION))]
    batch = pd.concat([carrier.head(len(reference)), copies], ignore_index=True)
    layer = privacy_evaluate(batch, reference, world.config)
    assert layer.metrics["min_dcr"] == pytest.approx(0.0, abs=1e-12)
    assert layer.passed is False


def test_small_batch_reports_insufficient_mia() -> None:
    world, batch, reference = _clean_batch()
    layer = privacy_evaluate(batch.head(SMALL_BATCH_ROWS), reference, world.config)
    assert "mia_auc" not in layer.metrics
    assert INSUFFICIENT_DATA in layer.detail


def test_rotation_excludes_one_layer() -> None:
    assert ROTATED_LAYERS == ("marginal", "joint", "adversarial")
    world, batch, reference = _clean_batch()
    for index, expected in enumerate(ROTATED_LAYERS):
        assert run_gate(batch, reference, index, world.config).shadow_layer == expected


def test_composite_is_geometric_mean() -> None:
    ratios = [1.0, 1.0, 1.0, 1.0, 100.0]
    composite = float(np.exp(np.mean(np.log(ratios))))
    assert composite == pytest.approx(2.512, abs=GEOMETRIC_MEAN_TOLERANCE)
    assert composite < float(np.mean(ratios))


def test_structural_collapse_sets_the_composite() -> None:
    """A row-independent generator has no within-entity autocorrelation at all, and the
    geometric mean must not dilute that into five healthy-looking ratios."""
    world, _, reference = _partitions()
    rng = rng_for("pytest:shuffle")
    shuffled = reference.copy()
    for column in ("pan_token", "device_id", "merchant_id"):
        values = shuffled[column].to_numpy()
        shuffled[column] = values[rng.permutation(values.size)]
    from fidelity.behavioral import evaluate as behavioral_evaluate

    layer = behavioral_evaluate(shuffled, reference, world.config)
    assert layer.passed is False
    assert layer.metrics["composite"] >= world.config.fidelity_behavioral_max * STRUCTURAL_FAILURE_MULTIPLE
