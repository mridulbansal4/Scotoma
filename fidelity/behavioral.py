"""Layer 3: behavioural degradation. This is the layer the GaussianCopula ablation fails."""

import numpy as np
import pandas as pd

from fidelity.marginal import LayerResult
from generate.graph import motif_counts
from generate.injectors.base import campaign_subgraph
from runtime.config import PayLoopConfig

FIDELITY_BEHAVIORAL_MAX: float = 10.0
BEHAVIORAL_KEYS: tuple[str, ...] = ("device_id", "pan_token", "merchant_id")
AUTOCORRELATION_KEY: str = "pan_token"
MIN_EVENTS_PER_ENTITY: int = 5
MIN_AUTOCORRELATION: float = 0.01
MOTIF_SAMPLE_ROWS: int = 40_000
STRUCTURAL_FAILURE_MULTIPLE: float = 2.0


def _iet_std_by_key(frame: pd.DataFrame, key: str) -> float:
    if key not in frame.columns:
        return float("nan")
    deltas = (
        frame.sort_values("event_ts").groupby(key, sort=False)["event_ts"].diff().dt.total_seconds()
    )
    return float(deltas.std(skipna=True))


def _lag1_autocorrelation(frame: pd.DataFrame, key: str) -> float:
    """Within-entity lag-1 inter-event-time autocorrelation, averaged over entities with
    enough events. Row-independent generators cannot produce a positive value here."""
    if key not in frame.columns:
        return 0.0
    working = frame[[key, "event_ts"]].dropna().sort_values("event_ts")
    deltas = working.groupby(key, sort=False)["event_ts"].diff().dt.total_seconds()
    working = working.assign(iet=deltas).dropna(subset=["iet"])
    correlations: list[float] = []
    for _, group in working.groupby(key, sort=False):
        series = group["iet"].to_numpy("float64")
        if series.size < MIN_EVENTS_PER_ENTITY or np.std(series) == 0.0:
            continue
        correlations.append(float(np.corrcoef(series[:-1], series[1:])[0, 1]))
    finite = [value for value in correlations if np.isfinite(value)]
    return float(np.mean(finite)) if finite else 0.0


def autocorrelation_degradation(reference: pd.DataFrame, batch: pd.DataFrame, key: str) -> float:
    """Signed on purpose: a row-independent generator lands at or below zero here, and
    taking the magnitude would let that read as a healthy positive correlation."""
    real = _lag1_autocorrelation(reference, key)
    synthetic = _lag1_autocorrelation(batch, key)
    if synthetic < MIN_AUTOCORRELATION:
        return FIDELITY_BEHAVIORAL_MAX * 2.0
    return max(real / synthetic, synthetic / max(real, MIN_AUTOCORRELATION))


def motif_degradation(reference: pd.DataFrame, batch: pd.DataFrame) -> float:
    left = campaign_subgraph(reference.head(MOTIF_SAMPLE_ROWS))
    right = campaign_subgraph(batch.head(MOTIF_SAMPLE_ROWS))
    real_triangles, real_stars = motif_counts(left)
    synth_triangles, synth_stars = motif_counts(right)
    ratios = []
    for real, synthetic in ((real_triangles, synth_triangles), (real_stars, synth_stars)):
        if real <= 0.0 and synthetic <= 0.0:
            ratios.append(1.0)
            continue
        ratios.append(
            max(real, 1.0) / max(synthetic, 1.0)
            if real >= synthetic
            else max(synthetic, 1.0) / max(real, 1.0)
        )
    return float(max(ratios))


def evaluate(batch: pd.DataFrame, reference: pd.DataFrame, config: PayLoopConfig) -> LayerResult:
    ceiling = float(config.fidelity_behavioral_max) * STRUCTURAL_FAILURE_MULTIPLE
    ratios: dict[str, float] = {}
    structural: list[str] = []
    for key in BEHAVIORAL_KEYS:
        real, synth = _iet_std_by_key(reference, key), _iet_std_by_key(batch, key)
        if not (np.isfinite(real) and np.isfinite(synth)) or min(real, synth) <= 0.0:
            ratios[f"velocity_{key}"] = ceiling
            structural.append(f"no inter-event-time spread on {key}")
        else:
            ratios[f"velocity_{key}"] = max(real / synth, synth / real)

    ratios["graph_motif"] = motif_degradation(reference, batch)
    ratios["iet_autocorr"] = autocorrelation_degradation(reference, batch, key=AUTOCORRELATION_KEY)
    if ratios["iet_autocorr"] >= ceiling:
        structural.append(
            f"within-entity lag-1 inter-event-time autocorrelation on {AUTOCORRELATION_KEY} "
            "is not positive"
        )

    # Geometric mean: one catastrophic ratio must not be averaged away by five passing
    # ones. A structural collapse is not a ratio at all, so it sets the composite directly
    # rather than being diluted by five components that happen to look healthy.
    composite = float(np.exp(np.mean(np.log(list(ratios.values())))))
    if structural:
        composite = max(composite, ceiling)
    passed = composite < config.fidelity_behavioral_max
    detail = f"composite {composite:.2f} vs max {config.fidelity_behavioral_max}"
    if structural:
        detail = f"{detail}; {'; '.join(structural)}"
    return LayerResult(
        "behavioral",
        passed,
        {**{k: round(v, 4) for k, v in ratios.items()}, "composite": round(composite, 4)},
        detail,
    )
