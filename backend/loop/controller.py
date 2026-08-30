"""Round orchestration: bootstrap, run_round, finalise."""

import gc
import json
import logging
import platform
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from backend.api import events as sse
from backend.defend.bench import HLL_BENCH_ITERATIONS, benchmark_feature_lookup, run_benchmark
from backend.defend.ensemble import ARTIFACTS_DIR, MODEL_FILENAME, Detector
from backend.defend.explain import background_sample, reason_dictionary_payload, shap_values, top_reasons
from backend.defend.features import FEATURE_NAMES, FeatureContext, compute_features
from backend.defend.gbdt import platt_coefficients
from backend.defend.ladder import action_for_band, band_for_score
from backend.defend.scopes import evaluate_all_scopes
from backend.defend.split import TRAIN_END_DAY
from backend.fidelity.ablation import run_ablation
from backend.fidelity.gate import run_gate
from backend.generate.behavior import emit_legitimate, simulation_window
from backend.generate.graph import edge_table, graph_metrics, population_graph
from backend.generate.holdout import partition_blind_cohort
from backend.generate.injectors import DEFAULT_PARAMS, INJECTORS, RAIL_OF_VECTOR
from backend.generate.population import SIM_START, Population, build_population, entities_frame
from backend.generate.prevalence import campaign_budget, enforce_caps, subsample_campaign
from backend.generate.red_agent.constraints import Proposal, partition_valid, set_population_account_count
from backend.generate.red_agent.offline_search import search_offline
from backend.loop.metrics import (
    ROUNDS_FILE,
    SSE_LOG_FILE,
    STATUS_COMPLETED,
    STATUS_FIDELITY_REJECTED,
    STATUS_MODEL_REGRESSION,
    STATUS_NO_VALID_PROPOSALS,
    RoundMetrics,
)
from backend.registry.coverage import coverage_for_run
from backend.registry.loader import load_vectors
from backend.runtime.artifacts import (
    append_jsonl,
    read_json,
    read_jsonl,
    reset_artifact,
    write_json,
    write_manifest,
)
from backend.runtime.config import PayLoopConfig, load_config
from backend.runtime.errors import InjectorProducedNothing, RedAgentUnavailable, WarehouseUnavailable
from backend.runtime.seeding import rng_for
from backend.runtime.timewindows import TimeWindow, round_window
from backend.runtime.warehouse import initialise_schema, open_warehouse, write_frame

LOGGER = logging.getLogger("payloop.loop")

ALERT_QUEUE_SIZE: int = 200
REFERENCE_SAMPLE_ROWS: int = 60_000
REFERENCE_ENTITY_FRACTION: float = 0.5
# The gate only ever compares samples, and the carrier is drawn at a small multiple of a
# campaign's size. Bounding both keeps their memory flat as the simulated volume grows.
CARRIER_POOL_ROWS: int = 200_000
CARRIER_MULTIPLIER: float = 24.0
DISTRIBUTION_BINS: int = 40
HOUR_BINS: int = 24
DEGREE_BINS: int = 30
DEFAULT_PROPOSAL_VECTORS: tuple[str, ...] = (
    "V01",
    "V28",
    "V05",
    "V19",
    "V18",
    "V06",
    "V02",
    "V31",
    "V22",
    "V20",
    "V21",
)
DATA_DIR: Path = Path(__file__).resolve().parent.parent.parent / "data"
RUN_ARTIFACTS: tuple[str, ...] = (
    "rounds.jsonl",
    "scope_matrix.json",
    "per_vector_recall.json",
    "coverage.json",
    "latency.json",
    "ablation.json",
    "reason_codes.json",
    "alerts.jsonl",
    "distributions.json",
)


@dataclass
class LoopContext:
    config: PayLoopConfig
    run_id: str
    population: Population
    sim_start: datetime
    pool: pd.DataFrame
    blind_events: pd.DataFrame
    reference: pd.DataFrame
    carrier: pd.DataFrame
    evaluation_legit: pd.DataFrame
    detector: Detector
    metrics: RoundMetrics
    context: FeatureContext
    agent_mode: str
    agent_hints: list[str] = field(default_factory=list)
    round_records: list[dict] = field(default_factory=list)


def persist(table: str, frame: pd.DataFrame, mode: str = "append") -> int:
    """Mirror a frame into the DuckDB supporting tables. The warehouse is a convenience for
    querying a run afterwards; the artefacts on disk remain the source of truth, so an
    unavailable warehouse degrades to a warning rather than losing the round."""
    if frame.empty:
        return 0
    try:
        connection = open_warehouse()
        initialise_schema(connection)
        written = write_frame(connection, table, frame, mode=mode)
        connection.close()
        return written
    except (WarehouseUnavailable, duckdb.Error) as exc:
        LOGGER.warning("warehouse write to %s skipped: %s", table, exc)
        return 0


