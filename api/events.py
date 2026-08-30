"""SSE event constructors, one per event type. The committed sse_log.jsonl replays these."""

from datetime import UTC, datetime

EVENT_ROUND_START: str = "round_start"
EVENT_PROPOSAL: str = "proposal"
EVENT_PROPOSAL_REJECTED: str = "proposal_rejected"
EVENT_FIDELITY: str = "fidelity"
EVENT_ROUND_RESULT: str = "round_result"
EVENT_ROUND_REJECTED: str = "round_rejected"
EVENT_DONE: str = "done"

EVENT_TYPES: tuple[str, ...] = (
    EVENT_ROUND_START,
    EVENT_PROPOSAL,
    EVENT_PROPOSAL_REJECTED,
    EVENT_FIDELITY,
    EVENT_ROUND_RESULT,
    EVENT_ROUND_REJECTED,
    EVENT_DONE,
)


def envelope(event: str, data: dict) -> dict:
    return {"event": event, "data": data}


def round_start(run_id: str, round_index: int, agent_mode: str, state) -> dict:
    return envelope(
        EVENT_ROUND_START,
        {
            "run_id": run_id,
            "round": round_index,
            "ts": datetime.now(UTC).isoformat(),
            "agent_mode": agent_mode,
            "threshold": round(state.threshold, 4),
            "top_shap_features": state.top_shap_features[:3],
            "per_vector_recall": {k: round(v, 4) for k, v in state.per_vector_recall.items()},
        },
    )


def proposal(round_index: int, index: int, item) -> dict:
    return envelope(
        EVENT_PROPOSAL,
        {
            "round": round_index,
            "index": index,
            "vector_id": item.vector_id,
            "valid": True,
            "params": item.params,
            "rationale": item.rationale,
        },
    )


def proposal_rejected(round_index: int, rejection: dict) -> dict:
    return envelope(
        EVENT_PROPOSAL_REJECTED,
        {
            "round": round_index,
            "index": rejection["index"],
            "vector_id": rejection["vector_id"],
            "reason": rejection["reason"],
            "rule": rejection["rule"],
            "params": rejection["params"],
        },
    )


def fidelity(round_index: int, gate) -> dict:
    return envelope(
        EVENT_FIDELITY,
        {
            "round": round_index,
            "passed": gate.passed,
            "composite_behavioral": round(gate.composite_behavioral, 4),
            "shadow_layer": gate.shadow_layer,
            "shadow_failure": gate.shadow_failure,
            "layers": {name: result.passed for name, result in gate.layers.items()},
        },
    )


def round_result(record: dict) -> dict:
    keys = (
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
        "coverage_pct",
        "latency_p99_ms",
        "latency_source",
        "model_retained",
    )
    return envelope(EVENT_ROUND_RESULT, {key: record.get(key) for key in keys})


def round_rejected(round_index: int, gate) -> dict:
    hints = gate.failure_hints()
    return envelope(
        EVENT_ROUND_REJECTED,
        {
            "round": round_index,
            "status": "FIDELITY_REJECTED",
            "failed_layers": gate.failed_layers(),
            "composite_behavioral": round(gate.composite_behavioral, 4),
            "hint": hints[0] if hints else "gate failed without a recorded hint",
        },
    )


def done(
    run_id: str, rounds_completed: int, rounds_rejected: int, gnn: dict, artifacts: list[str]
) -> dict:
    return envelope(
        EVENT_DONE,
        {
            "run_id": run_id,
            "rounds_completed": rounds_completed,
            "rounds_rejected": rounds_rejected,
            "gnn_enabled": gnn.get("enabled", False),
            "gnn_measured_lift_pr_auc": gnn.get("measured_lift_pr_auc"),
            "artifacts": artifacts,
        },
    )
