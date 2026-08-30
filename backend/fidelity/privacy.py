"""Layer 6: membership inference against a shadow split, plus distance to closest record."""

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

from backend.fidelity.marginal import LayerResult, numeric_frame
from backend.runtime.config import PayLoopConfig
from backend.runtime.seeding import rng_for

FIDELITY_MIA_AUC_MIN: float = 0.50
FIDELITY_MIA_AUC_MAX: float = 0.55
FIDELITY_DCR_MIN: float = 0.0
MIA_MIN_ROWS: int = 5_000
MIA_SAMPLE_ROWS: int = 8_000
DCR_SAMPLE_ROWS: int = 8_000
INSUFFICIENT_DATA: str = "INSUFFICIENT_DATA"


EPOCH_SCALE_SECONDS: float = 1.0


def _matrix(frame: pd.DataFrame, size: int, rng: np.random.Generator) -> np.ndarray:
    """The distributional columns plus the event timestamp. A distance of zero then means
    the record itself was reproduced, not that two rows share a coarse bucket."""
    numeric = numeric_frame(frame)
    if numeric.empty:
        return np.empty((0, 0))
    numeric = numeric.assign(
        event_epoch=pd.to_datetime(frame["event_ts"], utc=True).astype("int64")
        / 1e9
        / EPOCH_SCALE_SECONDS
    )
    values = numeric.fillna(0.0).to_numpy("float64")
    if values.shape[0] > size:
        values = values[rng.choice(values.shape[0], size=size, replace=False)]
    return values


def distance_to_closest_record(batch: pd.DataFrame, reference: pd.DataFrame) -> float:
    """Zero means a training row was replicated verbatim."""
    rng = rng_for("fidelity:dcr")
    synthetic = _matrix(batch, DCR_SAMPLE_ROWS, rng)
    real = _matrix(reference, DCR_SAMPLE_ROWS, rng)
    if synthetic.size == 0 or real.size == 0:
        return 1.0
    scaler = StandardScaler().fit(real)
    neighbours = NearestNeighbors(n_neighbors=1).fit(scaler.transform(real))
    distances, _ = neighbours.kneighbors(scaler.transform(synthetic))
    return float(distances.min())


def membership_inference_auc(batch: pd.DataFrame, reference: pd.DataFrame) -> float:
    """Shadow attack: members are reference rows the generator saw, non-members are held
    out. The attack score is proximity to the nearest synthetic record."""
    rng = rng_for("fidelity:mia_shadow")
    real = _matrix(reference, MIA_SAMPLE_ROWS * 2, rng)
    synthetic = _matrix(batch, MIA_SAMPLE_ROWS, rng)
    if real.shape[0] < 4 or synthetic.size == 0:
        return 0.5
    split = real.shape[0] // 2
    members, non_members = real[:split], real[split:]
    scaler = StandardScaler().fit(synthetic)
    neighbours = NearestNeighbors(n_neighbors=1).fit(scaler.transform(synthetic))
    member_distance, _ = neighbours.kneighbors(scaler.transform(members))
    non_member_distance, _ = neighbours.kneighbors(scaler.transform(non_members))
    scores = -np.concatenate([member_distance.ravel(), non_member_distance.ravel()])
    labels = np.concatenate([np.ones(split), np.zeros(real.shape[0] - split)])
    auc = float(roc_auc_score(labels, scores))
    # An attacker can always invert the decision rule, so the advantage is one-sided. An
    # AUC of 0.49 is the same non-result as 0.51 and must not read as a failure.
    return max(auc, 1.0 - auc)


def evaluate(batch: pd.DataFrame, reference: pd.DataFrame, config: PayLoopConfig) -> LayerResult:
    min_dcr = distance_to_closest_record(batch, reference)
    dcr_ok = min_dcr > FIDELITY_DCR_MIN
    if len(batch) < config.mia_min_rows:
        # A shadow model on a few hundred rows returns noise, and reporting noise as an
        # AUC is worse than reporting nothing.
        return LayerResult(
            "privacy",
            bool(dcr_ok),
            {"min_dcr": round(min_dcr, 6)},
            f"mia {INSUFFICIENT_DATA} below {config.mia_min_rows} rows; min dcr {min_dcr:.4f}",
        )
    auc = membership_inference_auc(batch, reference)
    passed = dcr_ok and FIDELITY_MIA_AUC_MIN <= auc <= config.fidelity_mia_auc_max
    return LayerResult(
        "privacy",
        bool(passed),
        {"mia_auc": round(auc, 4), "min_dcr": round(min_dcr, 6)},
        f"mia auc {auc:.3f}; min dcr {min_dcr:.4f}",
    )


def mia_status(batch: pd.DataFrame, config: PayLoopConfig) -> str:
    return INSUFFICIENT_DATA if len(batch) < config.mia_min_rows else "EVALUATED"