def campaign_rows(
    campaigns, round_index: int, active, hardest_ids: set[str], passed: bool
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "campaign_id": str(campaign.campaign_id),
                "vector_id": campaign.vector_id,
                "round": round_index,
                "params": json.dumps(campaign.params, sort_keys=True, default=str),
                "agent_rationale": campaign.rationale,
                "n_events": int(len(campaign.events)),
                "evasion_rate": float((active.evasion or {}).get(str(campaign.campaign_id), 0.0))
                if active
                else None,
                "fidelity_passed": passed,
                "in_training_pool": str(campaign.campaign_id) in hardest_ids,
            }
            for campaign in campaigns
        ]
    )


def round_metric_row(record: dict) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "run_id": record["run_id"],
                "round": record["round"],
                "status": record["status"],
                "pr_auc": record["pr_auc"],
                "pr_auc_blind": record["pr_auc_blind"],
                "fpr_legit": record["fpr_legit"],
                "evasion_active": record["evasion_active"],
                "evasion_blind": record["evasion_blind"],
                "fidelity_composite": record["fidelity_composite"],
                "cost_per_100k": record["cost_per_100k"],
                "coverage_pct": record["coverage_pct"],
                "threshold": record["threshold"],
                "latency_p99_ms": record["latency_p99_ms"],
            }
        ]
    )


def emit(context: LoopContext, event: str, payload: dict) -> None:
    append_jsonl(context.run_id, SSE_LOG_FILE, payload)


def git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(DATA_DIR.parent), text=True, timeout=10
        ).strip()
    except (subprocess.SubprocessError, OSError, FileNotFoundError):
        return "uncommitted"


def host_description() -> str:
    return f"{platform.processor() or platform.machine()}, Python {platform.python_version()}"


def build_feature_context(population: Population, events: pd.DataFrame) -> FeatureContext:
    graph = population_graph(population, events.head(REFERENCE_SAMPLE_ROWS))
    ranks, sizes = graph_metrics(graph)
    holders = population.cardholders.set_index("entity_id")
    merchants = population.merchants.set_index("entity_id")
    first_seen = pd.concat(
        [
            pd.Series(merchants["created_ts"].to_numpy(), index=merchants.index),
            pd.Series(
                population.merchants["created_ts"].to_numpy(),
                index=population.merchants["terminal_id"].to_numpy(),
            ),
            pd.Series(
                population.accounts["created_ts"].to_numpy(),
                index=population.accounts["entity_id"].to_numpy(),
            ),
        ]
    )
    return FeatureContext(
        circadian_mu=holders["circadian_mu"],
        circadian_kappa=holders["circadian_kappa"],
        merchant_control_strength=merchants["control_strength"],
        merchant_lat=merchants["lat"],
        merchant_lon=merchants["lon"],
        entity_first_seen=first_seen[~first_seen.index.duplicated()],
        pagerank=ranks,
        component_size=sizes,
    )


def bootstrap(config: PayLoopConfig) -> LoopContext:
    run_id = config.run_id
    for artefact in (ROUNDS_FILE, SSE_LOG_FILE, "fidelity_report.json"):
        reset_artifact(run_id, artefact)
    write_manifest(run_id, config, git_sha(), host_description())

    population = build_population(config)
    set_population_account_count(population.account_count())
    window = simulation_window(config, SIM_START)
    partition = partition_blind_cohort(population, config, window)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "campaigns").mkdir(parents=True, exist_ok=True)
    entities = entities_frame(population)
    entities.to_parquet(DATA_DIR / "entities.parquet", index=False)
    partition.pool_events.to_parquet(DATA_DIR / "events_legit.parquet", index=False)
    partition.blind_events.to_parquet(DATA_DIR / "events_blind.parquet", index=False)
    edges = edge_table(partition.pool_events.head(REFERENCE_SAMPLE_ROWS))
    edges.to_parquet(DATA_DIR / "edges.parquet", index=False)
    # Entities and edges are a full snapshot of a deterministic population, so a re-run
    # replaces them; campaigns and round metrics accumulate across rounds.
    persist("entities", entities, mode="replace")
    persist("edges", edges, mode="replace")

    reference, carrier = _split_reference_and_carrier(partition.pool_events)
    evaluation_legit = _evaluation_window(partition.pool_events)

    context_features = build_feature_context(population, partition.pool_events)
    pool = _seed_pool(population, partition.pool_events, window, config)
    blind_events = _seed_blind(population, partition.blind_events, window, config)
    # The partition's own frames are now duplicated inside pool, reference, carrier and the
    # evaluation window. Releasing them keeps one copy of the traffic resident instead of two.
    del partition
    gc.collect()

    detector = Detector(config, context=context_features, sim_start=SIM_START).fit(
        pool, blind=blind_events
    )
    detector.export_onnx()

    vectors = load_vectors()
    coverage_pct = sum(1 for v in vectors if v.injector) / len(vectors)
    return LoopContext(
        config=config,
        run_id=run_id,
        population=population,
        sim_start=SIM_START,
        pool=pool,
        blind_events=blind_events,
        reference=reference,
        carrier=carrier,
        evaluation_legit=evaluation_legit,
        detector=detector,
        metrics=RoundMetrics(run_id, round(coverage_pct, 4), config.red_agent_mode),
        context=context_features,
        agent_mode=config.red_agent_mode,
    )


