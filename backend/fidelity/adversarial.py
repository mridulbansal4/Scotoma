"""Layer 5: a real-versus-synthetic discriminator. Too separable fails; so does inverted."""

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

from backend.fidelity.marginal import LayerResult, numeric_frame
from backend.runtime.config import PayLoopConfig
from backend.runtime.seeding import rng_for

FIDELITY_DISCRIMINATOR_AUC_MIN: float = 0.50
FIDELITY_DISCRIMINATOR_AUC_MAX: float = 0.65
DISCRIMINATOR_SAMPLE_ROWS: int = 20_000
DISCRIMINATOR_MAX_ITER: int = 80
DISCRIMINATOR_TEST_FRACTION: float = 0.30
MIN_ROWS_FOR_DISCRIMINATOR: int = 400
# A discriminator that lands at chance is the desired result and will scatter either side
# of 0.50. Inversion means a materially negative signal, so the floor carries three
# standard errors of slack; at 0.50 the standard error is about 1 / (2 * sqrt(n)).
DISCRIMINATOR_NOISE_SIGMAS: float = 3.0


def _balanced_sample(frame: pd.DataFrame, size: int, rng: np.random.Generator) -> pd.DataFrame:
    if len(frame) <= size:
        return frame
    return frame.iloc[rng.choice(len(frame), size=size, replace=False)].reset_index(drop=True)


def noise_floor(test_rows: int) -> float:
    if test_rows <= 0:
        return FIDELITY_DISCRIMINATOR_AUC_MIN
    slack = DISCRIMINATOR_NOISE_SIGMAS / (2.0 * np.sqrt(test_rows))
    return FIDELITY_DISCRIMINATOR_AUC_MIN - float(slack)


def discriminator_auc(batch: pd.DataFrame, reference: pd.DataFrame) -> tuple[float, int]:
    rng = rng_for("fidelity:adversarial")
    size = min(len(batch), len(reference), DISCRIMINATOR_SAMPLE_ROWS)
    left = numeric_frame(_balanced_sample(batch, size, rng))
    right = numeric_frame(_balanced_sample(reference, size, rng))
    shared = [c for c in left.columns if c in right.columns]
    if not shared:
        return 0.5, 0
    design = np.vstack([left[shared].to_numpy("float64"), right[shared].to_numpy("float64")])
    labels = np.concatenate([np.ones(len(left)), np.zeros(len(right))])
    train_x, test_x, train_y, test_y = train_test_split(
        design, labels, test_size=DISCRIMINATOR_TEST_FRACTION, random_state=0, stratify=labels
    )
    model = HistGradientBoostingClassifier(max_iter=DISCRIMINATOR_MAX_ITER, random_state=0)
    model.fit(train_x, train_y)
    return float(roc_auc_score(test_y, model.predict_proba(test_x)[:, 1])), int(test_y.size)


def evaluate(batch: pd.DataFrame, reference: pd.DataFrame, config: PayLoopConfig) -> LayerResult:
    if len(batch) < MIN_ROWS_FOR_DISCRIMINATOR or len(reference) < MIN_ROWS_FOR_DISCRIMINATOR:
        return LayerResult(
            "adversarial", True, {"discriminator_auc": 0.5}, "too few rows to discriminate"
        )
    auc, test_rows = discriminator_auc(batch, reference)
    # Below the noise floor the discriminator is inverted, which indicates a bug rather
    # than quality, so it fails the same way an over-separable batch does.
    floor = noise_floor(test_rows)
    passed = floor <= auc <= config.fidelity_discriminator_auc_max
    return LayerResult(
        "adversarial",
        bool(passed),
        {"discriminator_auc": round(auc, 4), "auc_floor": round(floor, 4)},
        f"auc {auc:.3f} against band [{floor:.3f}, {config.fidelity_discriminator_auc_max}]",
    )
