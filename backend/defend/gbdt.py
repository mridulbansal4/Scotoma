"""Channel A: the inline LightGBM scorer, its Platt calibration, and the ONNX export."""

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from lightgbm import LGBMClassifier, early_stopping, log_evaluation
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss

from backend.runtime.config import PayLoopConfig
from backend.runtime.errors import ModelArtifactMissing

LGBM_FEATURE_FRACTION: float = 0.8
LGBM_BAGGING_FRACTION: float = 0.8
LGBM_BAGGING_FREQ: int = 1
LGBM_LAMBDA_L2: float = 1.0
LGBM_N_ESTIMATORS: int = 600
MIN_TRAINING_POSITIVES: int = 30
CALIBRATION_BINS: int = 10
ONNX_OPSET: int = 13


@dataclass
class ChannelAResult:
    model: CalibratedClassifierCV
    booster: LGBMClassifier
    feature_names: list[str]
    brier_calibrated: float
    brier_uncalibrated: float
    reliability: list[dict[str, float]]


def _classifier(config: PayLoopConfig, scale_pos_weight: float) -> LGBMClassifier:
    # scale_pos_weight OR is_unbalance, never both: using both distorts the predicted
    # probabilities the Elkan threshold depends on.
    return LGBMClassifier(
        learning_rate=config.lgbm_learning_rate,
        num_leaves=config.lgbm_num_leaves,
        min_child_samples=config.lgbm_min_child_samples,
        n_estimators=LGBM_N_ESTIMATORS,
        colsample_bytree=LGBM_FEATURE_FRACTION,
        subsample=LGBM_BAGGING_FRACTION,
        subsample_freq=LGBM_BAGGING_FREQ,
        reg_lambda=LGBM_LAMBDA_L2,
        scale_pos_weight=scale_pos_weight,
        objective="binary",
        n_jobs=-1,
        verbose=-1,
    )


def reliability_curve(y_true: np.ndarray, probabilities: np.ndarray) -> list[dict[str, float]]:
    edges = np.linspace(0.0, 1.0, CALIBRATION_BINS + 1)
    bins = np.clip(np.digitize(probabilities, edges[1:-1]), 0, CALIBRATION_BINS - 1)
    curve = []
    for index in range(CALIBRATION_BINS):
        selector = bins == index
        if not selector.any():
            continue
        curve.append(
            {
                "bin_lower": float(edges[index]),
                "bin_upper": float(edges[index + 1]),
                "mean_predicted": float(probabilities[selector].mean()),
                "observed_rate": float(y_true[selector].mean()),
                "count": int(selector.sum()),
            }
        )
    return curve


def fit_channel_a(
    train_x: np.ndarray,
    train_y: np.ndarray,
    validation_x: np.ndarray,
    validation_y: np.ndarray,
    feature_names: list[str],
    config: PayLoopConfig,
) -> ChannelAResult:
    positives = int(train_y.sum())
    if positives < MIN_TRAINING_POSITIVES:
        raise ValueError(
            f"only {positives} positives in the training window; the calibrator is "
            f"meaningless below {MIN_TRAINING_POSITIVES}"
        )
    negatives = int((train_y == 0).sum())
    booster = _classifier(config, scale_pos_weight=max(negatives / max(positives, 1), 1.0))
    booster.fit(
        train_x,
        train_y,
        eval_set=[(validation_x, validation_y)],
        eval_metric="average_precision",
        callbacks=[
            early_stopping(config.lgbm_early_stopping_rounds, verbose=False),
            log_evaluation(0),
        ],
    )

    # Platt (sigmoid) scaling on the held-out temporal slice. Isotonic overfits when
    # positives are scarce, and at 0.15% prevalence positives are scarce.
    calibrated = CalibratedClassifierCV(estimator=booster, method="sigmoid", cv="prefit")
    calibrated.fit(validation_x, validation_y)

    raw = booster.predict_proba(validation_x)[:, 1]
    tuned = calibrated.predict_proba(validation_x)[:, 1]
    return ChannelAResult(
        model=calibrated,
        booster=booster,
        feature_names=feature_names,
        brier_calibrated=float(brier_score_loss(validation_y, tuned)),
        brier_uncalibrated=float(brier_score_loss(validation_y, raw)),
        reliability=reliability_curve(validation_y, tuned),
    )


def platt_coefficients(calibrated: CalibratedClassifierCV) -> tuple[float, float]:
    calibrator = calibrated.calibrated_classifiers_[0].calibrators[0]
    return float(calibrator.a_), float(calibrator.b_)


def export_onnx(result: ChannelAResult, path: Path) -> Path:
    """The frozen artefact the hot path loads once at process start."""
    from onnxmltools import convert_lightgbm
    from onnxmltools.convert.common.data_types import FloatTensorType

    path.parent.mkdir(parents=True, exist_ok=True)
    initial_types = [("input", FloatTensorType([None, len(result.feature_names)]))]
    try:
        model = convert_lightgbm(
            result.booster.booster_,
            initial_types=initial_types,
            target_opset=ONNX_OPSET,
            zipmap=False,
        )
    except TypeError:
        model = convert_lightgbm(
            result.booster.booster_, initial_types=initial_types, target_opset=ONNX_OPSET
        )
    path.write_bytes(model.SerializeToString())
    return path


def write_threshold_artifact(
    path: Path,
    threshold: float,
    platt: tuple[float, float],
    feature_names: list[str],
    bands: dict[str, float],
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "threshold": threshold,
        "platt_a": platt[0],
        "platt_b": platt[1],
        "feature_names": feature_names,
        "ladder_bands": bands,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def load_threshold_artifact(path: Path) -> dict:
    if not path.exists():
        raise ModelArtifactMissing(f"threshold artefact missing at {path}")
    return json.loads(path.read_text(encoding="utf-8"))