def _evaluation_window(legit: pd.DataFrame) -> pd.DataFrame:
    """Legitimate traffic after the temporal split boundary.

    Scoring a round's campaigns against legitimate rows the model was fitted on inflates
    PR-AUC to near one and makes the false-positive rate meaningless: the detector has
    memorised those rows. The evaluation window is the only legitimate traffic the model
    has never seen."""
    boundary = pd.Timestamp(SIM_START) + pd.Timedelta(days=TRAIN_END_DAY)
    held = legit[pd.to_datetime(legit["event_ts"], utc=True) >= boundary]
    return held.reset_index(drop=True)


def _split_reference_and_carrier(legit: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split legitimate traffic into a gate reference and a campaign carrier, by entity.

    The partitions must be disjoint, or the privacy layer's distance-to-closest-record
    reads zero for a tautological reason. They must also split whole entities rather than
    rows: thinning an entity's event sequence destroys the within-entity structure the
    behavioural layer exists to measure, and the batch would fail for the wrong reason."""
    rng = rng_for("loop:reference")
    entities = legit["payer_entity_id"].astype(str)
    unique = np.sort(entities.unique())
    held = set(unique[rng.random(unique.size) < REFERENCE_ENTITY_FRACTION].tolist())
    selector = entities.isin(held).to_numpy()
    reference = _carrier_entities(legit[selector], REFERENCE_SAMPLE_ROWS, rng)
    carrier = _carrier_entities(legit[~selector], CARRIER_POOL_ROWS, rng)
    return reference, carrier


def _carrier_entities(
    carrier: pd.DataFrame, target_rows: int, rng: np.random.Generator
) -> pd.DataFrame:
    """Whole entities up to the row budget, so every carried sequence stays intact."""
    entities = carrier["payer_entity_id"].astype(str)
    unique = np.sort(entities.unique())
    if unique.size == 0:
        return carrier.head(0)
    order = rng.permutation(unique.size)
    counts = entities.value_counts()
    running, chosen = 0, []
    for position in order:
        entity = unique[position]
        chosen.append(entity)
        running += int(counts.get(entity, 0))
        if running >= target_rows:
            break
    return carrier[entities.isin(set(chosen)).to_numpy()].reset_index(drop=True)


def _rail_share(vector_id: str, vector_ids: list[str]) -> float:
    rail = RAIL_OF_VECTOR[vector_id]
    siblings = sum(1 for other in vector_ids if RAIL_OF_VECTOR[other] == rail)
    return 1.0 / max(siblings, 1)


def budgeted_campaign(
    campaign, legit: pd.DataFrame, config: PayLoopConfig, vector_ids: list[str], purpose: str
) -> pd.DataFrame:
    """Campaigns are trimmed to their rail's target prevalence before they enter any pool,
    so the caps in generate/prevalence.py stay a backstop rather than the mechanism."""
    budget = campaign_budget(
        legit,
        RAIL_OF_VECTOR[campaign.vector_id],
        config,
        _rail_share(campaign.vector_id, vector_ids),
    )
    return subsample_campaign(campaign.events, budget, purpose)


def _seed_pool(
    population: Population, legit: pd.DataFrame, window: TimeWindow, config: PayLoopConfig
) -> pd.DataFrame:
    """Round-zero pool: legitimate traffic plus one baseline campaign per non-holdout vector."""
    vector_ids = [v for v in INJECTORS if v not in config.blind_holdout_vector_ids]
    campaigns = []
    for vector_id in vector_ids:
        try:
            campaign = INJECTORS[vector_id]().inject(
                population, dict(DEFAULT_PARAMS[vector_id]), window, rng_for(f"round0:{vector_id}")
            )
        except (InjectorProducedNothing, ValueError, KeyError, IndexError) as exc:
            LOGGER.warning("round-0 injector %s produced nothing: %s", vector_id, exc)
            continue
        campaigns.append(
            budgeted_campaign(campaign, legit, config, vector_ids, f"round0:{vector_id}")
        )
    pool = pd.concat([legit, *campaigns], ignore_index=True).sort_values("event_ts")
    return enforce_caps(pool.reset_index(drop=True), config)


def _seed_blind(
    population: Population, blind_legit: pd.DataFrame, window: TimeWindow, config: PayLoopConfig
) -> pd.DataFrame:
    """The blind cohort carries its own legitimate traffic plus the held-out V07 family."""
    vector_ids = list(config.blind_holdout_vector_ids)
    campaigns = []
    for vector_id in vector_ids:
        injector = INJECTORS.get(vector_id)
        if injector is None:
            continue
        campaign = injector().inject(
            population, dict(DEFAULT_PARAMS[vector_id]), window, rng_for(f"blind:{vector_id}")
        )
        campaigns.append(
            budgeted_campaign(campaign, blind_legit, config, vector_ids, f"blind:{vector_id}")
        )
    blind = pd.concat([blind_legit, *campaigns], ignore_index=True).sort_values("event_ts")
    return enforce_caps(blind.reset_index(drop=True), config)


def propose_or_search(
    context: LoopContext, state, round_index: int, window: TimeWindow
) -> list[Proposal]:
    schemas = {
        vector_id: INJECTORS[vector_id].param_schema
        for vector_id in DEFAULT_PROPOSAL_VECTORS
        if vector_id in INJECTORS
    }
    if context.config.red_agent_mode == "live":
        from backend.generate.red_agent.client import propose

        try:
            proposals = propose(state, schemas, context.config.loop_proposals_per_round)
            context.agent_mode = "live"
            context.metrics.agent_mode = "live"
            return proposals
        except RedAgentUnavailable as exc:
            LOGGER.warning("red agent unavailable, falling back to offline search: %s", exc)
    context.agent_mode = "offline"
    context.metrics.agent_mode = "offline"
    return search_offline(
        state,
        schemas,
        k=context.config.loop_proposals_per_round,
        population=context.population,
        window=window,
        detector=context.detector,
        round_index=round_index,
        carrier=context.carrier,
    )


def _carrier_sample(context: LoopContext, batch_size: int, round_index: int) -> pd.DataFrame:
    """The gate scores what would actually be appended: the campaign mixed into legitimate
    traffic at its realised share, not raw fraud rows against a legitimate reference."""
    rng = rng_for(f"loop:carrier:{round_index}")
    size = min(len(context.carrier), int(batch_size * CARRIER_MULTIPLIER))
    if size <= 0:
        return context.carrier.head(0)
    return _carrier_entities(context.carrier, size, rng)


def _no_valid_proposals(context, round_index, started, rejected, total) -> dict:
    return context.metrics.record(
        round_index,
        status=STATUS_NO_VALID_PROPOSALS,
        started=started,
        rejected=rejected,
        proposals_total=total,
        detector=context.detector,
    )


def realise_campaigns(
    context: LoopContext,
    valid: list[Proposal],
    window: TimeWindow,
    round_index: int,
    rejected: list,
) -> list:
    """Turn surviving proposals into campaigns, trimmed to their rail's prevalence budget."""
    legit = context.pool[~context.pool["is_fraud"]]
    vector_ids = [item.vector_id for item in valid]
    campaigns = []
    for item in valid:
        purpose = f"round{round_index}:{item.vector_id}"
        try:
            campaign = INJECTORS[item.vector_id]().inject(
                context.population, dict(item.params), window, rng_for(purpose)
            )
            campaign.events = budgeted_campaign(
                campaign, legit, context.config, vector_ids, purpose
            )
            campaigns.append(campaign)
        except (InjectorProducedNothing, ValueError, KeyError, IndexError) as exc:
            rejected.append(
                {
                    "index": len(rejected),
                    "vector_id": item.vector_id,
                    "reason": f"injector produced nothing: {exc}",
                    "rule": "injector returned zero events",
                    "params": item.params,
                }
            )
            emit(
                context,
                sse.EVENT_PROPOSAL_REJECTED,
                sse.proposal_rejected(round_index, rejected[-1]),
            )
    return campaigns


def gate_batch(context: LoopContext, batch: pd.DataFrame, round_index: int):
    """Run the six layers on the batch as it would be appended: campaigns mixed into a
    matched slice of legitimate traffic."""
    mixed = (
        pd.concat([_carrier_sample(context, len(batch), round_index), batch], ignore_index=True)
        .sort_values("event_ts")
        .reset_index(drop=True)
    )
    gate = run_gate(mixed, context.reference, round_index, context.config)
    emit(context, sse.EVENT_FIDELITY, sse.fidelity(round_index, gate))
    append_jsonl(
        context.run_id, "fidelity_report.jsonl", {"round": round_index, **gate.as_payload()}
    )
    return gate


def score_round(context: LoopContext, batch: pd.DataFrame):
    """Score the round against legitimate traffic the model has never been fitted on."""
    scored = (
        pd.concat([context.evaluation_legit, batch], ignore_index=True)
        .sort_values("event_ts")
        .reset_index(drop=True)
    )
    return context.detector.evaluate(scored), context.detector.evaluate(context.blind_events)


def extend_pool(context: LoopContext, campaigns: list, active, round_index: int) -> list:
    """Append the hardest campaigns and keep everything already there.

    The original population and round-1 campaigns stay in the pool permanently: replay of
    older typologies is what stops the detector forgetting them as new ones arrive."""
    hardest = sorted(
        campaigns, key=lambda c: active.evasion.get(str(c.campaign_id), 0.0), reverse=True
    )[: context.config.loop_hardest_k]
    for campaign in campaigns:
        campaign.events.to_parquet(
            DATA_DIR / "campaigns" / f"round_{round_index}_{campaign.vector_id}.parquet",
            index=False,
        )
    context.pool = enforce_caps(
        pd.concat([context.pool, *(c.events for c in hardest)], ignore_index=True)
        .sort_values("event_ts")
        .reset_index(drop=True),
        context.config,
    )
    return hardest


def round_latency_p99(context: LoopContext) -> float | None:
    """The inline scorer is re-benchmarked each round because each round may replace it.

    Ten thousand single-row calls cost well under a second, so there is no reason to quote
    a stale figure or leave the field empty."""
    model_path = ARTIFACTS_DIR / MODEL_FILENAME
    if not model_path.exists() or context.detector.channel_a is None:
        return None
    features = compute_features(context.pool.head(1), context.context)
    measurement = run_benchmark(
        str(model_path),
        features.to_numpy("float32")[0],
        platt_coefficients(context.detector.channel_a.model),
    )
    return float(measurement["p99_ms"])


def _candidate_is_kept(context: LoopContext, candidate: Detector, batch: pd.DataFrame) -> bool:
    """Both models scored on the same held-out frame, at the same moment.

    Comparing a freshly fitted candidate's own validation score against the incumbent's
    stored one is not a comparison: the incumbent's was measured on a smaller pool, and the
    slice each was calibrated on is not held out from it."""
    frame = (
        pd.concat([context.evaluation_legit, batch], ignore_index=True)
        .sort_values("event_ts")
        .reset_index(drop=True)
    )
    return candidate.evaluate(frame).pr_auc >= context.detector.evaluate(frame).pr_auc


def run_round(context: LoopContext, round_index: int) -> dict:
    started = datetime.now(UTC)
    state = context.detector.state()
    emit(
        context,
        sse.EVENT_ROUND_START,
        sse.round_start(context.run_id, round_index, context.agent_mode, state),
    )

    window = round_window(
        round_index, context.sim_start, context.config.sim_days, context.config.loop_rounds
    )
    proposals = propose_or_search(context, state, round_index, window)
    valid, rejected = partition_valid(proposals)
    for position, item in enumerate(valid):
        emit(context, sse.EVENT_PROPOSAL, sse.proposal(round_index, position, item))
    for item in rejected:
        emit(context, sse.EVENT_PROPOSAL_REJECTED, sse.proposal_rejected(round_index, item))
    if not valid:
        return _no_valid_proposals(context, round_index, started, rejected, len(proposals))

    campaigns = realise_campaigns(context, valid, window, round_index, rejected)
    if not campaigns:
        return _no_valid_proposals(context, round_index, started, rejected, len(proposals))

    batch = pd.concat([c.events for c in campaigns], ignore_index=True)
    gate = gate_batch(context, batch, round_index)
    if not gate.passed:
        context.agent_hints = gate.failure_hints()
        emit(context, sse.EVENT_ROUND_REJECTED, sse.round_rejected(round_index, gate))
        return context.metrics.record(
            round_index,
            status=STATUS_FIDELITY_REJECTED,
            started=started,
            gate=gate,
            campaigns=campaigns,
            rejected=rejected,
            proposals_total=len(proposals),
            detector=context.detector,
        )

    active, blind = score_round(context, batch)
    hardest = extend_pool(context, campaigns, active, round_index)

    candidate = Detector(context.config, context=context.context, sim_start=context.sim_start).fit(
        context.pool, blind=context.blind_events
    )
    retained = _candidate_is_kept(context, candidate, batch)
    if retained:
        context.detector = candidate
        context.detector.export_onnx()
    gc.collect()

    record = context.metrics.record(
        round_index,
        status=STATUS_COMPLETED if retained else STATUS_MODEL_REGRESSION,
        started=started,
        gate=gate,
        active=active,
        blind=blind,
        campaigns=campaigns,
        hardest=hardest,
        rejected=rejected,
        detector=context.detector,
        proposals_total=len(proposals),
        latency_p99_ms=round_latency_p99(context),
    )
    emit(context, sse.EVENT_ROUND_RESULT, sse.round_result(record))
    hardest_ids = {str(campaign.campaign_id) for campaign in hardest}
    persist("campaigns", campaign_rows(campaigns, round_index, active, hardest_ids, True))
    persist("round_metrics", round_metric_row(record))
    context.round_records.append(record)
    return record


def _write_detector_reports(context: LoopContext, active, blind) -> dict[str, float]:
    """Per-vector recall, the headline metrics, and the coverage matrix they feed."""
    run_id = context.run_id
    per_vector = {**active.per_vector_recall, **blind.per_vector_recall}
    write_json(
        run_id,
        "per_vector_recall.json",
        {
            "recall": {k: round(v, 4) for k, v in per_vector.items()},
            "precision_at_k": round(active.precision_at_k, 4),
            "recall_at_95_precision": round(active.recall_at_95_precision, 4),
            "fp_tp_ratio": round(active.fp_tp_ratio, 3)
            if np.isfinite(active.fp_tp_ratio)
            else None,
            "calibration": {
                "brier_calibrated": round(context.detector.brier_calibrated, 6),
                "brier_uncalibrated": round(context.detector.brier_uncalibrated, 6),
                "reliability": context.detector.reliability,
            },
        },
    )
    write_json(run_id, "coverage.json", coverage_for_run(run_id, per_vector))
    return per_vector


def _write_gate_reports(context: LoopContext) -> bool:
    """The per-round gate history and the ablation that proves the gate can fail."""
    run_id = context.run_id
    result, payload = run_ablation(context.carrier, context.reference, context.config)
    write_json(run_id, "ablation.json", payload)
    write_json(
        run_id, "fidelity_report.json", {"rounds": read_jsonl(run_id, "fidelity_report.jsonl")}
    )
    reset_artifact(run_id, "fidelity_report.jsonl")
    return result.passed


def _gnn_result(context: LoopContext) -> dict:
    lift = context.detector.gnn_measured_lift
    return {
        "enabled": context.detector.gnn_enabled,
        "measured_lift_pr_auc": round(lift, 4) if lift is not None else None,
        "kill_threshold": context.config.gnn_min_lift_prauc,
    }


def finalise(context: LoopContext) -> dict:
    run_id = context.run_id
    campaigns = _pool_campaigns(context)
    evaluation_frame = pd.concat(
        [context.evaluation_legit, campaigns, context.blind_events], ignore_index=True
    )

    scopes = evaluate_all_scopes(
        context.pool, context.config, context.context, sim_start=context.sim_start
    )
    write_json(run_id, "scope_matrix.json", scopes.as_payload())

    active = context.detector.evaluate(
        pd.concat([context.evaluation_legit, campaigns], ignore_index=True)
        .sort_values("event_ts")
        .reset_index(drop=True)
    )
    blind = context.detector.evaluate(context.blind_events)
    _write_detector_reports(context, active, blind)

    write_json(run_id, "reason_codes.json", _reason_payload(context))
    _write_alerts(context, evaluation_frame)
    write_json(run_id, "distributions.json", _distributions(context))
    write_json(run_id, "latency.json", _benchmark(context))
    ablation_passed = _write_gate_reports(context)

    rounds = read_jsonl(run_id, ROUNDS_FILE)
    completed = sum(1 for record in rounds if record["status"] == STATUS_COMPLETED)
    rejected = sum(1 for record in rounds if record["status"] == STATUS_FIDELITY_REJECTED)
    gnn = _gnn_result(context)
    write_json(run_id, "gnn.json", gnn)

    emit(context, sse.EVENT_DONE, sse.done(run_id, completed, rejected, gnn, RUN_ARTIFACTS))
    return {
        "run_id": run_id,
        "rounds_completed": completed,
        "rounds_rejected": rejected,
        "gnn": gnn,
        "ablation_passed": ablation_passed,
    }


def _pool_campaigns(context: LoopContext) -> pd.DataFrame:
    return context.pool[context.pool["is_fraud"]].reset_index(drop=True)


def _reason_payload(context: LoopContext) -> dict:
    payload = reason_dictionary_payload()
    payload["run_id"] = context.run_id
    return payload


def _write_alerts(context: LoopContext, frame: pd.DataFrame) -> None:
    reset_artifact(context.run_id, "alerts.jsonl")
    rng = rng_for("loop:alerts")
    sample = frame
    if len(sample) > REFERENCE_SAMPLE_ROWS:
        sample = sample.iloc[
            np.sort(rng.choice(len(sample), size=REFERENCE_SAMPLE_ROWS, replace=False))
        ]
    sample = sample.reset_index(drop=True)
    scores = context.detector.score(sample)
    features = compute_features(sample, context.context)
    order = np.argsort(-scores)[:ALERT_QUEUE_SIZE]
    design = features.to_numpy("float32")
    try:
        values = shap_values(
            context.detector.channel_a.booster.booster_,
            design[order],
            background_sample(design, rng),
        )
    except (ValueError, RuntimeError, MemoryError):
        values = np.zeros((len(order), design.shape[1]))

    for position, index in enumerate(order):
        row = sample.iloc[int(index)]
        band = band_for_score(float(scores[index]))
        append_jsonl(
            context.run_id,
            "alerts.jsonl",
            {
                "event_id": str(row["event_id"]),
                "event_ts": str(row["event_ts"]),
                "rail": str(row["rail"]),
                "amount": float(row["amount"]),
                "currency": str(row["currency"]),
                "score": round(float(scores[index]), 4),
                "band": str(band),
                "action": action_for_band(band),
                "is_fraud": bool(row["is_fraud"]),
                "vector_id": None if pd.isna(row.get("vector_id")) else str(row.get("vector_id")),
                "reason_codes": top_reasons(
                    values[position], list(FEATURE_NAMES), features.iloc[int(index)]
                ),
                "invariants": {
                    "cart_hash_match": bool(features.iloc[int(index)]["cart_hash_mismatch"] == 0),
                    "mandate_in_scope": bool(
                        features.iloc[int(index)]["mandate_scope_breach"] == 0
                    ),
                    "nonce_reused": bool(features.iloc[int(index)]["nonce_reused"] == 1),
                    "attestation_valid": bool(
                        features.iloc[int(index)]["attestation_invalid"] == 0
                    ),
                },
            },
        )


def _histogram(values: np.ndarray, bins: int, low: float, high: float) -> dict:
    counts, edges = np.histogram(
        values[np.isfinite(values)], bins=bins, range=(low, high), density=True
    )
    return {
        "edges": [round(float(e), 4) for e in edges],
        "density": [round(float(c), 6) for c in counts],
    }


def _distributions(context: LoopContext) -> dict:
    real = context.reference
    synthetic = context.pool[context.pool["is_fraud"]]
    if synthetic.empty:
        synthetic = context.pool.head(len(real))

    def log_amount(frame: pd.DataFrame) -> np.ndarray:
        return np.log10(
            pd.to_numeric(frame["amount"], errors="coerce").clip(lower=0.01).to_numpy("float64")
        )

    def hours(frame: pd.DataFrame) -> np.ndarray:
        return pd.to_datetime(frame["event_ts"], utc=True).dt.hour.to_numpy("float64")

    def log_iet(frame: pd.DataFrame) -> np.ndarray:
        deltas = (
            frame.sort_values("event_ts")
            .groupby("payer_entity_id", sort=False)["event_ts"]
            .diff()
            .dt.total_seconds()
            .dropna()
            .to_numpy("float64")
        )
        return np.log10(np.clip(deltas, 1.0, None))

    def log_degree(frame: pd.DataFrame) -> np.ndarray:
        degree = frame["payee_entity_id"].value_counts().to_numpy("float64")
        return np.log10(np.clip(degree, 1.0, None))

    return {
        "amount": {
            "real": _histogram(log_amount(real), DISTRIBUTION_BINS, -1.0, 5.0),
            "synthetic": _histogram(log_amount(synthetic), DISTRIBUTION_BINS, -1.0, 5.0),
        },
        "hour_of_day": {
            "real": _histogram(hours(real), HOUR_BINS, 0.0, 24.0),
            "synthetic": _histogram(hours(synthetic), HOUR_BINS, 0.0, 24.0),
        },
        "interarrival": {
            "real": _histogram(log_iet(real), DISTRIBUTION_BINS, 0.0, 6.0),
            "synthetic": _histogram(log_iet(synthetic), DISTRIBUTION_BINS, 0.0, 6.0),
        },
        "merchant_degree": {
            "real": _histogram(log_degree(real), DEGREE_BINS, 0.0, 5.0),
            "synthetic": _histogram(log_degree(synthetic), DEGREE_BINS, 0.0, 5.0),
            "power_law_alpha": _power_law_alpha(real),
        },
    }


def _power_law_alpha(frame: pd.DataFrame) -> float:
    import powerlaw

    degree = frame["payee_entity_id"].value_counts().to_numpy("float64")
    if degree.size < 20:
        return 0.0
    fit = powerlaw.Fit(degree, verbose=False)
    return round(float(fit.alpha), 4)


def _benchmark(context: LoopContext) -> dict:
    model_path = ARTIFACTS_DIR / MODEL_FILENAME
    features = compute_features(context.pool.head(1), context.context)
    measurement = run_benchmark(
        str(model_path),
        features.to_numpy("float32")[0],
        platt_coefficients(context.detector.channel_a.model),
    )
    measurement["host"] = host_description()
    measurement["feature_lookup"] = benchmark_feature_lookup(
        context.config.redis_url, HLL_BENCH_ITERATIONS, context.config.bench_warmup
    )
    return measurement


def run(config: PayLoopConfig | None = None) -> str:
    config = config or load_config()
    context = bootstrap(config)
    for round_index in range(config.loop_rounds):
        run_round(context, round_index)
    finalise(context)
    return context.run_id


STAGES: tuple[str, ...] = ("generate", "fidelity", "defend", "scopes", "bench", "report")


def stage(name: str, config: PayLoopConfig | None = None) -> dict:
    """Run one make-target stage on its own. bootstrap is deterministic given the seed, so
    a standalone stage rebuilds the same population and pool the full run would have."""
    config = config or load_config()
    if name not in STAGES:
        raise ValueError(f"unknown stage {name}; expected one of {STAGES}")
    if name == "report":
        return _rebuild_reports(config)

    context = bootstrap(config)
    if name in {"generate", "defend"}:
        return {
            "stage": name,
            "pool_events": len(context.pool),
            "threshold": context.detector.threshold,
        }
    if name == "fidelity":
        result, payload = run_ablation(context.carrier, context.reference, config)
        write_json(config.run_id, "ablation.json", payload)
        return {"stage": name, "ablation_passed": result.passed, "layers": payload["layers"]}
    if name == "scopes":
        scopes = evaluate_all_scopes(
            context.pool, config, context.context, sim_start=context.sim_start
        )
        write_json(config.run_id, "scope_matrix.json", scopes.as_payload())
        return {"stage": name, "vectors": len(scopes.matrix), "status": scopes.status}
    latency = _benchmark(context)
    write_json(config.run_id, "latency.json", latency)
    return {"stage": name, **latency}


def _rebuild_reports(config: PayLoopConfig) -> dict:
    """Regenerate coverage.json from the committed run without re-running the loop."""
    recall = read_json(config.run_id, "per_vector_recall.json")
    payload = coverage_for_run(config.run_id, dict(recall.get("recall", {})))
    write_json(config.run_id, "coverage.json", payload)
    return {"stage": "report", "coverage_pct": payload["coverage_pct"]}


def run_from_request(request: dict) -> dict:
    """Queue entry point for POST /loop/run."""
    config = load_config().model_copy(
        update={
            "run_id": request["run_id"],
            "loop_rounds": int(request["rounds"]),
            "loop_proposals_per_round": int(request["proposals_per_round"]),
            "red_agent_mode": request.get("agent_mode", "offline"),
        }
    )
    context = bootstrap(config)
    for round_index in range(config.loop_rounds):
        run_round(context, round_index)
    return finalise(context)


def simulate_batch(request: dict) -> dict:
    """Queue entry point for POST /simulate: realise the requested vectors over a window,
    run the gate on the result, and write the batch to data/campaigns/."""
    config = load_config()
    population = build_population(config)
    set_population_account_count(population.account_count())
    window = TimeWindow(start=SIM_START, end=SIM_START + timedelta(days=int(request["days"])))
    intensity = float(request["intensity"])
    reference, carrier = _split_reference_and_carrier(
        emit_legitimate(population, window, target_events=int(config.target_events * intensity))
    )
    vector_ids = [v for v in request["vectors"] if v in INJECTORS]
    campaigns = []
    for vector_id in vector_ids:
        campaign = INJECTORS[vector_id]().inject(
            population, dict(DEFAULT_PARAMS[vector_id]), window, rng_for(f"simulate:{vector_id}")
        )
        campaigns.append(
            budgeted_campaign(campaign, carrier, config, vector_ids, f"simulate:{vector_id}")
        )

    batch = pd.concat([carrier, *campaigns], ignore_index=True).sort_values("event_ts")
    batch = enforce_caps(batch.reset_index(drop=True), config)
    gate = run_gate(batch, reference, 0, config)
    task_seed = request.get("seed") or config.population_seed
    parquet_path = DATA_DIR / "campaigns" / f"task_{task_seed}.parquet"
    batch.to_parquet(parquet_path, index=False)
    return {
        "n_events": int(len(batch)),
        "n_fraud": int(batch["is_fraud"].sum()),
        "prevalence": round(float(batch["is_fraud"].mean()), 6),
        "vectors": vector_ids,
        "fidelity": gate.as_payload(),
        "parquet_path": str(parquet_path.relative_to(DATA_DIR.parent)),
    }
