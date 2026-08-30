"""RQ queue wiring and job status lookup. Redis holds queue state only; run artefacts
are always written to disk."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from redis.exceptions import RedisError
from rq import Queue
from rq.exceptions import NoSuchJobError
from rq.job import Job

from backend.runtime.errors import WarehouseUnavailable
from backend.runtime.redis_store import redis_client

QUEUE_NAME: str = "payloop"
QUEUE_MAX_DEPTH: int = 32
SIMULATION_TIMEOUT_S: float = 900.0
ROUND_TIMEOUT_S: float = 1800.0

JobStatus = Literal["QUEUED", "RUNNING", "COMPLETED", "FAILED"]

RQ_STATUS_MAP: dict[str, JobStatus] = {
    "queued": "QUEUED",
    "deferred": "QUEUED",
    "scheduled": "QUEUED",
    "started": "RUNNING",
    "finished": "COMPLETED",
    "failed": "FAILED",
    "stopped": "FAILED",
    "canceled": "FAILED",
}


@dataclass(frozen=True)
class JobRecord:
    task_id: UUID
    status: JobStatus
    started_ts: datetime | None
    finished_ts: datetime | None
    result: dict | None
    error: str | None


def queue() -> Queue:
    try:
        return Queue(QUEUE_NAME, connection=redis_client())
    except RedisError as exc:
        raise WarehouseUnavailable(f"redis unreachable: {exc}") from exc


def queue_depth() -> int:
    try:
        return len(queue())
    except RedisError as exc:
        raise WarehouseUnavailable(f"redis unreachable: {exc}") from exc


def enqueue(function_path: str, payload: dict, timeout: float = SIMULATION_TIMEOUT_S) -> str:
    active = queue()
    if len(active) >= QUEUE_MAX_DEPTH:
        raise QueueFull(f"queue depth {len(active)} at capacity {QUEUE_MAX_DEPTH}")
    job = active.enqueue(function_path, payload, job_timeout=timeout)
    return str(job.id)


def fetch(task_id: UUID) -> JobRecord:
    try:
        job = Job.fetch(str(task_id), connection=redis_client())
    except RedisError as exc:
        raise WarehouseUnavailable(f"redis unreachable: {exc}") from exc
    except NoSuchJobError as exc:
        raise JobNotFound(str(task_id)) from exc
    status = RQ_STATUS_MAP.get(job.get_status(refresh=True), "QUEUED")
    return JobRecord(
        task_id=task_id,
        status=status,
        started_ts=job.started_at.replace(tzinfo=UTC) if job.started_at else None,
        finished_ts=job.ended_at.replace(tzinfo=UTC) if job.ended_at else None,
        result=job.result if status == "COMPLETED" else None,
        error=str(job.latest_result().exc_string) if status == "FAILED" else None,
    )


class QueueFull(WarehouseUnavailable):
    pass


class JobNotFound(WarehouseUnavailable):
    pass
