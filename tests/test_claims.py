"""The three rulings, enforced against the whole repository."""

import re
from pathlib import Path

import pytest

from backend.registry.loader import load_claims
from backend.runtime.artifacts import run_dir
from backend.runtime.config import load_config

REPO_ROOT: Path = Path(__file__).resolve().parent.parent
WEB_ROOT: Path = REPO_ROOT / "frontend"
README_PATH: Path = REPO_ROOT / "README.md"
RUN_ID: str = load_config().run_id

TEXT_SUFFIXES: frozenset[str] = frozenset({".md", ".ts", ".tsx", ".css", ".json", ".jsonl", ".mjs"})
SCANNED_ROOTS: tuple[Path, ...] = (
    README_PATH,
    WEB_ROOT / "app",
    WEB_ROOT / "components",
    WEB_ROOT / "lib",
)

# Ruling R-A: the holdout is one attack family and one entity cohort from the same
# generator with divergent parameters. The banned form is the affirmative claim; the
# negation is the honest statement the loop screen is required to carry, so a preceding
# "not" or "never" is what separates the two.
# A leading word boundary keeps "row-independent generators" out of scope: that is a
# property of a class of generators, not a claim about where this holdout came from.
BANNED_PHRASES: tuple[str, ...] = (
    r"(?<![\w-])independently generated",
    r"(?<![\w-])independent generator",
)
NEGATION_PREFIXES: tuple[str, ...] = ("not ", "never ", "no ")
NEGATION_WINDOW: int = 24

# Ruling R-B: two sources disagree on which generator produced which figure. The range is
# quotable; an attribution to a named generator is not.
GENERATOR_NAMES: tuple[str, ...] = ("TVAE", "GaussianCopula")
ATTRIBUTION_FIGURES: tuple[str, ...] = ("24.4", "39.0", "81.6", "99.7")
ATTRIBUTION_WINDOW: int = 80

# Ruling R-C: no sub-millisecond latency figure appears anywhere.
BANNED_LATENCY: tuple[str, ...] = ("1.8 ms", "1.2 ms", "5 µs", "5 us")

NETWORK_CALLS: tuple[str, ...] = ("fetch(", "axios", "XMLHttpRequest", "EventSource")

HONESTY_CALLOUT: str = (
    "This loop measures and shrinks a detector's blind spots. It does not claim to make anyone "
    "monotonically safer. The blind holdout is one attack family and one entity cohort, neither "
    "of which enters any training pool — it is not independently generated."
)

HIDDEN_PATTERN = re.compile(r"(className=[\"'][^\"']*hidden|<[A-Za-z][^>]*\shidden[\s>=])")
BUILT_VS_NARRATIVE_ROWS: int = 15
NUMBER_PATTERN = re.compile(r"\$?\d[\d,]*\.?\d*\s*(?:%|B|M|bn|billion|million|ms|bps|x)\b")

web_present = pytest.mark.skipif(not WEB_ROOT.exists(), reason="frontend not built")
readme_present = pytest.mark.skipif(not README_PATH.exists(), reason="README not written")


def _scan_files() -> list[Path]:
    files: list[Path] = []
    for root in SCANNED_ROOTS:
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            files.extend(p for p in root.rglob("*") if p.is_file() and p.suffix in TEXT_SUFFIXES)
    run_directory = run_dir(RUN_ID)
    if run_directory.exists():
        files.extend(p for p in run_directory.iterdir() if p.suffix in TEXT_SUFFIXES)
    return files


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _flatten(text: str) -> str:
    """Collapse the source's string-literal concatenation so the sentence can be compared."""
    stripped = re.sub(r"['\"+]", "", text)
    return " ".join(stripped.split())


def _is_negated(text: str, position: int) -> bool:
    window = text[max(0, position - NEGATION_WINDOW) : position]
    return any(prefix in window for prefix in NEGATION_PREFIXES)


def test_no_banned_phrases() -> None:
    offenders = []
    for path in _scan_files():
        text = _read(path).lower()
        for phrase in BANNED_PHRASES:
            for match in re.finditer(phrase, text):
                if not _is_negated(text, match.start()):
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{phrase}")
    assert not offenders, offenders


def test_no_generator_attribution() -> None:
    """Naming GaussianCopula as PayLoop's own ablation baseline is permitted, because it
    appears nowhere near the published literature figures."""
    offenders = []
    for path in _scan_files():
        text = _read(path)
        for figure in ATTRIBUTION_FIGURES:
            for match in re.finditer(re.escape(figure), text):
                window = text[
                    max(0, match.start() - ATTRIBUTION_WINDOW) : match.end() + ATTRIBUTION_WINDOW
                ]
                if any(name in window for name in GENERATOR_NAMES):
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{figure}")
    assert not offenders, offenders


def test_no_unbadged_latency() -> None:
    offenders = [
        str(path.relative_to(REPO_ROOT))
        for path in _scan_files()
        if any(value in _read(path) for value in BANNED_LATENCY)
    ]
    assert not offenders, offenders


@web_present
def test_web_has_no_fetch() -> None:
    offenders = []
    for root in (WEB_ROOT / "app", WEB_ROOT / "components"):
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if path.suffix not in {".ts", ".tsx"}:
                continue
            text = _read(path)
            offenders.extend(
                f"{path.relative_to(REPO_ROOT)}:{call}" for call in NETWORK_CALLS if call in text
            )
    assert not offenders, offenders


@web_present
def test_ui_numbers_are_claimed() -> None:
    """Every externally quotable figure in the copy resolves to a claims.yaml key.

    Both the components and the page copy are scanned: a headline is as quotable as a chart
    label, and it is the headline a judge reads first."""
    claims = load_claims()
    approved = " ".join(f"{c.value} {c.approved_text}" for c in claims.values())
    offenders = []
    scanned = [
        *(WEB_ROOT / "components").rglob("*.tsx"),
        *(WEB_ROOT / "app").rglob("*.tsx"),
    ]
    for path in scanned:
        for match in NUMBER_PATTERN.finditer(_read(path)):
            token = match.group(0).strip()
            if token not in approved:
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{token}")
    assert not offenders, offenders


@web_present
def test_honesty_callout_present() -> None:
    callout = WEB_ROOT / "components" / "HonestyCallout.tsx"
    assert callout.exists()
    source = _read(callout)
    assert _flatten(HONESTY_CALLOUT) in _flatten(source), _flatten(source)
    # No collapse control and no hidden class: the callout is never conditionally rendered.
    assert not HIDDEN_PATTERN.search(source)
    assert "useState" not in source


@readme_present
def test_built_vs_narrative_in_readme() -> None:
    text = _read(README_PATH)
    assert "## Built vs narrative" in text
    section = text.split("## Built vs narrative", 1)[1]
    rows: list[str] = []
    for line in section.splitlines():
        if line.startswith("|"):
            if "---" not in line:
                rows.append(line)
        elif rows:
            break
    assert len(rows) - 1 == BUILT_VS_NARRATIVE_ROWS, len(rows) - 1


@readme_present
def test_readme_states_the_three_rulings() -> None:
    text = _read(README_PATH)
    for ruling in ("R-A", "R-B", "R-C"):
        assert ruling in text


def test_claims_cover_the_headline_figures() -> None:
    claims = load_claims()
    for key in (
        "false_declines_four_markets",
        "behavioural_degradation_range",
        "blind_holdout",
        "coverage_split",
    ):
        assert key in claims
    assert claims["false_declines_four_markets"].suffix == "vendor-commissioned"
    assert "independently generated" not in claims["blind_holdout"].approved_text
