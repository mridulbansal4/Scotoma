"""Layer 2: pairwise correlation difference and categorical association drift."""

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency

from fidelity.marginal import LayerResult, legitimate_view, numeric_frame
from runtime.config import PayLoopConfig

FIDELITY_PCD_MAX: float = 0.15
FIDELITY_CRAMERS_V_MAX: float = 0.10

CATEGORICAL_COLUMNS: tuple[str, ...] = (
    "rail",
    "mcc",
    "response_code",
    "pos_entry_mode",
    "threeds_flow",
    "currency",
)
MISSING_CATEGORY: str = "__missing__"


def pairwise_correlation_difference(batch: pd.DataFrame, reference: pd.DataFrame) -> float:
    """Frobenius norm of the correlation-matrix difference, normalised by the number of
    off-diagonal pairs so the threshold does not move with the column count."""
    left, right = numeric_frame(batch), numeric_frame(reference)
    shared = [c for c in left.columns if c in right.columns]
    if len(shared) < 2:
        return 0.0
    left_corr = left[shared].corr().to_numpy()
    right_corr = right[shared].corr().to_numpy()
    difference = np.nan_to_num(left_corr - right_corr)
    pairs = difference.size - difference.shape[0]
    if pairs <= 0:
        return 0.0
    return float(np.sqrt((difference**2).sum() / pairs))


def cramers_v(left: pd.Series, right: pd.Series) -> float:
    table = pd.crosstab(left, right)
    if table.shape[0] < 2 or table.shape[1] < 2:
        return 0.0
    chi2 = float(chi2_contingency(table, correction=False)[0])
    total = float(table.to_numpy().sum())
    minimum_dimension = min(table.shape) - 1
    if total <= 0 or minimum_dimension <= 0:
        return 0.0
    return float(np.sqrt(chi2 / (total * minimum_dimension)))


def _categorical(frame: pd.DataFrame, column: str) -> pd.Series:
    return frame[column].astype("object").fillna(MISSING_CATEGORY).astype(str)


def max_cramers_v_delta(batch: pd.DataFrame, reference: pd.DataFrame) -> float:
    available = [c for c in CATEGORICAL_COLUMNS if c in batch.columns and c in reference.columns]
    worst = 0.0
    for position, first in enumerate(available):
        for second in available[position + 1 :]:
            batch_v = cramers_v(_categorical(batch, first), _categorical(batch, second))
            reference_v = cramers_v(_categorical(reference, first), _categorical(reference, second))
            worst = max(worst, abs(batch_v - reference_v))
    return worst


def evaluate(batch: pd.DataFrame, reference: pd.DataFrame, config: PayLoopConfig) -> LayerResult:
    batch = legitimate_view(batch)
    pcd = pairwise_correlation_difference(batch, reference)
    delta = max_cramers_v_delta(batch, reference)
    passed = pcd < config.fidelity_pcd_max and delta < FIDELITY_CRAMERS_V_MAX
    return LayerResult(
        name="joint",
        passed=bool(passed),
        metrics={"pcd": round(pcd, 4), "cramers_v_max_delta": round(delta, 4)},
        detail=f"pcd {pcd:.3f} vs max {config.fidelity_pcd_max}; max |dV| {delta:.3f}",
    )
