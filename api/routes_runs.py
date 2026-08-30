"""GET /runs/{run_id}/metrics."""

from fastapi import APIRouter
from pydantic import BaseModel

from runtime.artifacts import read_json, read_jsonl, run_dir
from runtime.config import load_config
from runtime.errors import PayLoopError

router = APIRouter()

ROUND_KEYS: tuple[str, ...] = (
    "round",
    "status",
    "evasion_active",
    "evasion_blind",
    "pr_auc",
    "pr_auc_blind",
    "fpr_legit",
    "fidelity_composite",
    "cost_per_100k",
    "threshold",
    "latency_p99_ms",
)


class RunNotFound(PayLoopError):
    pass


class RunMetrics(BaseModel):
    run_id: str
    rounds: list[dict]
    per_vector_recall: dict
    scope_matrix: dict
    gnn: dict
    latency: dict
    holdout: dict


def _optional_json(run_id: str, name: str) -> dict:
    if not (run_dir(run_id) / name).exists():
        return {}
    payload = read_json(run_id, name)
    return payload if isinstance(payload, dict) else {}


@router.get("/runs/{run_id}/metrics", response_model=RunMetrics)
async def run_metrics(run_id: str) -> RunMetrics:
    if not (run_dir(run_id) / "rounds.jsonl").exists():
        raise RunNotFound(f"no run artefacts at runs/{run_id}")
    config = load_config()
    records = read_jsonl(run_id, "rounds.jsonl")
    rounds = [{key: record.get(key) for key in ROUND_KEYS} for record in records]
    recall = _optional_json(run_id, "per_vector_recall.json")
    scope = _optional_json(run_id, "scope_matrix.json")
    return RunMetrics(
        run_id=run_id,
        rounds=rounds,
        per_vector_recall=recall,
        scope_matrix=scope.get("matrix", {}),
        gnn=_optional_json(run_id, "gnn.json"),
        latency=_optional_json(run_id, "latency.json"),
        holdout={
            "vectors": config.blind_holdout_vector_ids,
            "entity_fraction": config.blind_holdout_entity_frac,
            "description": (
                "One attack family and one entity cohort, neither of which enters any "
                "training pool."
            ),
        },
    )
