"""The four-tier mitigation ladder. These four boundaries exist exactly once, here."""

from enum import StrEnum

LADDER_APPROVE_MAX: float = 0.30
LADDER_STEPUP_MAX: float = 0.70
LADDER_HOLD_MAX: float = 0.90
LADDER_HOLD_MINUTES: int = 15


class LadderBand(StrEnum):
    APPROVE = "APPROVE"
    STEP_UP = "STEP_UP"
    HOLD = "HOLD"
    DECLINE_REVIEW = "DECLINE_REVIEW"


BAND_ACTIONS: dict[LadderBand, str] = {
    LadderBand.APPROVE: "Frictionless approval",
    LadderBand.STEP_UP: "EMV 3DS 2.x challenge / biometric / push confirmation",
    LadderBand.HOLD: f"{LADDER_HOLD_MINUTES}-minute settlement delay + dynamic risk warning",
    LadderBand.DECLINE_REVIEW: "Decline + SAR / AML analyst queue",
}


def band_for_score(score: float) -> LadderBand:
    if score < LADDER_APPROVE_MAX:
        return LadderBand.APPROVE
    if score < LADDER_STEPUP_MAX:
        return LadderBand.STEP_UP
    if score < LADDER_HOLD_MAX:
        return LadderBand.HOLD
    return LadderBand.DECLINE_REVIEW


def action_for_band(band: LadderBand) -> str:
    return BAND_ACTIONS[band]


def band_boundaries() -> dict[str, float]:
    return {
        "approve_max": LADDER_APPROVE_MAX,
        "stepup_max": LADDER_STEPUP_MAX,
        "hold_max": LADDER_HOLD_MAX,
    }
