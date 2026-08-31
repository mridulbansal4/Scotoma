"""IBM AML HI-Small: Channel B scoping, and a measured negative result.

Per the appendix ruling, this corpus is not for training a graph model in the time
available. It is here to answer one question with a number instead of an opinion: is there
enough signal in pure account-graph structure to justify a graph channel at all?

The method is deliberately the cheapest thing that could work. Degree and reciprocity
features only, no embeddings, no neighbour sampling, no GNN. If coordinated laundering
structure is separable at all, a gradient boosting model over degree features will find
some of it, and that PR-AUC is the floor any graph channel has to beat to be worth its
complexity. If even that floor is near the base rate, the negative result is real and
publishing it beats shipping a decorative model.

Multi-currency is normalised before any amount feature. Summing US Dollar and Euro rows
into one velocity total produces a number that means nothing.
"""

from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.metrics import average_precision_score, roc_auc_score

from backend.runtime.errors import RegistryInvalid

SOURCE_COLUMN: str = "Account"
TARGET_COLUMN: str = "Account.1"
LABEL_COLUMN: str = "Is Laundering"
AMOUNT_PAID: str = "Amount Paid"
PAYMENT_CURRENCY: str = "Payment Currency"
TIMESTAMP: str = "Timestamp"

# Rates to a common unit. HI-Small is dominated by US Dollar; the rest are normalised so
# that an amount feature is comparable across rows rather than silently mixing units.
CURRENCY_TO_USD: dict[str, float] = {
    "US Dollar": 1.00,
    "Euro": 1.09,
    "Yuan": 0.14,
    "Yen": 0.0067,
    "Swiss Franc": 1.12,
    "UK Pound": 1.27,
    "Canadian Dollar": 0.74,
    "Australian Dollar": 0.66,
    "Rupee": 0.012,
    "Ruble": 0.011,
    "Brazil Real": 0.20,
    "Mexican Peso": 0.058,
    "Saudi Riyal": 0.27,
    "Shekel": 0.27,
    "Bitcoin": 60000.0,
}
DEFAULT_RATE: float = 1.0

GRAPH_FEATURES: tuple[str, ...] = (
    "src_out_degree",
    "src_in_degree",
    "dst_out_degree",
    "dst_in_degree",
    "src_unique_targets",
    "dst_unique_sources",
    "is_reciprocated",
    "is_self_loop",
    "src_fanout_ratio",
    "dst_fanin_ratio",
    "amount_usd_log",
)


def read_aml(path: Path, rows: int | None = None) -> pd.DataFrame:
    frame = pd.read_csv(path, nrows=rows, low_memory=False)
    # pandas de-duplicates the two identically named Account columns to Account/Account.1.
    for column in (SOURCE_COLUMN, TARGET_COLUMN, LABEL_COLUMN):
        if column not in frame.columns:
            raise RegistryInvalid(f"{path.name} is not IBM AML HI-Small; missing {column}")
    return frame


def normalise_amount(frame: pd.DataFrame) -> np.ndarray:
    rates = frame[PAYMENT_CURRENCY].map(CURRENCY_TO_USD).fillna(DEFAULT_RATE).to_numpy("float64")
    paid = pd.to_numeric(frame[AMOUNT_PAID], errors="coerce").fillna(0.0).to_numpy("float64")
    return paid * rates


def motif_census(frame: pd.DataFrame) -> dict:
    """Degree and reciprocity structure, split by label.

    These are the observable shadows of Altman's eight patterns: fan-in and fan-out are
    degree, cycles and scatter-gather show up as reciprocity and as accounts that are both
    high in-degree and high out-degree.
    """
    source = frame[SOURCE_COLUMN].astype("string")
    target = frame[TARGET_COLUMN].astype("string")
    labels = frame[LABEL_COLUMN].to_numpy("int8")

    out_degree = source.value_counts()
    in_degree = target.value_counts()
    pairs = pd.Series(list(zip(source, target)))
    reverse = set(zip(target, source))
    reciprocated = pairs.map(lambda edge: edge in reverse).to_numpy()

    def summarise(mask: np.ndarray, name: str) -> dict:
        subset = frame[mask]
        if subset.empty:
            return {"label": name, "edges": 0}
        src = subset[SOURCE_COLUMN].astype("string")
        dst = subset[TARGET_COLUMN].astype("string")
        return {
            "label": name,
            "edges": int(mask.sum()),
            "unique_sources": int(src.nunique()),
            "unique_targets": int(dst.nunique()),
            "mean_src_out_degree": round(float(out_degree.reindex(src).mean()), 3),
            "mean_dst_in_degree": round(float(in_degree.reindex(dst).mean()), 3),
            "max_src_out_degree": int(out_degree.reindex(src).max()),
            "max_dst_in_degree": int(in_degree.reindex(dst).max()),
            "reciprocated_share": round(float(reciprocated[mask].mean()), 5),
            "self_loop_share": round(float((src.to_numpy() == dst.to_numpy()).mean()), 5),
        }

    return {
        "accounts": int(pd.concat([source, target]).nunique()),
        "edges": int(len(frame)),
        "laundering": summarise(labels == 1, "laundering"),
        "legitimate": summarise(labels == 0, "legitimate"),
    }


