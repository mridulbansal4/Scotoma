"""Leakage, point-in-time correctness, calibration, the kill rule, and the hot-path boundary."""

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from defend.cost import THRESHOLD_GRID, CostMatrix, expected_cost, optimal_threshold
from defend.ensemble import SUSPICIOUS_PR_AUC, Detector, keeps_graph_channel
from defend.features import cart_hash_mismatch, compute_features
from defend.gbdt import reliability_curve
from defend.split import temporal_split
from defend.windows import rolling_by_key
from generate.population import SIM_START
from runtime.errors import FeatureLeakage
from schema.ces import feature_columns
from tests import campaign_for, fixture_world

BENCH_PATH: Path = Path(__file__).resolve().parent.parent / "defend" / "bench.py"
PERMITTED_HOT_PATH_IMPORTS: frozenset[str] = frozenset(
    {"onnxruntime", "redis", "hmac", "hashlib", "numpy", "time", "runtime.config"}
)
GNN_LIFT_BELOW: float = 0.029
GNN_LIFT_ABOVE: float = 0.031
GNN_KILL_THRESHOLD: float = 0.03


def test_feature_columns_rejects_labels() -> None:
    with pytest.raises(FeatureLeakage):
        feature_columns(pd.DataFrame({"amount": [1.0], "is_fraud": [True]}))


def test_feature_columns_rejects_raw_identifiers() -> None:
    with pytest.raises(FeatureLeakage):
        feature_columns(pd.DataFrame({"amount": [1.0], "pan_token": ["tok_a"]}))
    assert feature_columns(pd.DataFrame({"amount": [1.0]})) == ["amount"]


def test_rolling_excludes_current_row() -> None:
    stamps = pd.to_datetime(
        ["2026-01-01T00:00:00Z", "2026-01-01T00:10:00Z", "2026-01-01T00:20:00Z"]
    )
    frame = pd.DataFrame(
        {"event_ts": stamps, "pan_token": ["a", "a", "a"], "amount": [1.0, 2.0, 3.0]}
    )
    counts = rolling_by_key(frame, "pan_token", "1h", "amount", "count").tolist()
    assert counts == [0.0, 1.0, 2.0]


def test_temporal_split_has_no_future_leakage() -> None:
    world = fixture_world()
    split = temporal_split(world.pool, SIM_START, world.config)
    assert split.train["event_ts"].max() < split.test["event_ts"].min()
    assert split.validation["event_ts"].max() < split.test["event_ts"].min()


def test_label_embargo_removes_recent_labels() -> None:
    world = fixture_world()
    split = temporal_split(world.pool, SIM_START, world.config)
    cutoff = pd.Timestamp(split.cutoff_ts)
    assert (pd.to_datetime(split.train["label_available_ts"], utc=True) <= cutoff).all()


def test_calibration_brier_improves() -> None:
    world = fixture_world()
    detector = Detector(world.config, sim_start=SIM_START).fit(world.pool)
    assert detector.brier_calibrated <= detector.brier_uncalibrated


def test_gnn_kill_rule_absolute() -> None:
    """Three absolute PR-AUC points, not three percent."""
    assert keeps_graph_channel(GNN_LIFT_ABOVE, GNN_KILL_THRESHOLD) is True
    assert keeps_graph_channel(GNN_LIFT_BELOW, GNN_KILL_THRESHOLD) is False
    # A three percent relative gain on a 0.72 baseline must not clear the bar.
    assert keeps_graph_channel(0.72 * 0.03, GNN_KILL_THRESHOLD) is False


def test_hot_path_imports() -> None:
    tree = ast.parse(BENCH_PATH.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert imported <= PERMITTED_HOT_PATH_IMPORTS, imported - PERMITTED_HOT_PATH_IMPORTS


def test_cart_hash_mismatch_fires_on_v19_only() -> None:
    injected = campaign_for("V19")
    assert float(cart_hash_mismatch(injected).mean()) == 1.0

    world = fixture_world()
    agentic = world.legit[world.legit["rail"] == "AGENTIC"]
    assert float(cart_hash_mismatch(agentic).sum()) == 0.0


def test_cost_threshold_is_grid_minimum() -> None:
    labels = np.array([0, 0, 1, 1, 0, 1, 0, 0])
    scores = np.array([0.05, 0.10, 0.80, 0.65, 0.20, 0.90, 0.02, 0.30])
    amounts = np.array([50.0, 90.0, 400.0, 120.0, 70.0, 900.0, 30.0, 60.0])
    matrix = CostMatrix()
    threshold = optimal_threshold(labels, scores, amounts, matrix)
    costs = [expected_cost(labels, scores, t, amounts, matrix) for t in THRESHOLD_GRID]
    assert expected_cost(labels, scores, threshold, amounts, matrix) == pytest.approx(min(costs))


def test_suspicious_pr_auc_is_flagged() -> None:
    world = fixture_world()
    leaky = world.pool.copy()
    # A deliberately leaky column: the label written straight into a feature.
    leaky["amount"] = np.where(leaky["is_fraud"], 999_999.0, leaky["amount"])
    detector = Detector(world.config, sim_start=SIM_START).fit(leaky)
    assert detector.suspicious_pr_auc == (detector.validation_pr_auc > SUSPICIOUS_PR_AUC)


def test_reliability_curve_covers_predictions() -> None:
    labels = np.array([0, 1, 0, 1, 1, 0])
    probabilities = np.array([0.05, 0.85, 0.15, 0.75, 0.95, 0.25])
    curve = reliability_curve(labels, probabilities)
    assert sum(row["count"] for row in curve) == labels.size


def test_features_are_point_in_time_for_a_single_entity() -> None:
    start = datetime(2026, 3, 1, tzinfo=UTC)
    frame = pd.DataFrame(
        {
            "event_id": ["a", "b", "c"],
            "event_ts": [start, start + timedelta(minutes=5), start + timedelta(minutes=9)],
            "payer_entity_id": ["CH_000001"] * 3,
            "payee_entity_id": ["MR_00001"] * 3,
            "amount": [10.0, 20.0, 30.0],
            "rail": ["CARD_CNP"] * 3,
            "cross_border": [False] * 3,
            "response_code": ["00"] * 3,
            "pan_token": ["tok_a"] * 3,
            "device_id": ["DV_000001"] * 3,
            "mcc": ["5411"] * 3,
            "is_fraud": [False] * 3,
        }
    )
    features = compute_features(frame)
    assert features["cnt_pan_token_1h"].tolist() == [0.0, 1.0, 2.0]
    assert features["first_time_payee"].tolist() == [1.0, 0.0, 0.0]
