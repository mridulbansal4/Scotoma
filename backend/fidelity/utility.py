"""Layer 4: train-synthetic-test-real against train-real-test-real.

The transfer task is whether an authorisation is declined, predicted from the rail,
merchant category, entry mode, currency, amount and timing. Using the fraud label would be
circular, because the batch under test is the very fraud the detector has not yet seen,
and a decline is the strongest non-label structure both frames carry.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score

from backend.fidelity.marginal import LayerResult
from backend.runtime.config import PayLoopConfig
from backend.runtime.seeding import rng_for

FIDELITY_TSTR_MIN_RATIO: float = 0.90
UTILITY_SAMPLE_ROWS: int = 20_000
UTILITY_MAX_ITER: int = 60
UTILITY_TEST_FRACTION: float = 0.30
MIN_ROWS_FOR_UTILITY: int = 200
MISSING_CATEGORY: str = "__missing__"

# The design carries only fields that bear on the target in this schema. Merchant category
# and amount do not move the approval decision here, so including them would measure how
# faithfully a generator reproduces noise rather than how well its structure transfers.
UTILITY_CATEGORICAL_COLUMNS: tuple[str, ...] = ("rail", "currency", "pos_entry_mode")
DECLINE_CODE_APPROVED: str = "00"


def _category_levels(reference: pd.DataFrame) -> dict[str, dict[str, int]]:
    levels: dict[str, dict[str, int]] = {}
    for column in UTILITY_CATEGORICAL_COLUMNS:
        if column not in reference.columns:
            continue
        encoded = reference[column].astype("object").fillna(MISSING_CATEGORY).astype(str)
        values = sorted(encoded.unique())
        levels[column] = {value: index for index, value in enumerate(values)}
    return levels


def _design(
    frame: pd.DataFrame, levels: dict[str, dict[str, int]]
) -> tuple[np.ndarray, np.ndarray]:
    if frame.empty:
        return np.empty((0, 0)), np.empty(0)
    response = frame.get("response_code", pd.Series(index=frame.index))
    response = response.fillna(DECLINE_CODE_APPROVED)
    target = (response != DECLINE_CODE_APPROVED).astype("int8").to_numpy()

    event_ts = pd.to_datetime(frame["event_ts"], utc=True)
    columns = {
        "hour_of_day": event_ts.dt.hour.astype("float64"),
        "day_of_week": event_ts.dt.dayofweek.astype("float64"),
        "cross_border": frame["cross_border"].astype("float64"),
    }
    for column, mapping in levels.items():
        encoded = frame[column].astype("object").fillna(MISSING_CATEGORY).astype(str)
        columns[column] = encoded.map(mapping).fillna(-1).astype("float64")
    return pd.DataFrame(columns).to_numpy("float64"), target


def _fit_score(
    train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray, test_y: np.ndarray
) -> float:
    if train_x.size == 0 or test_x.size == 0 or len(set(train_y)) < 2 or len(set(test_y)) < 2:
        return 0.0
    model = HistGradientBoostingClassifier(max_iter=UTILITY_MAX_ITER, random_state=0)
    model.fit(train_x, train_y)
    return float(average_precision_score(test_y, model.predict_proba(test_x)[:, 1]))


def _subsample(frame: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    if len(frame) <= UTILITY_SAMPLE_ROWS:
        return frame
    positions = rng.choice(len(frame), size=UTILITY_SAMPLE_ROWS, replace=False)
    return frame.iloc[positions].reset_index(drop=True)


def evaluate(batch: pd.DataFrame, reference: pd.DataFrame, config: PayLoopConfig) -> LayerResult:
    rng = rng_for("fidelity:utility")
    if len(batch) < MIN_ROWS_FOR_UTILITY or len(reference) < MIN_ROWS_FOR_UTILITY:
        return LayerResult(
            "utility", True, {"tstr_ratio": 1.0}, "too few rows to evaluate transfer"
        )

    levels = _category_levels(reference)
    synthetic_x, synthetic_y = _design(_subsample(batch, rng), levels)
    real_x, real_y = _design(_subsample(reference, rng), levels)

    split = int(len(real_y) * (1.0 - UTILITY_TEST_FRACTION))
    tstr = _fit_score(synthetic_x, synthetic_y, real_x[split:], real_y[split:])
    trtr = _fit_score(real_x[:split], real_y[:split], real_x[split:], real_y[split:])
    ratio = tstr / trtr if trtr > 0 else 0.0
    return LayerResult(
        "utility",
        bool(ratio >= config.fidelity_tstr_min_ratio),
        {
            "tstr_pr_auc": round(tstr, 4),
            "trtr_pr_auc": round(trtr, 4),
            "tstr_ratio": round(ratio, 4),
        },
        f"tstr/trtr {ratio:.3f} vs min {config.fidelity_tstr_min_ratio}",
    )
