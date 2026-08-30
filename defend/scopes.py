"""Train and evaluate the same detector at issuer, acquirer and network scope.

PayLoop operationalises a known asymmetry as a code-level mask. It did not discover one.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from defend.ensemble import Detector
from defend.features import FeatureContext
from generate.population import SIM_START
from runtime.config import PayLoopConfig
from schema.projections import project_frame

SCOPES: tuple[str, ...] = ("ISSUER", "ACQUIRER", "NETWORK")
SCOPE_COLLAPSE_DELTA: float = 0.20
MIN_SCOPE_ROWS: int = 2_000
MIN_SCOPE_POSITIVES: int = 2

STATUS_FITTED: str = "fitted"
STATUS_TOO_FEW_ROWS: str = "too_few_rows"
STATUS_TOO_FEW_POSITIVES: str = "too_few_positives"


@dataclass
class ScopeReport:
    matrix: dict[str, dict[str, float]] = field(default_factory=dict)
    status: dict[str, dict] = field(default_factory=dict)

    def collapse(self) -> dict[str, bool]:
        return collapse_flags(self.matrix)

    def as_payload(self) -> dict:
        return {"matrix": self.matrix, "collapse": self.collapse(), "status": self.status}


def party_id_for(scope: str, config: PayLoopConfig) -> str | None:
    if scope == "ISSUER":
        return config.party_issuer_id
    if scope == "ACQUIRER":
        return config.party_acquirer_id
    return None


def evaluate_all_scopes(
    events: pd.DataFrame,
    config: PayLoopConfig,
    context: FeatureContext | None = None,
    sim_start: datetime | None = None,
) -> ScopeReport:
    """Same detector class, three visibility masks.

    A scope with too little fraud to fit a calibrated model is reported as exactly that.
    It is the asymmetry in its strongest form — the party cannot train the detector at all —
    and swallowing it as an empty column would hide the finding."""
    report = ScopeReport(matrix=defaultdict(dict), status={})
    for scope in SCOPES:
        scoped = project_frame(events, scope, party_id=party_id_for(scope, config))
        positives = int(scoped["is_fraud"].sum())
        report.status[scope] = {
            "rows": int(len(scoped)),
            "positives": positives,
            "party_id": party_id_for(scope, config),
            "status": STATUS_FITTED,
        }
        if len(scoped) < MIN_SCOPE_ROWS:
            report.status[scope]["status"] = STATUS_TOO_FEW_ROWS
            continue
        if positives < MIN_SCOPE_POSITIVES:
            report.status[scope]["status"] = STATUS_TOO_FEW_POSITIVES
            continue
        try:
            # The split boundary is an absolute date. Letting each scope infer its own start
            # from its earliest surviving row would train the three on different windows.
            detector = Detector(config, context=context, sim_start=sim_start or SIM_START).fit(
                scoped
            )
        except ValueError as exc:
            report.status[scope]["status"] = STATUS_TOO_FEW_POSITIVES
            report.status[scope]["detail"] = str(exc)
            continue
        for vector_id, score in detector.pr_auc_by_vector(scoped).items():
            report.matrix[vector_id][scope] = round(float(score), 4)
    report.matrix = dict(report.matrix)
    return report


def collapse_flags(matrix: dict[str, dict[str, float]]) -> dict[str, bool]:
    flags = {}
    for vector_id, scores in matrix.items():
        issuer = scores.get("ISSUER")
        network = scores.get("NETWORK")
        flags[vector_id] = bool(
            issuer is not None and network is not None and (network - issuer) > SCOPE_COLLAPSE_DELTA
        )
    return flags
