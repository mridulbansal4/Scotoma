"""The three-channel detector: stacking, the graph-channel kill rule, and the
disjointness assertions that protect the blind holdout."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, precision_recall_curve

from defend.anomaly import ChannelCResult, anomaly_scores, fit_channel_c
from defend.cost import CostMatrix, cost_per_100k, matrix_from_config, optimal_threshold
from defend.features import FEATURE_NAMES, FeatureContext, compute_features
from defend.gbdt import (
    ChannelAResult,
    export_onnx,
    fit_channel_a,
    platt_coefficients,
    write_threshold_artifact,
)
from defend.graph_channel import ChannelBResult, build_design, fit_channel_b, score_channel_b
from defend.ladder import band_boundaries
from defend.split import temporal_split
from runtime.config import PayLoopConfig
from runtime.errors import BlindHoldoutLeak
from runtime.seeding import rng_for
from schema.ces import feature_columns

GNN_MIN_LIFT_PRAUC: float = 0.03
SUSPICIOUS_PR_AUC: float = 0.95
DETECTOR_SHAP_TOP_K: int = 15
PRECISION_AT_K_FRACTION: float = 0.001
RECALL_AT_PRECISION: float = 0.95
ARTIFACTS_DIR: Path = Path(__file__).resolve().parent.parent / "artifacts"
MODEL_FILENAME: str = "model.onnx"
THRESHOLD_FILENAME: str = "threshold.json"
REASON_DICTIONARY_FILENAME: str = "reason_dictionary.json"


def keeps_graph_channel(lift: float, minimum: float) -> bool:
    """Three absolute PR-AUC points, not three percent: 0.72 to 0.75, not 0.72 to 0.7416."""
    return lift >= minimum


@dataclass(frozen=True)
class DetectorState:
    threshold: float
    top_shap_features: list[str]
    per_vector_recall: dict[str, float]
    survivors: list[str]


@dataclass
class EvaluationResult:
    pr_auc: float
    fpr_legit: float
    evasion_rate: float
    cost_per_100k: float
    precision_at_k: float
    recall_at_95_precision: float
    fp_tp_ratio: float
    scores: np.ndarray
    labels: np.ndarray
    evasion: dict[str, float] = field(default_factory=dict)
    per_vector_recall: dict[str, float] = field(default_factory=dict)
    suspicious: bool = False


def _fp_tp_ratio(labels: np.ndarray, predicted: np.ndarray) -> float:
    true_positive = int(((labels == 1) & predicted).sum())
    false_positive = int(((labels == 0) & predicted).sum())
    return float(false_positive / true_positive) if true_positive else float("inf")


def _precision_at_k(labels: np.ndarray, scores: np.ndarray) -> float:
    k = max(int(len(scores) * PRECISION_AT_K_FRACTION), 1)
    top = np.argsort(-scores)[:k]
    return float(labels[top].mean())


def _recall_at_precision(labels: np.ndarray, scores: np.ndarray) -> float:
    if labels.sum() == 0:
        return 0.0
    precision, recall, _ = precision_recall_curve(labels, scores)
    eligible = recall[precision >= RECALL_AT_PRECISION]
    return float(eligible.max()) if eligible.size else 0.0


class Detector:
    """Channel A always ships. Channel C always ships. Channel B ships only if it earns
    three absolute PR-AUC points."""

    def __init__(
        self,
        config: PayLoopConfig,
        context: FeatureContext | None = None,
        sim_start: datetime | None = None,
    ) -> None:
        self.config = config
        self.context = context or FeatureContext()
        self.sim_start = sim_start
        self.cost_matrix: CostMatrix = matrix_from_config(config)
        self.channel_a: ChannelAResult | None = None
        self.channel_b: ChannelBResult | None = None
        self.channel_c: ChannelCResult | None = None
        self.stack: LogisticRegression | None = None
        self.threshold: float = 0.5
        self.gnn_enabled: bool = False
        self.gnn_measured_lift: float | None = None
        self.validation_pr_auc: float = 0.0
        self.top_shap_features: list[str] = []
        self.per_vector_recall: dict[str, float] = {}
        self.brier_calibrated: float = 0.0
        self.brier_uncalibrated: float = 0.0
        self.reliability: list[dict[str, float]] = []
        self.suspicious_pr_auc: bool = False

    def assert_blind_disjoint(self, pool: pd.DataFrame, blind: pd.DataFrame) -> None:
        if blind is None or blind.empty or pool.empty:
            return
        if not set(blind["event_id"].astype(str)).isdisjoint(set(pool["event_id"].astype(str))):
            raise BlindHoldoutLeak("blind cohort event ids intersect the training pool")
        if not set(blind["payer_entity_id"].astype(str)).isdisjoint(
            set(pool["payer_entity_id"].astype(str))
        ):
            raise BlindHoldoutLeak("blind cohort payer entities intersect the training pool")

    def design(self, frame: pd.DataFrame) -> pd.DataFrame:
        features = compute_features(frame, self.context)
        feature_columns(features)
        return features

    def fit(self, pool: pd.DataFrame, blind: pd.DataFrame | None = None) -> "Detector":
        self.assert_blind_disjoint(pool, blind)
        sim_start = (
            self.sim_start or pd.to_datetime(pool["event_ts"], utc=True).min().to_pydatetime()
        )
        split = temporal_split(pool, sim_start, self.config)
        if split.train.empty or split.validation.empty:
            raise ValueError("temporal split produced an empty training or validation slice")

        train_features = self.design(split.train)
        validation_features = self.design(split.validation)
        train_y = split.train["is_fraud"].to_numpy(dtype=int)
        validation_y = split.validation["is_fraud"].to_numpy(dtype=int)

        self.channel_a = fit_channel_a(
            train_features.to_numpy("float32"),
            train_y,
            validation_features.to_numpy("float32"),
            validation_y,
            list(FEATURE_NAMES),
            self.config,
        )
        self.brier_calibrated = self.channel_a.brier_calibrated
        self.brier_uncalibrated = self.channel_a.brier_uncalibrated
        self.reliability = self.channel_a.reliability

        rng = rng_for("detector:anomaly")
        self.channel_c = fit_channel_c(train_features.to_numpy("float32"), self.config, rng)

        channel_scores = {
            "gbdt": self.channel_a.model.predict_proba(validation_features.to_numpy("float32"))[
                :, 1
            ],
            "anomaly": anomaly_scores(self.channel_c, validation_features.to_numpy("float32")),
        }

        if self.config.gnn_enabled:
            self._fit_graph_channel(
                split, train_features, validation_features, train_y, validation_y, channel_scores
            )

        self.stack = LogisticRegression(max_iter=500)
        stacked = np.column_stack([channel_scores[name] for name in self._channel_order()])
        self.stack.fit(stacked, validation_y)

        blended = self.stack.predict_proba(stacked)[:, 1]
        amounts = pd.to_numeric(split.validation["amount"], errors="coerce").to_numpy("float64")
        self.threshold = optimal_threshold(validation_y, blended, amounts, self.cost_matrix)
        self._record_shap(train_features, rng)

        evaluation = self.evaluate(split.validation)
        self.suspicious_pr_auc = evaluation.pr_auc > SUSPICIOUS_PR_AUC
        self.validation_pr_auc = evaluation.pr_auc
        self.per_vector_recall = evaluation.per_vector_recall
        return self

    def _channel_order(self) -> list[str]:
        return ["gbdt", "graph", "anomaly"] if self.gnn_enabled else ["gbdt", "anomaly"]

    def _fit_graph_channel(
        self,
        split,
        train_features: pd.DataFrame,
        validation_features: pd.DataFrame,
        train_y: np.ndarray,
        validation_y: np.ndarray,
        channel_scores: dict[str, np.ndarray],
    ) -> None:
        train_design = build_design(train_features, split.train["payee_entity_id"])
        validation_design = build_design(validation_features, split.validation["payee_entity_id"])
        candidate = fit_channel_b(train_design, train_y, self.config)
        graph_scores = score_channel_b(candidate, validation_design)

        baseline = average_precision_score(validation_y, channel_scores["gbdt"])
        combined = average_precision_score(
            validation_y, 0.5 * (channel_scores["gbdt"] + graph_scores)
        )
        lift = float(combined - baseline)
        self.gnn_measured_lift = lift
        if keeps_graph_channel(lift, self.config.gnn_min_lift_prauc):
            self.channel_b = candidate
            self.gnn_enabled = True
            channel_scores["graph"] = graph_scores
        else:
            self.channel_b = None
            self.gnn_enabled = False

    def _record_shap(self, train_features: pd.DataFrame, rng: np.random.Generator) -> None:
        from defend.explain import background_sample, shap_values

        if self.channel_a is None:
            return
        design = train_features.to_numpy("float32")
        sample = design[rng.choice(design.shape[0], size=min(2000, design.shape[0]), replace=False)]
        try:
            values = shap_values(
                self.channel_a.booster.booster_, sample, background_sample(design, rng)
            )
        except (ValueError, RuntimeError, MemoryError):
            self.top_shap_features = list(FEATURE_NAMES[:DETECTOR_SHAP_TOP_K])
            return
        importance = np.abs(values).mean(axis=0)
        order = np.argsort(-importance)[:DETECTOR_SHAP_TOP_K]
        self.top_shap_features = [FEATURE_NAMES[int(i)] for i in order]

    def channel_scores(self, frame: pd.DataFrame) -> dict[str, np.ndarray]:
        features = self.design(frame)
        design = features.to_numpy("float32")
        scores = {
            "gbdt": self.channel_a.model.predict_proba(design)[:, 1],
            "anomaly": anomaly_scores(self.channel_c, design),
        }
        if self.gnn_enabled and self.channel_b is not None:
            scores["graph"] = score_channel_b(
                self.channel_b, build_design(features, frame["payee_entity_id"])
            )
        return scores

    def score(self, frame: pd.DataFrame) -> np.ndarray:
        scores = self.channel_scores(frame)
        stacked = np.column_stack([scores[name] for name in self._channel_order()])
        return self.stack.predict_proba(stacked)[:, 1]

    def evaluate(self, frame: pd.DataFrame) -> EvaluationResult:
        if frame.empty:
            return EvaluationResult(
                0.0, 0.0, 1.0, 0.0, 0.0, 0.0, float("inf"), np.empty(0), np.empty(0)
            )
        scores = self.score(frame)
        labels = frame["is_fraud"].to_numpy(dtype=int)
        amounts = pd.to_numeric(frame["amount"], errors="coerce").to_numpy("float64")
        predicted = scores >= self.threshold

        pr_auc = (
            float(average_precision_score(labels, scores))
            if labels.sum() and (labels == 0).sum()
            else 0.0
        )
        legitimate = labels == 0
        fpr = float(predicted[legitimate].mean()) if legitimate.any() else 0.0
        fraud = labels == 1
        evasion = float((~predicted[fraud]).mean()) if fraud.any() else 0.0

        per_campaign: dict[str, float] = {}
        if "campaign_id" in frame.columns and fraud.any():
            for campaign_id, group in frame[fraud].groupby("campaign_id", sort=False):
                if campaign_id is None or pd.isna(campaign_id):
                    continue
                group_scores = scores[frame.index.get_indexer(group.index)]
                per_campaign[str(campaign_id)] = float((group_scores < self.threshold).mean())

        per_vector: dict[str, float] = {}
        if "vector_id" in frame.columns and fraud.any():
            for vector_id, group in frame[fraud].groupby("vector_id", sort=False):
                if vector_id is None or pd.isna(vector_id):
                    continue
                group_scores = scores[frame.index.get_indexer(group.index)]
                per_vector[str(vector_id)] = float((group_scores >= self.threshold).mean())

        return EvaluationResult(
            pr_auc=pr_auc,
            fpr_legit=fpr,
            evasion_rate=evasion,
            cost_per_100k=cost_per_100k(labels, scores, self.threshold, amounts, self.cost_matrix),
            precision_at_k=_precision_at_k(labels, scores),
            recall_at_95_precision=_recall_at_precision(labels, scores),
            fp_tp_ratio=_fp_tp_ratio(labels, predicted),
            scores=scores,
            labels=labels,
            evasion=per_campaign,
            per_vector_recall=per_vector,
            suspicious=pr_auc > SUSPICIOUS_PR_AUC,
        )

    def pr_auc_by_vector(self, frame: pd.DataFrame) -> dict[str, float]:
        if frame.empty or "vector_id" not in frame.columns:
            return {}
        scores = self.score(frame)
        labels = frame["is_fraud"].to_numpy(dtype=int)
        legitimate = labels == 0
        results: dict[str, float] = {}
        for vector_id in sorted({str(v) for v in frame.loc[labels == 1, "vector_id"].dropna()}):
            selector = (frame["vector_id"].astype(str) == vector_id).to_numpy() | legitimate
            subset_labels = labels[selector]
            if subset_labels.sum() == 0 or (subset_labels == 0).sum() == 0:
                continue
            results[vector_id] = float(average_precision_score(subset_labels, scores[selector]))
        return results

    def pr_auc_validation(self) -> float:
        """PR-AUC on the calibration slice. Optimistic by construction, so it is a sanity
        reading rather than a basis for choosing between models; loop.controller compares
        candidates on a held-out frame instead."""
        return self.validation_pr_auc

    def state(self) -> DetectorState:
        survivors = [vector for vector, recall in self.per_vector_recall.items() if recall < 0.6]
        return DetectorState(
            threshold=self.threshold,
            top_shap_features=list(self.top_shap_features),
            per_vector_recall=dict(self.per_vector_recall),
            survivors=survivors,
        )

    def export_onnx(self, path: Path | None = None) -> Path:
        """The frozen artefacts a clean clone needs to score an event without a pipeline run."""
        from defend.explain import reason_dictionary_payload

        target = path or ARTIFACTS_DIR / MODEL_FILENAME
        exported = export_onnx(self.channel_a, target)
        write_threshold_artifact(
            target.parent / THRESHOLD_FILENAME,
            self.threshold,
            platt_coefficients(self.channel_a.model),
            list(FEATURE_NAMES),
            band_boundaries(),
        )
        (target.parent / REASON_DICTIONARY_FILENAME).write_text(
            json.dumps(reason_dictionary_payload(), indent=2, sort_keys=True), encoding="utf-8"
        )
        return exported
