"""CES validation, the registry contract, and the repo-wide build rules."""

import ast
import re
from pathlib import Path

import pytest

from backend.defend.features import FEATURE_NAMES
from backend.defend.ladder import LADDER_APPROVE_MAX, LADDER_HOLD_MAX, LADDER_STEPUP_MAX
from backend.generate.declines import DE39_MIX
from backend.generate.injectors import INJECTOR_CLASS_COUNT, INJECTOR_MODULE_COUNT, INJECTORS
from backend.generate.injectors.base import TEST_BIN_RANGES, synth_pan
from backend.registry.loader import (
    EXPECTED_VECTOR_COUNT,
    load_claims,
    load_vectors,
    mechanism_imperatives,
    resolve_injector,
)
from backend.runtime.seeding import rng_for
from backend.schema.ces import CanonicalEvent, validate_frame
from backend.schema.mappings.iso8583 import CES_TO_DE

REPO_ROOT: Path = Path(__file__).resolve().parent.parent
PACKAGE_DIRS: tuple[str, ...] = (
    "backend/api",
    "backend/defend",
    "backend/fidelity",
    "backend/generate",
    "backend/loop",
    "backend/registry",
    "backend/runtime",
    "backend/schema",
)
CONFIG_MODULE: str = "backend/runtime/config.py"
SEEDING_MODULE: str = "backend/runtime/seeding.py"
GLOBAL_RANDOM_PATTERN = re.compile(
    r"(?<![\w.])(np\.random\.(?!Generator|SeedSequence|default_rng)|random\.)"
)
DEFAULT_RNG_ALLOWED: tuple[str, ...] = (SEEDING_MODULE,)
MIX_TOLERANCE: float = 1e-9
PAN_SAMPLE_COUNT: int = 200


def _python_files() -> list[Path]:
    files: list[Path] = []
    for directory in PACKAGE_DIRS:
        files.extend(sorted((REPO_ROOT / directory).rglob("*.py")))
    return files


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def test_registry_has_32_entries() -> None:
    assert len(load_vectors()) == EXPECTED_VECTOR_COUNT


def test_registry_injector_paths_import() -> None:
    resolved = [resolve_injector(v) for v in load_vectors() if v.injector]
    assert len(resolved) == INJECTOR_CLASS_COUNT
    for injector in resolved:
        assert hasattr(injector, "vector_id")
        assert hasattr(injector, "param_schema")
        assert callable(injector.inject)


def test_registry_expected_features_exist() -> None:
    for vector in load_vectors():
        missing = [f for f in vector.expected_features if f not in FEATURE_NAMES]
        assert not missing, f"{vector.id} names unknown features {missing}"


def test_registry_has_no_operational_detail() -> None:
    for vector in load_vectors():
        assert len(vector.mechanism) <= 200
        assert not mechanism_imperatives(vector.mechanism)


def test_exactly_one_blind_holdout_vector() -> None:
    assert sum(1 for v in load_vectors() if v.blind_holdout) == 1


def test_injector_counts_match_the_published_split() -> None:
    modules = {INJECTORS[vector_id].__module__ for vector_id in INJECTORS}
    assert len(modules) == INJECTOR_MODULE_COUNT
    assert len(INJECTORS) == INJECTOR_CLASS_COUNT


def test_claims_load_and_carry_provenance() -> None:
    claims = load_claims()
    assert claims
    for claim in claims.values():
        assert claim.approved_text
        assert claim.attribution


def test_single_config_read() -> None:
    offenders = [
        _relative(path)
        for path in _python_files()
        if _relative(path) != CONFIG_MODULE
        and (
            "os.getenv" in path.read_text(encoding="utf-8")
            or "os.environ" in path.read_text(encoding="utf-8")
        )
    ]
    assert not offenders, offenders


def test_no_global_random() -> None:
    offenders = []
    for path in _python_files():
        if _relative(path) in DEFAULT_RNG_ALLOWED:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if GLOBAL_RANDOM_PATTERN.search(line) and "np.random.Generator" not in line:
                offenders.append(f"{_relative(path)}:{number}")
    assert not offenders, offenders


def test_de39_mix_sums_to_one() -> None:
    for region, mix in DE39_MIX.items():
        assert abs(sum(mix.values()) - 1.0) < MIX_TOLERANCE, region
        assert "14" not in mix


def test_ladder_bands_are_non_overlapping() -> None:
    assert 0.0 < LADDER_APPROVE_MAX < LADDER_STEPUP_MAX < LADDER_HOLD_MAX < 1.0


def test_test_bin_ranges_only() -> None:
    rng = rng_for("pytest:pan")
    for index in range(PAN_SAMPLE_COUNT):
        pan = synth_pan("41111100", 7, index, rng)
        assert any(low <= int(pan[:8]) <= high for low, high in TEST_BIN_RANGES)
    with pytest.raises(ValueError):
        synth_pan("40000000", 1, 0, rng)


def test_iso8583_field_numbers() -> None:
    assert CES_TO_DE["terminal_id"] == "DE41"
    assert CES_TO_DE["merchant_id"] == "DE42"
    assert CES_TO_DE["merchant_country"] == "DE43"
    assert CES_TO_DE["response_code"] == "DE39"


def test_cross_border_is_validated_not_trusted() -> None:
    from tests import fixture_world

    row = fixture_world().legit.iloc[0].to_dict()
    row["cross_border"] = not row["cross_border"]
    with pytest.raises(ValueError):
        CanonicalEvent.model_validate({k: v for k, v in row.items() if v is not None and v == v})


def test_validate_frame_accepts_generated_events() -> None:
    from tests import fixture_world

    frame = fixture_world().legit.head(300)
    assert len(validate_frame(frame)) == len(frame)


def test_no_banned_module_names() -> None:
    banned = {"utils.py", "helpers.py", "manager.py", "core", "common", "misc"}
    names = {path.name for path in _python_files()} | {path.parent.name for path in _python_files()}
    assert names.isdisjoint(banned)


def test_no_bare_exception_handlers_outside_the_api_boundary() -> None:
    offenders = []
    for path in _python_files():
        if _relative(path) == "api/app.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            if node.type is None or (
                isinstance(node.type, ast.Name) and node.type.id == "Exception"
            ):
                offenders.append(f"{_relative(path)}:{node.lineno}")
    assert not offenders, offenders
