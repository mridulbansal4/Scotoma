"""POST /simulate and GET /simulate/status/{task_id}."""

from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.api.jobs import enqueue, fetch, queue_depth
from backend.generate.injectors import INJECTORS

router = APIRouter()

SIMULATE_JOB: str = "loop.controller.simulate_batch"
MIN_DAYS: int = 1
MAX_DAYS: int = 180
MIN_INTENSITY: float = 0.1
MAX_INTENSITY: float = 1.0


class SimulateRequest(BaseModel):
    vectors: list[str] = Field(min_length=1)
    days: int = Field(ge=MIN_DAYS, le=MAX_DAYS)
    intensity: float = Field(ge=MIN_INTENSITY, le=MAX_INTENSITY)
    seed: int | None = None


class SimulateAccepted(BaseModel):
    task_id: str
    status: str
    queue_depth: int
    message: str


class SimulateStatus(BaseModel):
    task_id: str
    status: str
    started_ts: str | None = None
    finished_ts: str | None = None
    result: dict | None = None
    error: dict | None = None


@router.post("/simulate", status_code=202, response_model=SimulateAccepted)
async def submit_simulation(request: SimulateRequest) -> SimulateAccepted:
    unknown = [vector for vector in request.vectors if vector not in INJECTORS]
    if unknown:
        raise ValueError(f"no injector for vectors {unknown}")
    task_id = enqueue(SIMULATE_JOB, request.model_dump())
    return SimulateAccepted(
        task_id=task_id,
        status="QUEUED",
        queue_depth=queue_depth(),
        message="Simulation queued.",
    )


@router.get("/simulate/status/{task_id}", response_model=SimulateStatus)
async def simulation_status(task_id: UUID) -> SimulateStatus:
    record = fetch(task_id)
    return SimulateStatus(
        task_id=str(record.task_id),
        status=record.status,
        started_ts=record.started_ts.isoformat() if record.started_ts else None,
        finished_ts=record.finished_ts.isoformat() if record.finished_ts else None,
        result=record.result,
        error={"detail": record.error} if record.error else None,
    )
