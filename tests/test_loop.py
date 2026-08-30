"""Round count, artefact shape, and rejected-round handling on the committed run."""

import json
from pathlib import Path

import pytest

from api.events import EVENT_TYPES
from loop.metrics import (
    STATUS_COMPLETED,
    STATUS_FIDELITY_REJECTED,
    STATUS_MODEL_REGRESSION,
    STATUS_NO_VALID_PROPOSALS,
)
from runtime.artifacts import read_json, read_jsonl, run_dir
from runtime.config import load_config

MIN_ROUNDS: int = 5
VALID_STATUSES: frozenset[str] = frozenset(
    {STATUS_COMPLETED, STATUS_FIDELITY_REJECTED, STATUS_NO_VALID_PROPOSALS, STATUS_MODEL_REGRESSION}
)
SCORED_STATUSES: frozenset[str] = frozenset({STATUS_COMPLETED, STATUS_MODEL_REGRESSION})
REQUIRED_ARTEFACTS: tuple[str, ...] = (
    "manifest.json",
    "rounds.jsonl",
    "fidelity_report.json",
    "ablation.json",
    "coverage.json",
    "per_vector_recall.json",
    "scope_matrix.json",
    "reason_codes.json",
    "alerts.jsonl",
    "latency.json",
    "distributions.json",
    "sse_log.jsonl",
)

RUN_ID: str = load_config().run_id
ROUNDS_PATH: Path = run_dir(RUN_ID) / "rounds.jsonl"
committed_run = pytest.mark.skipif(
    not ROUNDS_PATH.exists(), reason=f"no committed run at runs/{RUN_ID}"
)


def _rounds() -> list[dict]:
    return read_jsonl(RUN_ID, "rounds.jsonl")


@committed_run
def test_loop_completes_minimum_rounds() -> None:
    assert len(_rounds()) >= MIN_ROUNDS


@committed_run
def test_every_round_reports_blind_evasion() -> None:
    for record in _rounds():
        if record["status"] in SCORED_STATUSES:
            assert record["evasion_blind"] is not None, record["round"]


@committed_run
def test_every_round_reports_fidelity_composite() -> None:
    for record in _rounds():
        if record["status"] != STATUS_NO_VALID_PROPOSALS:
            assert record["fidelity_composite"] is not None, record["round"]


@committed_run
def test_rejected_round_has_null_metrics() -> None:
    rejected = [r for r in _rounds() if r["status"] == STATUS_FIDELITY_REJECTED]
    for record in rejected:
        assert record["pr_auc"] is None
        assert record["evasion_active"] is None
        assert record["cost_per_100k"] is None


@committed_run
def test_fpr_is_recorded_every_round() -> None:
    for record in _rounds():
        if record["status"] in SCORED_STATUSES:
            assert record["fpr_legit"] is not None, record["round"]


@committed_run
def test_every_round_status_is_known() -> None:
    assert {r["status"] for r in _rounds()} <= VALID_STATUSES


@committed_run
def test_run_writes_every_artefact() -> None:
    missing = [name for name in REQUIRED_ARTEFACTS if not (run_dir(RUN_ID) / name).exists()]
    assert not missing, missing


@committed_run
def test_sse_log_contains_a_rejected_proposal() -> None:
    """The most compelling twenty seconds of the demo has to exist in the committed log."""
    events = {record["event"] for record in read_jsonl(RUN_ID, "sse_log.jsonl")}
    assert "proposal_rejected" in events
    assert events <= set(EVENT_TYPES)


@committed_run
def test_latency_is_measured_not_targeted() -> None:
    latency = read_json(RUN_ID, "latency.json")
    assert latency["source"] == "measured"
    for percentile in ("p50_ms", "p95_ms", "p99_ms"):
        assert latency[percentile] > 0.0
    assert latency["host"]
    assert latency["targets"]


@committed_run
def test_manifest_records_provenance() -> None:
    manifest = read_json(RUN_ID, "manifest.json")
    for key in ("git_sha", "host", "population_seed", "config_hash", "ladder_bands"):
        assert manifest[key] not in (None, "")


def test_no_valid_proposals_does_not_crash() -> None:
    """Forcing every proposal invalid yields NO_VALID_PROPOSALS rather than an exception."""
    from generate.red_agent.constraints import Proposal, partition_valid

    proposals = [
        Proposal("V01", {"probes_per_min": -1.0}, "invalid"),
        Proposal("V99", {}, "unknown"),
    ]
    valid, rejected = partition_valid(proposals)
    assert valid == []
    assert len(rejected) == 2
    assert all(item["rule"] for item in rejected)


@committed_run
def test_alerts_carry_reason_codes_and_bands() -> None:
    alerts = read_jsonl(RUN_ID, "alerts.jsonl")
    assert alerts
    for alert in alerts[:20]:
        assert alert["reason_codes"]
        assert alert["band"]
        assert alert["action"]


@committed_run
def test_rounds_are_json_serialisable_records() -> None:
    for record in _rounds():
        json.dumps(record)
