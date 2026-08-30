"""POST /loop/run and the SSE stream at GET /loop/stream/{run_id}."""

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from api.jobs import ROUND_TIMEOUT_S, enqueue, queue
from runtime.artifacts import read_jsonl, run_dir
from runtime.config import load_config
from runtime.errors import PayLoopError

router = APIRouter()

LOOP_JOB: str = "loop.controller.run_from_request"
SSE_LOG_FILE: str = "sse_log.jsonl"
REPLAY_INTERVAL_MS: int = 400
SSE_KEEPALIVE_S: float = 15.0
MIN_ROUNDS: int = 1
MAX_ROUNDS: int = 20
MIN_PROPOSALS: int = 1
MAX_PROPOSALS: int = 12


class LoopAlreadyRunning(PayLoopError):
    pass


class RunNotFound(PayLoopError):
    pass


class LoopRunRequest(BaseModel):
    run_id: str
    rounds: int = Field(ge=MIN_ROUNDS, le=MAX_ROUNDS)
    proposals_per_round: int = Field(ge=MIN_PROPOSALS, le=MAX_PROPOSALS)
    agent_mode: str = "offline"


class LoopAccepted(BaseModel):
    run_id: str
    status: str
    rounds: int
    stream_url: str


def _run_in_progress(run_id: str) -> bool:
    return any(job.args and job.args[0].get("run_id") == run_id for job in queue().get_jobs())


@router.post("/loop/run", status_code=202, response_model=LoopAccepted)
async def start_loop(request: LoopRunRequest) -> LoopAccepted:
    if _run_in_progress(request.run_id):
        raise LoopAlreadyRunning(f"a loop run is already queued for {request.run_id}")
    enqueue(LOOP_JOB, request.model_dump(), timeout=ROUND_TIMEOUT_S * request.rounds)
    return LoopAccepted(
        run_id=request.run_id,
        status="RUNNING",
        rounds=request.rounds,
        stream_url=f"/api/v1/loop/stream/{request.run_id}",
    )


async def _replay(run_id: str) -> AsyncIterator[dict]:
    """Replaying the committed log is what makes the console work with the cable pulled."""
    for record in read_jsonl(run_id, SSE_LOG_FILE):
        yield {"event": record["event"], "data": json.dumps(record["data"], sort_keys=True)}
        await asyncio.sleep(REPLAY_INTERVAL_MS / 1000.0)


@router.get("/loop/stream/{run_id}")
async def loop_stream(run_id: str) -> EventSourceResponse:
    if not (run_dir(run_id) / SSE_LOG_FILE).exists():
        raise RunNotFound(f"no event log at runs/{run_id}/{SSE_LOG_FILE}")
    load_config()
    return EventSourceResponse(_replay(run_id), ping=int(SSE_KEEPALIVE_S))
