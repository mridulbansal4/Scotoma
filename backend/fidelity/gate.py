"""Gate composition and the anti-gaming rotation rule.

The batch handed to the gate is what would actually be appended to the training pool: the
round's campaign events mixed into a matched slice of legitimate traffic at the campaign's
realised prevalence. Comparing raw fraud rows against a legitimate reference would measure
the fraud signal rather than the fidelity of the generator; layers 1 and 2 narrow further
to the legitimate view for the same reason.
"""

from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd

from backend.fidelity import adversarial, behavioral, joint, marginal, privacy, utility
from backend.fidelity.marginal import LayerResult
from backend.runtime.config import PayLoopConfig
from backend.runtime.errors import FidelityGateFailure

ROTATED_LAYERS: tuple[str, ...] = ("marginal", "joint", "adversarial")

LAYER_FUNCTIONS: dict[str, Callable[[pd.DataFrame, pd.DataFrame, PayLoopConfig], LayerResult]] = {
    "marginal": marginal.evaluate,
    "joint": joint.evaluate,
    "behavioral": behavioral.evaluate,
    "utility": utility.evaluate,
    "adversarial": adversarial.evaluate,
    "privacy": privacy.evaluate,
}


@dataclass(frozen=True)
class GateResult:
    passed: bool
    layers: dict[str, LayerResult]
    composite_behavioral: float
    shadow_layer: str
    shadow_failure: bool

    def failure_hints(self) -> list[str]:
        hints = []
        for name, result in self.layers.items():
            if not result.passed and name != self.shadow_layer:
                hints.append(f"{name}: {result.detail}")
        return hints

    def failed_layers(self) -> list[str]:
        return [
            name
            for name, result in self.layers.items()
            if not result.passed and name != self.shadow_layer
        ]

    def as_payload(self) -> dict:
        return {
            "passed": self.passed,
            "shadow_layer": self.shadow_layer,
            "shadow_failure": self.shadow_failure,
            "composite_behavioral": self.composite_behavioral,
            "layers": {
                name: {"passed": result.passed, **result.metrics}
                for name, result in self.layers.items()
            },
        }


def run_gate(
    batch: pd.DataFrame, reference: pd.DataFrame, round_index: int, config: PayLoopConfig
) -> GateResult:
    if batch.empty:
        raise FidelityGateFailure("empty batch reached the gate")
    if reference.empty:
        raise FidelityGateFailure("empty reference frame reached the gate")

    # One of the three rotatable layers is scored but excluded from the pass decision each
    # round, so a generator cannot be tuned against a fixed set of six checks.
    shadow = ROTATED_LAYERS[round_index % len(ROTATED_LAYERS)]

    results = {
        name: _safe_evaluate(name, fn, batch, reference, config)
        for name, fn in LAYER_FUNCTIONS.items()
    }
    active = [result for name, result in results.items() if name != shadow]

    return GateResult(
        passed=all(result.passed for result in active),
        layers=results,
        composite_behavioral=float(results["behavioral"].metrics["composite"]),
        shadow_layer=shadow,
        shadow_failure=not results[shadow].passed,
    )


def _safe_evaluate(
    name: str,
    function: Callable[[pd.DataFrame, pd.DataFrame, PayLoopConfig], LayerResult],
    batch: pd.DataFrame,
    reference: pd.DataFrame,
    config: PayLoopConfig,
) -> LayerResult:
    try:
        return function(batch, reference, config)
    except (ValueError, KeyError, TypeError, ZeroDivisionError) as exc:
        # A layer that cannot run is a failed layer, not a skipped one.
        return LayerResult(
            name,
            False,
            {"composite": float(config.fidelity_behavioral_max) * 2.0}
            if name == "behavioral"
            else {},
            f"layer raised {type(exc).__name__}: {exc}",
        )
