"""FastAPI app factory, the single exception boundary, and router mounting."""

import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from api import routes_detect, routes_loop, routes_registry, routes_runs, routes_simulate
from api.errors import (
    CODE_BAD_REQUEST,
    CODE_CONFLICT,
    CODE_INTERNAL,
    CODE_NOT_FOUND,
    CODE_QUEUE_FULL,
    CODE_UNAVAILABLE,
    code_for,
    envelope,
    status_for,
)
from api.jobs import JobNotFound, QueueFull
from api.routes_loop import LoopAlreadyRunning
from api.routes_loop import RunNotFound as StreamNotFound
from api.routes_runs import RunNotFound
from runtime.errors import PayLoopError

API_PREFIX: str = "/api/v1"
API_TITLE: str = "PayLoop"
API_VERSION: str = "1.0.0"
QUEUE_MAX_DEPTH: int = 32
REPLAY_INTERVAL_MS: int = 400
SSE_KEEPALIVE_S: float = 15.0

LOGGER = logging.getLogger("payloop.api")

ROUTE_EXCEPTION_CODES: dict[type[PayLoopError], str] = {
    LoopAlreadyRunning: CODE_CONFLICT,
    QueueFull: CODE_QUEUE_FULL,
    JobNotFound: CODE_NOT_FOUND,
    RunNotFound: CODE_NOT_FOUND,
    StreamNotFound: CODE_NOT_FOUND,
}


def _code_for_route_error(error: PayLoopError) -> str:
    for exception_type, code in ROUTE_EXCEPTION_CODES.items():
        if isinstance(error, exception_type):
            return code
    return code_for(error)


def create_app() -> FastAPI:
    app = FastAPI(title=API_TITLE, version=API_VERSION)
    for module in (
        routes_simulate,
        routes_loop,
        routes_detect,
        routes_registry,
        routes_runs,
    ):
        app.include_router(module.router, prefix=API_PREFIX)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        code = CODE_BAD_REQUEST
        return JSONResponse(status_code=status_for(code), content=envelope(code, str(exc.errors())))

    @app.exception_handler(ValueError)
    async def _value_error(request: Request, exc: ValueError) -> JSONResponse:
        code = CODE_BAD_REQUEST
        return JSONResponse(status_code=status_for(code), content=envelope(code, str(exc)))

    @app.exception_handler(PayLoopError)
    async def _payloop_error(request: Request, exc: PayLoopError) -> JSONResponse:
        code = _code_for_route_error(exc)
        return JSONResponse(status_code=status_for(code), content=envelope(code, str(exc)))

    # The one place in the project that catches bare Exception. The traceback is logged
    # against a request id and never returned in the body.
    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        request_id = uuid4()
        LOGGER.exception("unhandled error on %s (request_id=%s)", request.url.path, request_id)
        return JSONResponse(
            status_code=status_for(CODE_INTERNAL),
            content=envelope(CODE_INTERNAL, "see server logs", request_id),
        )

    @app.get(f"{API_PREFIX}/health")
    async def health() -> dict:
        return {"status": "ok", "version": API_VERSION, "unavailable_code": CODE_UNAVAILABLE}

    return app


app = create_app()
