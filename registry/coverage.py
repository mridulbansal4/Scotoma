"""Vector x {injector, features, recall} matrix. The implemented/documented gap is shown."""

from defend.features import FEATURE_NAMES
from registry.loader import Vector, load_vectors, status_counts

COVERAGE_RECALL_BAR: float = 0.60
EXPECTED_VECTOR_COUNT: int = 32
EXPECTED_INJECTOR_MODULES: int = 8
EXPECTED_INJECTOR_CLASSES: int = 12


def build_coverage(vectors: list[Vector], recall_by_vector: dict[str, float]) -> dict:
    rows = []
    for vector in vectors:
        has_injector = vector.injector is not None
        recall = recall_by_vector.get(vector.id) if has_injector else None
        rows.append(
            {
                "vector_id": vector.id,
                "name": vector.name,
                "status": vector.status,
                "rails": vector.rails,
                "tier": vector.tier,
                "has_injector": has_injector,
                "has_expected_features": all(f in FEATURE_NAMES for f in vector.expected_features),
                "recall": recall,
                "detected_at_recall_0_6": recall is not None and recall >= COVERAGE_RECALL_BAR,
                "blind_holdout": vector.blind_holdout,
            }
        )
    with_injector = sum(1 for row in rows if row["has_injector"])
    return {
        "total_vectors": len(vectors),
        "injector_modules": EXPECTED_INJECTOR_MODULES,
        "injector_classes": EXPECTED_INJECTOR_CLASSES,
        "vectors_with_injector": with_injector,
        "coverage_pct": with_injector / EXPECTED_VECTOR_COUNT,
        "counts": status_counts(vectors),
        "recall_bar": COVERAGE_RECALL_BAR,
        "rows": rows,
    }


def coverage_for_run(run_id: str, recall_by_vector: dict[str, float]) -> dict:
    payload = build_coverage(load_vectors(), recall_by_vector)
    payload["run_id"] = run_id
    return payload
