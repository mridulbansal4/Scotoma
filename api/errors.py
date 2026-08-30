"""The single error envelope and the PayLoop error-code table."""

from dataclasses import dataclass
from uuid import UUID, uuid4

from runtime.errors import (
    LatencyBudgetExceeded,
    ModelArtifactMissing,
    PayLoopError,
    SchemaViolation,
    WarehouseUnavailable,
)

CODE_BAD_REQUEST: str = "PAYLOOP-E-400"
CODE_NOT_FOUND: str = "PAYLOOP-E-404"
CODE_CONFLICT: str = "PAYLOOP-E-409"
CODE_UNPROCESSABLE: str = "PAYLOOP-E-422"
CODE_MODEL_MISSING: str = "PAYLOOP-E-424"
CODE_QUEUE_FULL: str = "PAYLOOP-E-429"
CODE_INTERNAL: str = "PAYLOOP-E-500"
CODE_UNAVAILABLE: str = "PAYLOOP-E-503"
CODE_TIMEOUT: str = "PAYLOOP-E-504"

STATUS_BY_CODE: dict[str, int] = {
    CODE_BAD_REQUEST: 400,
    CODE_NOT_FOUND: 404,
    CODE_CONFLICT: 409,
    CODE_UNPROCESSABLE: 422,
    CODE_MODEL_MISSING: 424,
    CODE_QUEUE_FULL: 429,
    CODE_INTERNAL: 500,
    CODE_UNAVAILABLE: 503,
    CODE_TIMEOUT: 504,
}

MESSAGE_BY_CODE: dict[str, str] = {
    CODE_BAD_REQUEST: "Request body failed validation.",
    CODE_NOT_FOUND: "Run identifier not found.",
    CODE_CONFLICT: "A loop run is already in progress for this run identifier.",
    CODE_UNPROCESSABLE: "The event is syntactically valid but violates a domain rule.",
    CODE_MODEL_MISSING: "Model artefact missing.",
    CODE_QUEUE_FULL: "Job queue is at capacity.",
    CODE_INTERNAL: "Unhandled server error.",
    CODE_UNAVAILABLE: "A dependency is unreachable.",
    CODE_TIMEOUT: "Scoring exceeded its latency budget.",
}

EXCEPTION_CODES: dict[type[PayLoopError], str] = {
    SchemaViolation: CODE_BAD_REQUEST,
    WarehouseUnavailable: CODE_UNAVAILABLE,
    ModelArtifactMissing: CODE_MODEL_MISSING,
    LatencyBudgetExceeded: CODE_TIMEOUT,
}


@dataclass(frozen=True)
class PayLoopHttpError(Exception):
    code: str
    detail: str
    request_id: UUID = uuid4()


def envelope(code: str, detail: str, request_id: UUID | None = None) -> dict:
    return {
        "error": {
            "code": code,
            "message": MESSAGE_BY_CODE[code],
            "detail": detail,
            "request_id": str(request_id or uuid4()),
        }
    }


def code_for(error: PayLoopError) -> str:
    for exception_type, code in EXCEPTION_CODES.items():
        if isinstance(error, exception_type):
            return code
    return CODE_INTERNAL


def status_for(code: str) -> int:
    return STATUS_BY_CODE[code]
