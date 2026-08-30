"""Parse and validate vectors.yaml and claims.yaml. Invalid registry aborts the process."""

import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

from backend.runtime.errors import RegistryInvalid

REGISTRY_DIR: Path = Path(__file__).resolve().parent
VECTORS_PATH: Path = REGISTRY_DIR / "vectors.yaml"
CLAIMS_PATH: Path = REGISTRY_DIR / "claims.yaml"

EXPECTED_VECTOR_COUNT: int = 32
MIN_OBSERVABLE_SIGNALS: int = 3
MAX_MECHANISM_CHARS: int = 200

VECTOR_STATUSES: frozenset[str] = frozenset({"documented", "emerging", "speculative"})
SIM_DIFFICULTIES: frozenset[str] = frozenset({"low", "medium", "high"})
CLAIM_PROVENANCE: frozenset[str] = frozenset({"independent", "vendor", "vendor_commissioned"})

# The registry documents mechanism, signals and countermeasure. An imperative in the
# mechanism field would turn a description into an instruction, which this list forbids.
BANNED_IMPERATIVES: frozenset[str] = frozenset(
    {
        "use",
        "run",
        "send",
        "exploit",
        "bypass",
        "install",
        "execute",
        "deploy",
        "obtain",
        "steal",
        "attack",
        "inject",
        "forge",
        "spoof",
        "generate",
        "create",
        "build",
        "harvest",
        "probe",
        "target",
        "evade",
        "defeat",
        "clone",
        "scrape",
    }
)

REQUIRED_VECTOR_KEYS: tuple[str, ...] = (
    "id",
    "name",
    "rails",
    "tier",
    "mechanism",
    "genai_delta",
    "observable_signals",
    "status",
    "sources",
    "sim_difficulty",
    "injector",
    "expected_features",
    "countermeasure",
    "blind_holdout",
)

REQUIRED_CLAIM_KEYS: tuple[str, ...] = (
    "key",
    "value",
    "scope",
    "provenance",
    "attribution",
    "approved_text",
    "suffix",
)


@dataclass(frozen=True)
class Vector:
    id: str
    name: str
    rails: list[str]
    tier: int
    mechanism: str
    genai_delta: str
    observable_signals: list[str]
    status: Literal["documented", "emerging", "speculative"]
    sources: list[str]
    sim_difficulty: Literal["low", "medium", "high"]
    injector: str | None
    expected_features: list[str]
    countermeasure: str
    blind_holdout: bool


@dataclass(frozen=True)
class Claim:
    key: str
    value: str
    scope: str
    provenance: Literal["independent", "vendor", "vendor_commissioned"]
    attribution: str
    approved_text: str
    suffix: str


def load_vectors(path: Path | None = None) -> list[Vector]:
    raw = yaml.safe_load((path or VECTORS_PATH).read_text(encoding="utf-8"))
    if not isinstance(raw, list) or len(raw) != EXPECTED_VECTOR_COUNT:
        raise RegistryInvalid(
            f"vectors.yaml must hold exactly {EXPECTED_VECTOR_COUNT} entries, found "
            f"{len(raw) if isinstance(raw, list) else 'a non-list'}"
        )
    vectors = [_build_vector(entry) for entry in raw]
    holdouts = [v.id for v in vectors if v.blind_holdout]
    if len(holdouts) != 1:
        raise RegistryInvalid(f"exactly one entry must set blind_holdout, found {holdouts}")
    ids = [v.id for v in vectors]
    if len(set(ids)) != len(ids):
        raise RegistryInvalid("duplicate vector ids in vectors.yaml")
    return vectors


def _build_vector(entry: dict) -> Vector:
    missing = [key for key in REQUIRED_VECTOR_KEYS if key not in entry]
    if missing:
        raise RegistryInvalid(f"vector {entry.get('id', '?')} missing keys {missing}")
    vector = Vector(**{key: entry[key] for key in REQUIRED_VECTOR_KEYS})
    if vector.status not in VECTOR_STATUSES:
        raise RegistryInvalid(f"vector {vector.id} has unknown status {vector.status}")
    if vector.sim_difficulty not in SIM_DIFFICULTIES:
        raise RegistryInvalid(f"vector {vector.id} has unknown sim_difficulty")
    if len(vector.observable_signals) < MIN_OBSERVABLE_SIGNALS:
        raise RegistryInvalid(f"vector {vector.id} needs at least three observable signals")
    if len(vector.mechanism) > MAX_MECHANISM_CHARS:
        raise RegistryInvalid(f"vector {vector.id} mechanism exceeds {MAX_MECHANISM_CHARS} chars")
    offending = mechanism_imperatives(vector.mechanism)
    if offending:
        raise RegistryInvalid(f"vector {vector.id} mechanism contains imperatives {offending}")
    if not vector.countermeasure:
        raise RegistryInvalid(f"vector {vector.id} has no countermeasure")
    return vector


def mechanism_imperatives(mechanism: str) -> list[str]:
    words = {word.strip(".,;:()").lower() for word in mechanism.split()}
    return sorted(words & BANNED_IMPERATIVES)


def resolve_injector(vector: Vector) -> type | None:
    if vector.injector is None:
        return None
    module_path, _, class_name = vector.injector.partition(":")
    try:
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
    except (ImportError, AttributeError) as exc:
        raise RegistryInvalid(
            f"vector {vector.id} injector {vector.injector} does not import: {exc}"
        ) from exc


def load_claims(path: Path | None = None) -> dict[str, Claim]:
    raw = yaml.safe_load((path or CLAIMS_PATH).read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise RegistryInvalid("claims.yaml must hold a non-empty list")
    claims: dict[str, Claim] = {}
    for entry in raw:
        missing = [key for key in REQUIRED_CLAIM_KEYS if key not in entry]
        if missing:
            raise RegistryInvalid(f"claim {entry.get('key', '?')} missing keys {missing}")
        claim = Claim(**{key: entry[key] for key in REQUIRED_CLAIM_KEYS})
        if claim.provenance not in CLAIM_PROVENANCE:
            raise RegistryInvalid(f"claim {claim.key} has unknown provenance {claim.provenance}")
        if claim.key in claims:
            raise RegistryInvalid(f"duplicate claim key {claim.key}")
        claims[claim.key] = claim
    return claims


def status_counts(vectors: list[Vector]) -> dict[str, int]:
    counts = {status: 0 for status in sorted(VECTOR_STATUSES)}
    for vector in vectors:
        counts[vector.status] += 1
    return counts
