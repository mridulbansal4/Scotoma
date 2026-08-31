"""Channel A fitted on real Sparkov traffic, and the weights bundle it exports.

Two rules from the appendix are load-bearing here and both are about calibration:

  1. Negatives may be downsampled for the booster fit. The Platt layer may not be fitted
     on the downsampled frame. If it is, the posteriors describe a 10:1 world that does
     not exist, the Elkan threshold derived from them is wrong, and every cost_per_100k
     figure downstream is wrong.
  2. scale_pos_weight OR is_unbalance, never both. fit_channel_a already picks the first.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from backend.defend.gbdt import fit_channel_a, reliability_curve
from backend.realdata.featurize import SHARED_FEATURE_NAMES, build_features
from backend.runtime.config import PayLoopConfig

VALIDATION_FRACTION: float = 0.20
DEFAULT_NEGATIVE_RATIO: float = 10.0


@dataclass(frozen=True)
class RealFitResult:
    metrics: dict
    feature_names: list[str]

    def as_payload(self) -> dict:
        return {"metrics": self.metrics, "n_features": len(self.feature_names)}


def _temporal_holdout(matrix: pd.DataFrame, labels: np.ndarray) -> tuple:
    """Last VALIDATION_FRACTION by row order, which is time order after build_features."""
    cut = int(len(matrix) * (1.0 - VALIDATION_FRACTION))
    return (
        matrix.iloc[:cut].to_numpy("float32"),
        labels[:cut],
        matrix.iloc[cut:].to_numpy("float32"),
        labels[cut:],
    )


def _downsample_negatives(
    matrix: np.ndarray, labels: np.ndarray, ratio: float, seed: int
) -> tuple[np.ndarray, np.ndarray]:
    """Keep every positive, sample negatives to ratio:1. Fit only. Never calibration."""
    positives = np.flatnonzero(labels == 1)
    negatives = np.flatnonzero(labels == 0)
    keep = int(min(len(negatives), round(len(positives) * ratio)))
    if keep >= len(negatives):
        return matrix, labels
    rng = np.random.default_rng(seed)
    chosen = rng.choice(negatives, size=keep, replace=False)
    order = np.sort(np.concatenate([positives, chosen]))
    return matrix[order], labels[order]


def train(
    frame: pd.DataFrame,
    config: PayLoopConfig,
    negative_ratio: float | None = DEFAULT_NEGATIVE_RATIO,
) -> tuple[object, RealFitResult]:
    """Fit Channel A on one real partition and report honest calibration numbers."""
    matrix = build_features(frame, include_absent=False)
    labels = frame.sort_values("event_ts")["is_fraud"].to_numpy("int8")

    train_x, train_y, valid_x, valid_y = _temporal_holdout(matrix, labels)
    fit_x, fit_y = (
        _downsample_negatives(train_x, train_y, negative_ratio, config.population_seed)
        if negative_ratio
        else (train_x, train_y)
    )

    result = fit_channel_a(
        train_x=fit_x,
        train_y=fit_y,
        # Validation stays at the true base rate: this frame is what Platt sees.
        validation_x=valid_x,
        validation_y=valid_y,
        feature_names=list(SHARED_FEATURE_NAMES),
        config=config,
    )

    calibrated = result.model.predict_proba(valid_x)[:, 1]
    raw = result.booster.predict_proba(valid_x)[:, 1]
    metrics = {
        "rows_total": int(len(matrix)),
        "rows_fit": int(len(fit_y)),
        "prevalence_source": round(float(labels.mean()), 6),
        "prevalence_fit": round(float(fit_y.mean()), 6),
        "prevalence_calibration": round(float(valid_y.mean()), 6),
        "pr_auc": round(float(average_precision_score(valid_y, calibrated)), 4),
        "roc_auc": round(float(roc_auc_score(valid_y, calibrated)), 4),
        "brier_calibrated": round(float(brier_score_loss(valid_y, calibrated)), 6),
        "brier_uncalibrated": round(float(brier_score_loss(valid_y, raw)), 6),
        "reliability": reliability_curve(valid_y, calibrated),
    }
    return result, RealFitResult(metrics=metrics, feature_names=list(SHARED_FEATURE_NAMES))


def evaluate(model, frame: pd.DataFrame) -> dict:
    """Score a fitted model on another partition. This is the TSTR entry point."""
    matrix = build_features(frame, include_absent=False)
    labels = frame.sort_values("event_ts")["is_fraud"].to_numpy("int8")
    scores = model.predict_proba(matrix.to_numpy("float32"))[:, 1]
    return {
        "rows": int(len(labels)),
        "prevalence": round(float(labels.mean()), 6),
        "pr_auc": round(float(average_precision_score(labels, scores)), 4),
        "roc_auc": round(float(roc_auc_score(labels, scores)), 4),
    }


def export_weights(
    result,
    fit: RealFitResult,
    out_dir: Path,
    background: pd.DataFrame | None = None,
    extra: dict | None = None,
) -> list[str]:
    """Write the bundle A.8 asks for. Native booster text, not pickle: version-portable."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    result.booster.booster_.save_model(str(out_dir / "channel_a_lgbm.txt"))
    written.append("channel_a_lgbm.txt")

    (out_dir / "feature_spec.json").write_text(
        json.dumps({"features": fit.feature_names, "order_is_significant": True}, indent=2),
        encoding="utf-8",
    )
    written.append("feature_spec.json")

    payload = {
        "trained_at": datetime.now(UTC).isoformat(),
        "corpus": "sparkov",
        **fit.metrics,
        **(extra or {}),
    }
    (out_dir / "channel_a_metrics.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    written.append("channel_a_metrics.json")

    if background is not None:
        background.to_parquet(out_dir / "shap_background.parquet", index=False)
        written.append("shap_background.parquet")
    return written


def fit_and_export_channel_c(frame: pd.DataFrame, config: PayLoopConfig, out_dir: Path) -> dict:
    """Channel C on real legitimate traffic only.

    Fitting the anomaly detector on fraud as well would teach it that fraud is normal,
    which is the one thing it exists not to believe. Zero-day recall only means something
    if the model has never been shown the thing it is asked to find surprising.
    """
    import joblib

    from backend.defend.anomaly import fit_channel_c
    from backend.runtime.seeding import rng_for

    legitimate = frame[frame["is_fraud"] == 0]
    matrix = build_features(legitimate, include_absent=False)
    design = np.nan_to_num(matrix.to_numpy("float32"), nan=0.0, posinf=0.0, neginf=0.0)
    result = fit_channel_c(design, config, rng_for("realdata:channel_c"))

    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(result.model, out_dir / "channel_c_iforest.joblib")
    return {
        "rows_fitted": int(len(legitimate)),
        "fraud_rows_excluded": int(len(frame) - len(legitimate)),
        "contamination": config.iforest_contamination,
    }
