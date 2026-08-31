"""ULB creditcardfraud: the calibration evidence, and nothing else.

This corpus does one job. Its features are PCA components, so it cannot produce a readable
reason code and must never be used for one. What it can do, which nothing else here can,
is settle the Platt-versus-isotonic question on **genuinely observed transactions** at a
real 0.172% base rate. Sparkov is simulated; ULB is not.

The ruling under test is that isotonic overfits when positives are scarce. That is an
empirical claim, so it gets measured on both calibrators over the same split rather than
asserted.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from backend.defend.gbdt import reliability_curve
from backend.runtime.config import PayLoopConfig
from backend.runtime.errors import RegistryInvalid

LABEL_COLUMN: str = "Class"
TIME_COLUMN: str = "Time"
AMOUNT_COLUMN: str = "Amount"

TRAIN_FRACTION: float = 0.60
VALIDATION_FRACTION: float = 0.20
N_ESTIMATORS: int = 300
CALIBRATORS: tuple[str, ...] = ("sigmoid", "isotonic")


@dataclass(frozen=True)
class CalibrationComparison:
    """One calibrator's numbers on the held-out test slice."""

    method: str
    pr_auc: float
    roc_auc: float
    brier: float
    expected_calibration_error: float
    worst_populated_bin: float
    saturated_fraction: float
    reliability: list[dict[str, float]]

    def as_payload(self) -> dict:
        return {
            "method": self.method,
            "pr_auc": round(self.pr_auc, 4),
            "roc_auc": round(self.roc_auc, 4),
            "brier": round(self.brier, 6),
            "expected_calibration_error": round(self.expected_calibration_error, 6),
            "worst_populated_bin": round(self.worst_populated_bin, 4),
            "saturated_fraction": round(self.saturated_fraction, 4),
            "reliability": self.reliability,
        }


def read_ulb(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    for column in (TIME_COLUMN, AMOUNT_COLUMN, LABEL_COLUMN):
        if column not in frame.columns:
            raise RegistryInvalid(f"{path.name} is not ULB creditcardfraud; missing {column}")
    return frame.sort_values(TIME_COLUMN).reset_index(drop=True)


def _splits(frame: pd.DataFrame) -> tuple[np.ndarray, ...]:
    """Split on Time rather than at random, since Time is elapsed seconds and position is order."""
    features = [c for c in frame.columns if c != LABEL_COLUMN]
    matrix = frame[features].to_numpy("float32")
    labels = frame[LABEL_COLUMN].to_numpy("int8")
    train_end = int(len(frame) * TRAIN_FRACTION)
    valid_end = int(len(frame) * (TRAIN_FRACTION + VALIDATION_FRACTION))
    return (
        matrix[:train_end],
        labels[:train_end],
        matrix[train_end:valid_end],
        labels[train_end:valid_end],
        matrix[valid_end:],
        labels[valid_end:],
    )


MIN_BIN_COUNT: int = 30


def _expected_calibration_error(curve: list[dict[str, float]]) -> float:
    """Mean |predicted - observed| weighted by how many events land in each bin.

    Weighting is the whole point. An unweighted worst-bin figure is decided by bins
    holding one or two events, where the observed rate can only be 0.0 or 1.0, so it
    reports noise as miscalibration and ranks the calibrators backwards.
    """
    if not curve:
        return float("nan")
    total = sum(bin_["count"] for bin_ in curve)
    if total <= 0:
        return float("nan")
    return sum(
        bin_["count"] * abs(bin_["mean_predicted"] - bin_["observed_rate"]) for bin_ in curve
    ) / total


def _worst_populated_bin(curve: list[dict[str, float]]) -> float:
    """Largest diagonal gap among bins carrying at least MIN_BIN_COUNT events."""
    gaps = [
        abs(bin_["mean_predicted"] - bin_["observed_rate"])
        for bin_ in curve
        if bin_["count"] >= MIN_BIN_COUNT
    ]
    return max(gaps) if gaps else float("nan")


def _saturated_fraction(scores: np.ndarray) -> float:
    """Share of scores pinned at exactly 0 or 1.

    Isotonic regression is a step function, so it can emit hard 0.0 and 1.0. A posterior
    of exactly 1.0 claims certainty, and the Elkan threshold cannot price certainty.
    """
    return float(np.mean((scores <= 0.0) | (scores >= 1.0)))


def compare_calibrators(frame: pd.DataFrame, config: PayLoopConfig) -> dict:
    """Fit once, calibrate twice, score both on the same untouched test slice."""
    train_x, train_y, valid_x, valid_y, test_x, test_y = _splits(frame)
    positives = int(train_y.sum())
    if positives < 30:
        raise RegistryInvalid(f"only {positives} positives in the ULB training window")

    booster = LGBMClassifier(
        learning_rate=config.lgbm_learning_rate,
        num_leaves=config.lgbm_num_leaves,
        min_child_samples=config.lgbm_min_child_samples,
        n_estimators=N_ESTIMATORS,
        scale_pos_weight=max(int((train_y == 0).sum()) / max(positives, 1), 1.0),
        objective="binary",
        n_jobs=-1,
        verbose=-1,
    )
    booster.fit(train_x, train_y)

    raw = booster.predict_proba(test_x)[:, 1]
    results = {
        "uncalibrated": CalibrationComparison(
            method="uncalibrated",
            pr_auc=float(average_precision_score(test_y, raw)),
            roc_auc=float(roc_auc_score(test_y, raw)),
            brier=float(brier_score_loss(test_y, raw)),
            expected_calibration_error=_expected_calibration_error(reliability_curve(test_y, raw)),
            worst_populated_bin=_worst_populated_bin(reliability_curve(test_y, raw)),
            saturated_fraction=_saturated_fraction(raw),
            reliability=reliability_curve(test_y, raw),
        ).as_payload()
    }

    for method in CALIBRATORS:
        calibrated = CalibratedClassifierCV(estimator=booster, method=method, cv="prefit")
        calibrated.fit(valid_x, valid_y)
        scores = calibrated.predict_proba(test_x)[:, 1]
        curve = reliability_curve(test_y, scores)
        results[method] = CalibrationComparison(
            method=method,
            pr_auc=float(average_precision_score(test_y, scores)),
            roc_auc=float(roc_auc_score(test_y, scores)),
            brier=float(brier_score_loss(test_y, scores)),
            expected_calibration_error=_expected_calibration_error(curve),
            worst_populated_bin=_worst_populated_bin(curve),
            saturated_fraction=_saturated_fraction(scores),
            reliability=curve,
        ).as_payload()

    sigmoid, isotonic = results["sigmoid"], results["isotonic"]
    return {
        "corpus": "ulb_creditcardfraud",
        "is_observed_data": True,
        "rows": int(len(frame)),
        "prevalence": round(float(frame[LABEL_COLUMN].mean()), 6),
        "train_rows": int(len(train_y)),
        "validation_rows": int(len(valid_y)),
        "validation_positives": int(valid_y.sum()),
        "test_rows": int(len(test_y)),
        "test_positives": int(test_y.sum()),
        "results": results,
        "platt_preserves_ranking": bool(sigmoid["pr_auc"] >= isotonic["pr_auc"]),
        "pr_auc_cost_of_isotonic": round(sigmoid["pr_auc"] - isotonic["pr_auc"], 4),
        "platt_better_on_populated_bins": bool(
            sigmoid["worst_populated_bin"] <= isotonic["worst_populated_bin"]
        ),
        "isotonic_saturated_fraction": isotonic["saturated_fraction"],
    }
