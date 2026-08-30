"""Channel C: Isolation Forest for held-out and zero-day vectors."""

from dataclasses import dataclass

import numpy as np
from sklearn.ensemble import IsolationForest

from backend.runtime.config import PayLoopConfig

# The library default of 0.1 is roughly twelve times the real base rate and destroys
# precision, so contamination is set from the configured rate instead.
IFOREST_CONTAMINATION: float = 0.008
IFOREST_N_ESTIMATORS: int = 200
IFOREST_MAX_SAMPLES: int = 65_536
IFOREST_FIT_ROWS: int = 200_000


@dataclass
class ChannelCResult:
    model: IsolationForest


def fit_channel_c(
    train_x: np.ndarray, config: PayLoopConfig, rng: np.random.Generator
) -> ChannelCResult:
    sample = train_x
    if sample.shape[0] > IFOREST_FIT_ROWS:
        sample = sample[rng.choice(sample.shape[0], size=IFOREST_FIT_ROWS, replace=False)]
    model = IsolationForest(
        n_estimators=IFOREST_N_ESTIMATORS,
        contamination=config.iforest_contamination,
        max_samples=min(IFOREST_MAX_SAMPLES, sample.shape[0]),
        random_state=config.population_seed,
        n_jobs=-1,
    )
    model.fit(sample)
    return ChannelCResult(model=model)


def anomaly_scores(result: ChannelCResult, design: np.ndarray) -> np.ndarray:
    """Map the signed decision function onto [0, 1] so it can join the logistic stack."""
    raw = -result.model.score_samples(design)
    low, high = float(np.percentile(raw, 1)), float(np.percentile(raw, 99))
    if high <= low:
        return np.full(raw.shape, 0.5)
    return np.clip((raw - low) / (high - low), 0.0, 1.0)
