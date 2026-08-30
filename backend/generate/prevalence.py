"""Per-rail fraud targets, hard caps, and the injector scale-down."""

import logging

import numpy as np
import pandas as pd

from backend.runtime.config import PayLoopConfig
from backend.runtime.errors import PrevalenceExceeded
from backend.runtime.seeding import rng_for

LOGGER = logging.getLogger("payloop.prevalence")

PREVALENCE_CAPPED: str = "PREVALENCE_CAPPED"

RAIL_TARGET_FIELD: dict[str, str] = {
    "CARD_CNP": "target_fraud_rate_card",
    "CARD_CP": "target_fraud_rate_card",
    "UPI": "target_fraud_rate_upi",
    "SEPA_INST": "target_fraud_rate_rtp",
    "ACH": "target_fraud_rate_rtp",
    "AGENTIC": "target_fraud_rate_agentic",
}

# The agentic rail is deliberately over-sampled as the novelty surface; this is stated in
# the README and excluded from any population-level prevalence claim.
RAIL_HARD_CAPS: dict[str, float] = {
    "CARD_CNP": 0.0100,
    "CARD_CP": 0.0100,
    "UPI": 0.0100,
    "SEPA_INST": 0.0100,
    "ACH": 0.0100,
    "AGENTIC": 0.0200,
}

MAX_SCALE_DOWN_ATTEMPTS: int = 2
SUBSAMPLE_BLOCK_ROWS: int = 14

# Budgets are drawn per rail family rather than per scheme: the published target rates are
# card-rail and credit-transfer rates, and that is also what the realism assertions measure.
RAIL_BUDGET_GROUPS: dict[str, tuple[str, ...]] = {
    "SEPA_INST": ("SEPA_INST", "ACH"),
    "ACH": ("SEPA_INST", "ACH"),
    "CARD_CNP": ("CARD_CNP", "CARD_CP"),
    "CARD_CP": ("CARD_CNP", "CARD_CP"),
}


def target_rate(rail: str, config: PayLoopConfig) -> float:
    return float(getattr(config, RAIL_TARGET_FIELD[rail]))


def realised_prevalence(events: pd.DataFrame) -> dict[str, float]:
    if events.empty:
        return {}
    grouped = events.groupby("rail")["is_fraud"]
    return {str(rail): float(value) for rail, value in grouped.mean().items()}


def scale_factor_for(rail: str, realised: float) -> float:
    cap = RAIL_HARD_CAPS[rail]
    if realised <= cap or realised <= 0.0:
        return 1.0
    LOGGER.warning("%s rail=%s realised=%.5f cap=%.5f", PREVALENCE_CAPPED, rail, realised, cap)
    return cap / realised


def enforce_caps(events: pd.DataFrame, config: PayLoopConfig) -> pd.DataFrame:
    """Drop fraud rows on any rail above its hard cap, then check the population total."""
    working = events
    for _ in range(MAX_SCALE_DOWN_ATTEMPTS):
        breaches = {
            rail: rate
            for rail, rate in realised_prevalence(working).items()
            if rate > RAIL_HARD_CAPS.get(rail, config.prevalence_hard_cap)
        }
        overall = float(working["is_fraud"].mean()) if len(working) else 0.0
        if not breaches and overall <= config.prevalence_hard_cap:
            return working
        working = _scale_down(working, breaches, config)
    if float(working["is_fraud"].mean()) > config.prevalence_hard_cap:
        raise PrevalenceExceeded("prevalence remains above the hard cap after scale-down")
    return working


def _scale_down(
    events: pd.DataFrame, breaches: dict[str, float], config: PayLoopConfig
) -> pd.DataFrame:
    """Fraud rows are dropped at random rather than from the tail: trimming the tail would
    empty the late part of the window and leave the validation slice with no positives."""
    rng = rng_for("prevalence:scale_down")
    keep = pd.Series(True, index=events.index)
    for rail, realised in breaches.items():
        factor = scale_factor_for(rail, realised)
        candidates = events.index[(events["rail"] == rail) & events["is_fraud"]]
        drop_count = int(round(len(candidates) * (1.0 - factor)))
        if drop_count > 0:
            keep.loc[rng.choice(candidates, size=drop_count, replace=False)] = False
    overall = float(events.loc[keep, "is_fraud"].mean()) if keep.any() else 0.0
    if overall > config.prevalence_hard_cap:
        fraud_index = events.index[events["is_fraud"] & keep]
        target_count = int(int(keep.sum()) * config.prevalence_hard_cap)
        excess = len(fraud_index) - target_count
        if excess > 0:
            LOGGER.warning("%s scope=population realised=%.5f", PREVALENCE_CAPPED, overall)
            keep.loc[rng.choice(fraud_index, size=excess, replace=False)] = False
    return events[keep].reset_index(drop=True)


def campaign_budget(legit: pd.DataFrame, rail: str, config: PayLoopConfig, share: float) -> int:
    """Event budget for one campaign on one rail, derived from that rail's target rate."""
    group = RAIL_BUDGET_GROUPS.get(rail, (rail,))
    rail_volume = int(legit["rail"].isin(group).sum())
    return max(int(rail_volume * target_rate(rail, config) * share), 1)


def subsample_campaign(events: pd.DataFrame, budget: int, purpose: str) -> pd.DataFrame:
    """Trim a campaign to its prevalence budget by keeping whole bursts.

    Sampling individual rows would thin every burst uniformly and leave the campaign with
    the inter-event-time profile of a Poisson process, which is exactly what realism
    assertion 11 exists to rule out."""
    if events.empty or len(events) <= budget:
        return events
    rng = rng_for(f"prevalence:{purpose}")
    blocks = np.arange(len(events)) // SUBSAMPLE_BLOCK_ROWS
    block_ids = np.unique(blocks)
    keep_blocks = max(int(np.ceil(budget / SUBSAMPLE_BLOCK_ROWS)), 1)
    chosen = rng.choice(block_ids, size=min(keep_blocks, block_ids.size), replace=False)
    selected = events[np.isin(blocks, chosen)]
    return selected.head(budget).reset_index(drop=True)
