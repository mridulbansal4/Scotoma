"""Channel B: PageRank plus neighbour-aggregated features into a second LightGBM.

Built as an offline batch job. In production it would sit on a stream at 30 seconds to
5 minutes of lag; it is never inline, because a multi-hop graph fetch cannot meet an
authorisation sub-budget.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier

from backend.runtime.config import PayLoopConfig

GRAPH_FEATURE_COLUMNS: tuple[str, ...] = (
    "fanin_payee_24h",
    "fanout_payer_24h",
    "payee_bank_degree",
    "payer_pagerank",
    "payee_pagerank",
    "component_size",
    "cnt_payee_entity_id_24h",
    "sum_payee_entity_id_24h",
    "amtstd_payee_entity_id_24h",
    "declrate_payee_entity_id_24h",
)
NEIGHBOUR_AGGREGATIONS: tuple[str, ...] = ("mean", "max", "std")
GRAPH_N_ESTIMATORS: int = 300
GRAPH_NUM_LEAVES: int = 31


@dataclass
class ChannelBResult:
    model: LGBMClassifier
    columns: list[str]


def neighbour_aggregate(features: pd.DataFrame, keys: pd.Series) -> pd.DataFrame:
    """Aggregate a row's graph features over the other rows sharing its payee, which is
    the neighbour-aggregation that boosted trees exploit better than a deep graph model."""
    available = [c for c in GRAPH_FEATURE_COLUMNS if c in features.columns]
    if not available:
        return pd.DataFrame(index=features.index)
    working = features[available].copy()
    working["_key"] = keys.to_numpy()
    grouped = working.groupby("_key", sort=False)[available]
    blocks = {}
    for aggregation in NEIGHBOUR_AGGREGATIONS:
        transformed = grouped.transform(aggregation)
        for column in available:
            blocks[f"nb{aggregation}_{column}"] = transformed[column].to_numpy()
    return pd.DataFrame(blocks, index=features.index).astype("float32").fillna(0.0)


def build_design(features: pd.DataFrame, keys: pd.Series) -> pd.DataFrame:
    available = [c for c in GRAPH_FEATURE_COLUMNS if c in features.columns]
    return pd.concat([features[available], neighbour_aggregate(features, keys)], axis=1)


def fit_channel_b(
    design: pd.DataFrame, labels: np.ndarray, config: PayLoopConfig
) -> ChannelBResult:
    positives = max(int(labels.sum()), 1)
    negatives = int((labels == 0).sum())
    model = LGBMClassifier(
        learning_rate=config.lgbm_learning_rate,
        num_leaves=GRAPH_NUM_LEAVES,
        n_estimators=GRAPH_N_ESTIMATORS,
        min_child_samples=config.lgbm_min_child_samples,
        scale_pos_weight=max(negatives / positives, 1.0),
        objective="binary",
        n_jobs=-1,
        verbose=-1,
    )
    model.fit(design.to_numpy("float32"), labels)
    return ChannelBResult(model=model, columns=list(design.columns))


def score_channel_b(result: ChannelBResult, design: pd.DataFrame) -> np.ndarray:
    aligned = design.reindex(columns=result.columns, fill_value=0.0)
    return result.model.predict_proba(aligned.to_numpy("float32"))[:, 1]
