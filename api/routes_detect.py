"""POST /detect/score — the inline scoring path exposed over HTTP."""

import time
from functools import lru_cache

import numpy as np
import pandas as pd
from fastapi import APIRouter
from pydantic import BaseModel

from defend.bench import calibrated_score, cart_hash_matches, load_session
from defend.ensemble import ARTIFACTS_DIR, MODEL_FILENAME, THRESHOLD_FILENAME
from defend.explain import reason_for
from defend.features import FEATURE_NAMES, compute_features
from defend.gbdt import load_threshold_artifact
from defend.ladder import action_for_band, band_for_score
from runtime.config import load_config
from runtime.errors import LatencyBudgetExceeded, ModelArtifactMissing
from schema.ces import CanonicalEvent

router = APIRouter()

LATENCY_BUDGET_MULTIPLIER: float = 20.0
MILLISECONDS_PER_SECOND: float = 1000.0
TOP_REASON_COUNT: int = 3


class ScoreResponse(BaseModel):
    event_id: str
    score: float
    band: str
    action: str
    threshold: float
    channels: dict[str, float]
    invariants: dict[str, bool]
    reason_codes: list[dict]
    latency_ms: float
    latency_source: str


@lru_cache(maxsize=1)
def _scorer() -> tuple[object, dict]:
    model_path = ARTIFACTS_DIR / MODEL_FILENAME
    if not model_path.exists():
        raise ModelArtifactMissing(f"model artefact missing at {model_path}")
    artefact = load_threshold_artifact(ARTIFACTS_DIR / THRESHOLD_FILENAME)
    return load_session(str(model_path)), artefact


def _invariants(features: pd.Series) -> dict[str, bool]:
    return {
        "cart_hash_match": bool(features["cart_hash_mismatch"] == 0),
        "mandate_in_scope": bool(features["mandate_scope_breach"] == 0),
        "nonce_reused": bool(features["nonce_reused"] == 1),
        "attestation_valid": bool(features["attestation_invalid"] == 0),
    }


def _reason_codes(features: pd.Series) -> list[dict]:
    """Without the training background the API reports the invariant-bearing features that
    actually fired, ranked by magnitude, rather than a fabricated SHAP attribution."""
    ranked = features.reindex(FEATURE_NAMES).abs().sort_values(ascending=False)
    reasons = []
    for feature in ranked.index[:TOP_REASON_COUNT]:
        code, label = reason_for(str(feature))
        reasons.append(
            {
                "code": code,
                "label": label,
                "feature": str(feature),
                "value": float(features[feature]),
                "shap": None,
            }
        )
    return reasons


@router.post("/detect/score", response_model=ScoreResponse)
async def score_event(event: CanonicalEvent) -> ScoreResponse:
    session, artefact = _scorer()
    config = load_config()
    frame = pd.DataFrame([event.model_dump()])
    frame["event_ts"] = pd.to_datetime(frame["event_ts"], utc=True)

    started = time.perf_counter()
    features = compute_features(frame)
    row = features.iloc[0]
    design = np.ascontiguousarray(features.to_numpy("float32"))
    raw = calibrated_score(session, design, artefact["platt_a"], artefact["platt_b"])
    elapsed_ms = (time.perf_counter() - started) * MILLISECONDS_PER_SECOND

    budget = config.scoring_latency_budget_ms * LATENCY_BUDGET_MULTIPLIER
    if elapsed_ms > budget:
        raise LatencyBudgetExceeded(f"scoring took {elapsed_ms:.1f} ms against {budget:.1f} ms")

    band = band_for_score(raw)
    invariants = _invariants(row)
    if event.cart_hash_at_intent and event.cart_hash_at_settle:
        invariants["cart_hash_match"] = cart_hash_matches(
            event.cart_hash_at_intent, event.cart_hash_at_settle
        )
    return ScoreResponse(
        event_id=str(event.event_id),
        score=round(raw, 4),
        band=str(band),
        action=action_for_band(band),
        threshold=float(artefact["threshold"]),
        channels={"gbdt": round(raw, 4)},
        invariants=invariants,
        reason_codes=_reason_codes(row),
        latency_ms=round(elapsed_ms, 3),
        latency_source="measured",
    )
