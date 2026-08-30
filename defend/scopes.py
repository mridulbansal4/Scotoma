"""Train and evaluate the same detector at issuer, acquirer and network scope.

PayLoop operationalises a known asymmetry as a code-level mask. It did not discover one.
"""

from collections import defaultdict

import pandas as pd

from defend.ensemble import Detector
from defend.features import FeatureContext
from runtime.config import PayLoopConfig
from schema.projections import project_frame

SCOPES: tuple[str, ...] = ("ISSUER", "ACQUIRER", "NETWORK")
SCOPE_COLLAPSE_DELTA: float = 0.20
MIN_SCOPE_ROWS: int = 2_000


def party_id_for(scope: str, config: PayLoopConfig) -> str | None:
    if scope == "ISSUER":
        return config.party_issuer_id
    if scope == "ACQUIRER":
        return config.party_acquirer_id
    return None


def evaluate_all_scopes(
    events: pd.DataFrame, config: PayLoopConfig, context: FeatureContext | None = None
) -> dict[str, dict[str, float]]:
    """Same detector class, three visibility masks. Returns {vector_id: {scope: pr_auc}}."""
    matrix: dict[str, dict[str, float]] = defaultdict(dict)
    for scope in SCOPES:
        scoped = project_frame(events, scope, party_id=party_id_for(scope, config))
        if len(scoped) < MIN_SCOPE_ROWS or scoped["is_fraud"].sum() < 2:
            continue
        detector = Detector(config, context=context).fit(scoped)
        for vector_id, score in detector.pr_auc_by_vector(scoped).items():
            matrix[vector_id][scope] = round(float(score), 4)
    return dict(matrix)


def collapse_flags(matrix: dict[str, dict[str, float]]) -> dict[str, bool]:
    flags = {}
    for vector_id, scores in matrix.items():
        issuer = scores.get("ISSUER")
        network = scores.get("NETWORK")
        flags[vector_id] = bool(
            issuer is not None and network is not None and (network - issuer) > SCOPE_COLLAPSE_DELTA
        )
    return flags
