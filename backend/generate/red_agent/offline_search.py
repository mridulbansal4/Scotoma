"""Optuna TPE over the same parameter schemas. Mandatory: the demo never depends on a
live network call, and this is also the deterministic optimiser the hybrid design assigns
the numeric work to in the first place."""

import logging
import time

import optuna
import pandas as pd

from backend.generate.injectors import INJECTORS, PARAM_SCHEMAS
from backend.generate.red_agent.constraints import Proposal, validate
from backend.runtime.config import load_config
from backend.runtime.seeding import rng_for
from backend.runtime.timewindows import TimeWindow

OFFLINE_TRIALS: int = 40
OFFLINE_BUDGET_S: float = 45.0
OFFLINE_PROBE_EVENTS: int = 400
PROBE_CARRIER_MULTIPLIER: int = 8
OFFLINE_RATIONALE: str = "offline evolutionary search"
BOUNDARY_RATIONALE: str = (
    "boundary probe: one parameter placed just outside the declared action space, so the "
    "constraint validator is exercised on every run rather than assumed to work"
)
BOUNDARY_OVERSHOOT: float = 1.5

optuna.logging.set_verbosity(optuna.logging.WARNING)
LOGGER = logging.getLogger("payloop.offline_search")


def _suggest(trial: optuna.Trial, name: str, spec: dict):
    if "enum" in spec:
        return trial.suggest_categorical(name, spec["enum"])
    if spec.get("type") == "integer":
        return trial.suggest_int(name, int(spec["minimum"]), int(spec["maximum"]))
    if spec.get("type") == "number":
        return trial.suggest_float(name, float(spec["minimum"]), float(spec["maximum"]))
    if spec.get("type") == "array":
        low = trial.suggest_float(f"{name}_low", 0.5, 50.0)
        high = trial.suggest_float(f"{name}_high", low, max(low * 8.0, low + 1.0))
        return [round(low, 2), round(high, 2)]
    return None


def sample_params(trial: optuna.Trial, schema: dict) -> dict:
    params: dict = {}
    for name, spec in schema.get("properties", {}).items():
        value = _suggest(trial, name, spec)
        if value is not None:
            params[name] = value
    return params


def search_offline(
    state,
    schemas: dict[str, dict],
    k: int = 6,
    n_trials: int = OFFLINE_TRIALS,
    population=None,
    window: TimeWindow | None = None,
    detector=None,
    round_index: int = 0,
    carrier=None,
) -> list[Proposal]:
    """One study per vector, objective = realised evasion rate on a short probe campaign."""
    config = load_config()
    candidates: list[tuple[float, Proposal]] = []
    for vector_id in sorted(schemas.keys()):
        schema = PARAM_SCHEMAS[vector_id]
        sampler = optuna.samplers.TPESampler(seed=config.population_seed + round_index)
        study = optuna.create_study(direction="maximize", sampler=sampler)
        deadline = time.perf_counter() + OFFLINE_BUDGET_S

        def objective(
            trial: optuna.Trial, vector_id=vector_id, schema=schema, deadline=deadline
        ) -> float:
            if time.perf_counter() > deadline:
                raise optuna.TrialPruned()
            params = sample_params(trial, schema)
            ok, _ = validate(Proposal(vector_id, params, OFFLINE_RATIONALE))
            if not ok:
                return 0.0
            return _probe_evasion(
                vector_id, params, population, window, detector, round_index, carrier
            )

        study.optimize(objective, n_trials=n_trials, catch=(ValueError, KeyError))
        best = sorted(study.trials, key=lambda t: (t.value or 0.0), reverse=True)
        for trial in best[:2]:
            params = sample_params_from_trial(trial, schema)
            proposal = Proposal(vector_id, params, OFFLINE_RATIONALE)
            ok, _ = validate(proposal)
            if ok:
                candidates.append((trial.value or 0.0, proposal))
                break

    candidates.sort(key=lambda item: item[0], reverse=True)
    chosen = [proposal for _, proposal in candidates[:k]]
    probe = boundary_probe(chosen)
    return [*chosen, probe] if probe else chosen


def boundary_probe(proposals: list[Proposal]) -> Proposal | None:
    """A deliberately out-of-schema proposal.

    The validator is the most load-bearing safety property in the loop, and a run in which
    nothing was ever rejected proves nothing about it. This proposal is built to fail, is
    labelled as such, and never reaches an injector."""
    if not proposals:
        return None
    source = proposals[0]
    schema = PARAM_SCHEMAS[source.vector_id]
    params = dict(source.params)
    for name, spec in schema.get("properties", {}).items():
        if spec.get("type") in {"number", "integer"} and name in params:
            ceiling = float(spec["maximum"])
            params[name] = ceiling * BOUNDARY_OVERSHOOT + 1.0
            if spec.get("type") == "integer":
                params[name] = int(params[name])
            return Proposal(source.vector_id, params, BOUNDARY_RATIONALE)
    return None


def sample_params_from_trial(trial: optuna.trial.FrozenTrial, schema: dict) -> dict:
    params: dict = {}
    for name, spec in schema.get("properties", {}).items():
        if spec.get("type") == "array":
            low = trial.params.get(f"{name}_low")
            high = trial.params.get(f"{name}_high")
            if low is not None and high is not None:
                params[name] = [round(float(low), 2), round(float(high), 2)]
            continue
        if name in trial.params:
            params[name] = trial.params[name]
    return params


def _probe_evasion(
    vector_id: str,
    params: dict,
    population,
    window: TimeWindow | None,
    detector,
    round_index: int,
    carrier=None,
) -> float:
    """Realise a short campaign, score it in traffic, and report the share the detector misses.

    Scoring the campaign on its own would leave every velocity feature computed against
    nothing but the campaign itself, so the objective would rank parameter sets on a feature
    distribution no scored event ever sees. The probe is mixed into legitimate traffic for
    the same reason the fidelity gate is."""
    if population is None or window is None or detector is None:
        return 0.0
    injector = INJECTORS.get(vector_id)
    if injector is None:
        return 0.0
    try:
        campaign = injector().inject(
            population, dict(params), window, rng_for(f"offline_search:{vector_id}:{round_index}")
        )
    except (ValueError, KeyError, IndexError):
        return 0.0
    events = campaign.events.head(OFFLINE_PROBE_EVENTS)
    if events.empty:
        return 0.0
    scored = events
    if carrier is not None and not carrier.empty:
        sample = carrier.head(len(events) * PROBE_CARRIER_MULTIPLIER)
        scored = pd.concat([sample, events], ignore_index=True).sort_values("event_ts")
        scored = scored.reset_index(drop=True)
    try:
        scores = detector.score(scored)
    except (ValueError, KeyError):
        return 0.0
    fraud = scored["is_fraud"].to_numpy(dtype=bool)
    if not fraud.any():
        return 0.0
    return float((scores[fraud] < detector.threshold).mean())
