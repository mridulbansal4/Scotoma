import json
from datetime import UTC, datetime
from pathlib import Path

from backend.runtime.config import PayLoopConfig, load_config

REPO_ROOT: Path = Path(__file__).resolve().parent.parent.parent
RUNS_ROOT: Path = REPO_ROOT / "runs"


def run_dir(run_id: str | None = None) -> Path:
    target = RUNS_ROOT / (run_id or load_config().run_id)
    target.mkdir(parents=True, exist_ok=True)
    return target


def write_json(run_id: str, name: str, payload: dict | list) -> Path:
    path = run_dir(run_id) / name
    # sort_keys + indent so a committed artefact produces a readable diff.
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return path


def read_json(run_id: str, name: str) -> dict | list:
    return json.loads((run_dir(run_id) / name).read_text(encoding="utf-8"))


def append_jsonl(run_id: str, name: str, record: dict) -> None:
    path = run_dir(run_id) / name
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, default=str) + "\n")


def read_jsonl(run_id: str, name: str) -> list[dict]:
    path = run_dir(run_id) / name
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def reset_artifact(run_id: str, name: str) -> None:
    path = run_dir(run_id) / name
    if path.exists():
        path.unlink()


def write_manifest(run_id: str, config: PayLoopConfig, git_sha: str, host: str) -> Path:
    payload = {
        "run_id": run_id,
        "git_sha": git_sha,
        "host": host,
        "started_ts": datetime.now(UTC).isoformat(),
        "population_seed": config.population_seed,
        "sim_days": config.sim_days,
        "loop_rounds": config.loop_rounds,
        "label_embargo_days": config.label_embargo_days,
        "blind_holdout_vectors": config.blind_holdout_vector_ids,
        "blind_holdout_entity_frac": config.blind_holdout_entity_frac,
        "ladder_bands": {
            "approve_max": config.ladder_approve_max,
            "stepup_max": config.ladder_stepup_max,
            "hold_max": config.ladder_hold_max,
        },
        "cost_matrix": {
            "chargeback_fee": config.cost_chargeback_fee,
            "merchant_margin": config.cost_merchant_margin,
            "p_attrition": config.cost_p_attrition,
            "customer_ltv": config.cost_customer_ltv,
        },
        "gnn_enabled": config.gnn_enabled,
        "gnn_min_lift_prauc": config.gnn_min_lift_prauc,
        "config_hash": config_hash(config),
    }
    return write_json(run_id, "manifest.json", payload)


def config_hash(config: PayLoopConfig) -> str:
    import hashlib

    blob = json.dumps(config.model_dump(), sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