def build_graph_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Degree, reciprocity and normalised amount. No embeddings, deliberately."""
    source = frame[SOURCE_COLUMN].astype("string")
    target = frame[TARGET_COLUMN].astype("string")

    out_degree = source.value_counts()
    in_degree = target.value_counts()
    unique_targets = frame.groupby(SOURCE_COLUMN)[TARGET_COLUMN].nunique()
    unique_sources = frame.groupby(TARGET_COLUMN)[SOURCE_COLUMN].nunique()
    reverse = set(zip(target, source))

    src_out = out_degree.reindex(source).to_numpy("float32")
    src_in = in_degree.reindex(source).fillna(0).to_numpy("float32")
    dst_out = out_degree.reindex(target).fillna(0).to_numpy("float32")
    dst_in = in_degree.reindex(target).to_numpy("float32")
    src_uniq = unique_targets.reindex(source).fillna(0).to_numpy("float32")
    dst_uniq = unique_sources.reindex(target).fillna(0).to_numpy("float32")

    amount = normalise_amount(frame)
    return pd.DataFrame(
        {
            "src_out_degree": src_out,
            "src_in_degree": src_in,
            "dst_out_degree": dst_out,
            "dst_in_degree": dst_in,
            "src_unique_targets": src_uniq,
            "dst_unique_sources": dst_uniq,
            "is_reciprocated": np.fromiter(
                ((s, t) in reverse for s, t in zip(target, source)), dtype="float32", count=len(frame)
            ),
            "is_self_loop": (source.to_numpy() == target.to_numpy()).astype("float32"),
            # Fan-out concentration: many edges to few distinct targets is a stacking shape.
            "src_fanout_ratio": src_out / np.maximum(src_uniq, 1.0),
            "dst_fanin_ratio": dst_in / np.maximum(dst_uniq, 1.0),
            "amount_usd_log": np.log1p(np.maximum(amount, 0.0)).astype("float32"),
        },
        index=frame.index,
    )


def scope_channel_b(frame: pd.DataFrame, min_lift: float) -> dict:
    """Measure the graph-only PR-AUC and compare it to the lift bar.

    The split is temporal on Timestamp. A random split across a graph leaks: the same
    account appears on both sides and the model memorises accounts rather than structure.
    """
    ordered = frame.sort_values(TIMESTAMP).reset_index(drop=True)
    matrix = build_graph_features(ordered)
    labels = ordered[LABEL_COLUMN].to_numpy("int8")

    cut = int(len(ordered) * 0.7)
    train_x, train_y = matrix.iloc[:cut].to_numpy("float32"), labels[:cut]
    test_x, test_y = matrix.iloc[cut:].to_numpy("float32"), labels[cut:]

    positives = int(train_y.sum())
    if positives < 30:
        raise RegistryInvalid(f"only {positives} laundering rows in the AML training window")

    booster = LGBMClassifier(
        n_estimators=300,
        learning_rate=0.05,
        num_leaves=63,
        scale_pos_weight=max(int((train_y == 0).sum()) / max(positives, 1), 1.0),
        objective="binary",
        n_jobs=-1,
        verbose=-1,
    )
    booster.fit(train_x, train_y)
    scores = booster.predict_proba(test_x)[:, 1]

    base_rate = float(test_y.mean())
    pr_auc = float(average_precision_score(test_y, scores))
    importance = dict(
        sorted(
            zip(GRAPH_FEATURES, booster.feature_importances_.tolist()),
            key=lambda item: item[1],
            reverse=True,
        )
    )
    return {
        "corpus": "ibm_aml_hi_small",
        "is_observed_data": False,
        "edges": int(len(ordered)),
        "train_rows": int(len(train_y)),
        "test_rows": int(len(test_y)),
        "test_base_rate": round(base_rate, 6),
        "graph_only_pr_auc": round(pr_auc, 4),
        "graph_only_roc_auc": round(float(roc_auc_score(test_y, scores)), 4),
        "lift_over_base_rate": round(pr_auc - base_rate, 4),
        "lift_bar": min_lift,
        "clears_lift_bar": bool(pr_auc - base_rate >= min_lift),
        "feature_importance": importance,
    }
