"""Constraint validation before realisation. Invalid proposals are regenerated, never
silently clipped: clipping is how a run ends up containing rows that could not exist."""

from dataclasses import dataclass

import jsonschema
from jsonschema import ValidationError

from backend.generate.injectors import PARAM_SCHEMAS, RAIL_OF_VECTOR
from backend.schema.ces import RAIL_LIMITS

EXPIRY_MARGIN_KEY: str = "expiry_margin_s"
FAN_IN_KEY: str = "fan_in_degree"
AMOUNT_BAND_KEY: str = "amount_band"


@dataclass(frozen=True)
class Proposal:
    vector_id: str
    params: dict
    rationale: str


_ACCOUNT_COUNT: int = 50_000


def set_population_account_count(count: int) -> None:
    global _ACCOUNT_COUNT
    _ACCOUNT_COUNT = int(count)


def population_account_count() -> int:
    return _ACCOUNT_COUNT


def validate(proposal: Proposal) -> tuple[bool, str]:
    schema = PARAM_SCHEMAS.get(proposal.vector_id)
    if schema is None:
        return False, f"unknown vector_id {proposal.vector_id}"
    try:
        jsonschema.validate(proposal.params, schema)
    except ValidationError as exc:
        return False, f"schema: {exc.message}"
    rail = RAIL_OF_VECTOR[proposal.vector_id]
    band = proposal.params.get(AMOUNT_BAND_KEY)
    if band and band[1] > RAIL_LIMITS[rail]:
        return False, f"amount {band[1]} exceeds {rail} limit {RAIL_LIMITS[rail]}"
    if band and band[0] > band[1]:
        return False, "amount band lower bound exceeds its upper bound"
    if proposal.params.get(EXPIRY_MARGIN_KEY, 0) < 0:
        return False, "mandate cannot settle after expiry in this simulator"
    if proposal.params.get(FAN_IN_KEY, 0) > population_account_count():
        return False, "fan-in degree exceeds available accounts"
    return True, "ok"


def rejection_rule(reason: str) -> str:
    if reason.startswith("schema:"):
        return "parameter outside the simulator's declared action space"
    if "expiry" in reason:
        return "mandate cannot settle after expiry in this simulator"
    if "fan-in" in reason:
        return "fan-in degree exceeds available accounts"
    if "exceeds" in reason:
        return "amount exceeds the rail limit"
    return "proposal rejected by the constraint validator"


def partition_valid(proposals: list[Proposal]) -> tuple[list[Proposal], list[dict]]:
    valid: list[Proposal] = []
    rejected: list[dict] = []
    for index, proposal in enumerate(proposals):
        ok, reason = validate(proposal)
        if ok:
            valid.append(proposal)
        else:
            rejected.append(
                {
                    "index": index,
                    "vector_id": proposal.vector_id,
                    "reason": reason,
                    "rule": rejection_rule(reason),
                    "params": proposal.params,
                }
            )
    return valid, rejected
