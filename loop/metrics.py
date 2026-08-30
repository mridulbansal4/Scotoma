"""Round record construction and append."""

from datetime import UTC, datetime

from runtime.artifacts import append_jsonl

ROUNDS_FILE: str = "rounds.jsonl"
SSE_LOG_FILE: str = "sse_log.jsonl"

STATUS_COMPLETED: str = "COMPLETED"
STATUS_FIDELITY_REJECTED: str = "FIDELITY_REJECTED"
STATUS_NO_VALID_PROPOSALS: str = "NO_VALID_PROPOSALS"
STATUS_MODEL_REGRESSION: str = "MODEL_REGRESSION_KEPT_PREVIOUS"


class RoundMetrics:
    def __init__(self, run_id: str, coverage_pct: float, agent_mode: str) -> None:
        self.run_id = run_id
        self.coverage_pct = coverage_pct
        self.agent_mode = agent_mode

    def record(
        self,
        round_index: int,
        status: str,
        started: datetime,
        gate=None,
        active=None,
        blind=None,
        campaigns=None,
        hardest=None,
        rejected=None,
        detector=None,
        proposals_total: int = 0,
        latency_p99_ms: float | None = None,
    ) -> dict:
        hardest_ids = {str(c.campaign_id) for c in (hardest or [])}
        record = {
            "run_id": self.run_id,
            "round": round_index,
            "status": status,
            "ts_start": started.isoformat(),
            "ts_end": datetime.now(UTC).isoformat(),
            "agent_mode": self.agent_mode,
            "proposals_total": proposals_total,
            "proposals_valid": proposals_total - len(rejected or []),
            "proposals_rejected": [
                {"vector_id": item["vector_id"], "reason": item["reason"]}
                for item in (rejected or [])
            ],
            "campaigns": [
                {
                    "campaign_id": str(campaign.campaign_id),
                    "vector_id": campaign.vector_id,
                    "n_events": int(len(campaign.events)),
                    "evasion_rate": round(
                        float((active.evasion or {}).get(str(campaign.campaign_id), 0.0)), 4
                    )
                    if active
                    else None,
                    "selected_for_pool": str(campaign.campaign_id) in hardest_ids,
                }
                for campaign in (campaigns or [])
            ],
            "fidelity": gate.as_payload() if gate is not None else None,
            "fidelity_composite": round(gate.composite_behavioral, 4) if gate is not None else None,
            "evasion_active": round(active.evasion_rate, 4) if active else None,
            "evasion_blind": round(blind.evasion_rate, 4) if blind else None,
            "pr_auc": round(active.pr_auc, 4) if active else None,
            "pr_auc_blind": round(blind.pr_auc, 4) if blind else None,
            "fpr_legit": round(active.fpr_legit, 6) if active else None,
            "threshold": round(detector.threshold, 4) if detector else None,
            "cost_per_100k": round(active.cost_per_100k, 2) if active else None,
            "coverage_pct": self.coverage_pct,
            "latency_p99_ms": latency_p99_ms,
            "latency_source": "measured" if latency_p99_ms is not None else None,
            "model_retained": status != STATUS_MODEL_REGRESSION,
            "suspicious_pr_auc": bool(active.suspicious) if active else False,
            "per_vector_recall": {
                k: round(v, 4) for k, v in (active.per_vector_recall if active else {}).items()
            },
        }
        append_round(self.run_id, record)
        return record


def append_round(run_id: str, record: dict) -> None:
    append_jsonl(run_id, ROUNDS_FILE, record)
