"""Optuna TPE over the same parameter schemas. Mandatory: the demo never depends on a
live network call, and this is also the deterministic optimiser the hybrid design assigns
the numeric work to in the first place."""

import logging
import time

import optuna

from generate.injectors import INJECTORS, PARAM_SCHEMAS
from generate.red_agent.constraints import Proposal, validate
from runtime.config import load_config
from runtime.seeding import rng_for
from runtime.timewindows import TimeWindow

OFFLINE_TRIALS: int = 40
OFFLINE_BUDGET_S: float = 45.0
OFFLINE_PROBE_EVENTS: int = 400
OFFLINE_RATIONALE: str = "offline evolutionary search"

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
            return _probe_evasion(vector_id, params, population, window, detector, round_index)

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
    return [proposal for _, proposal in candidates[:k]]


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
    vector_id: str, params: dict, population, window: TimeWindow | None, detector, round_index: int
) -> float:
    """Realise a short campaign, score it, and report the share the detector misses."""
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
    try:
        scores = detector.score(events)
    except (ValueError, KeyError):
        return 0.0
    return float((scores < detector.threshold).mean())
