"""GET /registry/vectors and GET /registry/coverage."""

from dataclasses import asdict

from fastapi import APIRouter
from pydantic import BaseModel

from backend.registry.coverage import coverage_for_run
from backend.registry.loader import load_vectors, status_counts
from backend.runtime.artifacts import read_json, run_dir
from backend.runtime.config import load_config
from backend.runtime.errors import PayLoopError

router = APIRouter()

COVERAGE_FILE: str = "coverage.json"


class VectorList(BaseModel):
    vectors: list[dict]
    counts: dict[str, int]


class CoverageMatrix(BaseModel):
    run_id: str
    total_vectors: int
    injector_modules: int
    injector_classes: int
    vectors_with_injector: int
    coverage_pct: float
    rows: list[dict]


class RunArtifactMissing(PayLoopError):
    pass


@router.get("/registry/vectors", response_model=VectorList)
async def list_vectors() -> VectorList:
    vectors = load_vectors()
    return VectorList(
        vectors=[asdict(vector) for vector in vectors], counts=status_counts(vectors)
    )


@router.get("/registry/coverage", response_model=CoverageMatrix)
async def coverage_matrix() -> CoverageMatrix:
    run_id = load_config().run_id
    if (run_dir(run_id) / COVERAGE_FILE).exists():
        payload = read_json(run_id, COVERAGE_FILE)
    else:
        payload = coverage_for_run(run_id, {})
    return CoverageMatrix(**{key: payload[key] for key in CoverageMatrix.model_fields})
