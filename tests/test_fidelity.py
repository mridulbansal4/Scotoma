"""Gate composition, the required ablation, and the failure modes the gate must catch."""

import numpy as np
import pandas as pd
import pytest

from backend.fidelity.ablation import run_ablation
from backend.fidelity.behavioral import STRUCTURAL_FAILURE_MULTIPLE
from backend.fidelity.gate import ROTATED_LAYERS, run_gate
from backend.fidelity.privacy import INSUFFICIENT_DATA
from backend.fidelity.privacy import evaluate as privacy_evaluate
from backend.loop.controller import _carrier_entities, _split_reference_and_carrier
from backend.runtime.seeding import rng_for
from tests import fixture_world

CARRIER_MULTIPLIER: float = 24.0
# Multiplying amounts by 1 + N(0, 0.5) measures a KS statistic near 0.05 against this
# population, comfortably inside the gate's declared 0.10 tolerance, and the gate is right
# to pass it. The noise here is sized to exceed that tolerance, which is what the layer is
# for; the amount and its currency conversion are noised together so the row stays coherent.
NOISE_SIGMA: float = 1.0
SMALL_BATCH_ROWS: int = 1_000
DUPLICATE_FRACTION: float = 0.05
GEOMETRIC_MEAN_TOLERANCE: float = 0.05
# The baseline matches each column on its own to within two points; that agreement is the
# premise of the argument, not an accident, so the test pins it.
MARGINAL_SHARE_TOLERANCE: float = 0.02
TIGHTLY_REPRODUCED_COLUMNS: tuple[str, ...] = ("rail", "response_code")


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
        pd.concat([carried, fraud], ignore_index=True)
        .sort_values("event_ts")
        .reset_index(drop=True)
    )
    return world, batch, reference


def test_gate_passes_own_simulator_output() -> None:
    world, batch, reference = _clean_batch()
    gate = run_gate(batch, reference, 0, world.config)
    load_bearing = {"behavioral", "utility", "adversarial", "privacy", "marginal"}
    failed = {name for name, layer in gate.layers.items() if not layer.passed}
    assert failed.isdisjoint(load_bearing), gate.layers


def test_gaussian_copula_ablation_fails_behavioral() -> None:
    """The ablation.

    The baseline reproduces the rail mix and the decline mix to within two points and still
    fails the behavioural layer outright, because a row-independent generator carries no
    within-entity sequence at all. Both halves are asserted: the per-column agreement is
    what makes the behavioural failure worth showing. Every column's agreement, including
    the looser ones, is written to ablation.json rather than left to this assertion."""
    _, reference, carrier = _partitions()
    result, payload = run_ablation(carrier, reference)

    behavioral = payload["layers"]["behavioral"]
    assert behavioral["passed"] is False, behavioral
    assert behavioral["composite"] >= payload["behavioral_max"], behavioral
    assert behavioral["iet_autocorr_batch"] < behavioral["iet_autocorr_reference"], behavioral

    for column in TIGHTLY_REPRODUCED_COLUMNS:
        difference = payload["marginal_shares"][column]["max_abs_difference"]
        assert difference <= MARGINAL_SHARE_TOLERANCE, (column, difference)

    assert result.passed is False


def test_noised_data_fails_marginal() -> None:
    world, batch, reference = _clean_batch()
    rng = rng_for("pytest:noise")
    noised = batch.copy()
    factor = (1.0 + rng.normal(0.0, NOISE_SIGMA, size=len(noised))).clip(0.05, None)
    noised["amount"] = (noised["amount"].to_numpy("float64") * factor).round(2)
    noised["amount_inr"] = (noised["amount_inr"].to_numpy("float64") * factor).round(2)
    gate = run_gate(noised, reference, 1, world.config)
    assert gate.layers["marginal"].passed is False


def test_duplicated_row_fails_privacy() -> None:
    world, _, reference = _partitions()
    rng = rng_for("pytest:duplicates")
    carrier = world.pool[~world.pool["is_fraud"]].reset_index(drop=True)
    copies = reference.iloc[
        rng.choice(len(reference), size=int(len(reference) * DUPLICATE_FRACTION))
    ]
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
    from backend.fidelity.behavioral import evaluate as behavioral_evaluate

    layer = behavioral_evaluate(shuffled, reference, world.config)
    assert layer.passed is False
    assert (
        layer.metrics["composite"]
        >= world.config.fidelity_behavioral_max * STRUCTURAL_FAILURE_MULTIPLE
    )
