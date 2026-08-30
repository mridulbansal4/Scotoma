import fs from 'node:fs';
import path from 'node:path';

// Every screen reads committed artefacts from disk at build time. There is no fetch call
// anywhere in this tree: `fetch` to the app's own origin is still a network call, and it
// still fails in a rehearsal with the cable pulled.
export const RUN_DATA_DIR = path.join(process.cwd(), 'data', 'run');

export type ArtifactResult<T> = { data: T; missing: false } | { data: null; missing: true; name: string };

function readText(name: string): string | null {
  const target = path.join(RUN_DATA_DIR, name);
  try {
    return fs.readFileSync(target, 'utf-8');
  } catch {
    return null;
  }
}

export function readJson<T>(name: string): ArtifactResult<T> {
  const text = readText(name);
  if (text === null) return { data: null, missing: true, name };
  try {
    return { data: JSON.parse(text) as T, missing: false };
  } catch {
    return { data: null, missing: true, name };
  }
}

export function readJsonl<T>(name: string): ArtifactResult<T[]> {
  const text = readText(name);
  if (text === null) return { data: null, missing: true, name };
  const rows: T[] = [];
  for (const line of text.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    try {
      rows.push(JSON.parse(trimmed) as T);
    } catch {
      return { data: null, missing: true, name };
    }
  }
  return { data: rows, missing: false };
}

export interface LadderBands {
  approve_max: number;
  stepup_max: number;
  hold_max: number;
}

export interface Manifest {
  run_id: string;
  git_sha: string;
  host: string;
  started_ts: string;
  population_seed: number;
  sim_days: number;
  loop_rounds: number;
  label_embargo_days: number;
  blind_holdout_vectors: string[];
  blind_holdout_entity_frac: number;
  ladder_bands: LadderBands;
  cost_matrix: {
    chargeback_fee: number;
    merchant_margin: number;
    p_attrition: number;
    customer_ltv: number;
  };
  gnn_enabled: boolean;
  gnn_min_lift_prauc: number;
  config_hash: string;
}

export interface CoverageRow {
  vector_id: string;
  name: string;
  status: 'documented' | 'emerging' | 'speculative';
  rails: string[];
  tier: number;
  has_injector: boolean;
  has_expected_features: boolean;
  recall: number | null;
  detected_at_recall_0_6: boolean;
  blind_holdout: boolean;
}

export interface Coverage {
  run_id: string;
  total_vectors: number;
  injector_modules: number;
  injector_classes: number;
  vectors_with_injector: number;
  coverage_pct: number;
  recall_bar: number;
  counts: Record<string, number>;
  rows: CoverageRow[];
}

export interface VectorEntry {
  id: string;
  name: string;
  rails: string[];
  tier: number;
  mechanism: string;
  genai_delta: string;
  observable_signals: string[];
  status: 'documented' | 'emerging' | 'speculative';
  sources: string[];
  sim_difficulty: string;
  injector: string | null;
  expected_features: string[];
  countermeasure: string;
  blind_holdout: boolean;
}

export interface RoundRecord {
  run_id: string;
  round: number;
  status: string;
  agent_mode: string;
  proposals_total: number;
  proposals_valid: number;
  proposals_rejected: { vector_id: string; reason: string }[];
  campaigns: {
    campaign_id: string;
    vector_id: string;
    n_events: number;
    evasion_rate: number | null;
    selected_for_pool: boolean;
  }[];
  fidelity: GatePayload | null;
  fidelity_composite: number | null;
  evasion_active: number | null;
  evasion_blind: number | null;
  pr_auc: number | null;
  pr_auc_blind: number | null;
  fpr_legit: number | null;
  threshold: number | null;
  cost_per_100k: number | null;
  coverage_pct: number;
  latency_p99_ms: number | null;
  latency_source: string | null;
  model_retained: boolean;
  suspicious_pr_auc: boolean;
  per_vector_recall: Record<string, number>;
}

export interface GateLayer {
  passed: boolean;
  [metric: string]: number | boolean;
}

export interface GatePayload {
  passed: boolean;
  shadow_layer: string;
  shadow_failure: boolean;
  composite_behavioral: number;
  layers: Record<string, GateLayer>;
}

export interface AblationPayload extends GatePayload {
  generator: string;
  fit_rows: number;
  sample_rows: number;
  behavioral_max: number;
  tstr_min_ratio: number;
}

export interface FidelityReport {
  rounds: (GatePayload & { round: number })[];
}

export interface ReasonCode {
  code: string;
  label: string;
  feature: string;
  value: number;
  shap: number | null;
}

export interface Alert {
  event_id: string;
  event_ts: string;
  rail: string;
  amount: number;
  currency: string;
  score: number;
  band: string;
  action: string;
  is_fraud: boolean;
  vector_id: string | null;
  reason_codes: ReasonCode[];
  invariants: Record<string, boolean>;
}

export interface PerVectorRecall {
  recall: Record<string, number>;
  precision_at_k: number;
  recall_at_95_precision: number;
  fp_tp_ratio: number | null;
  calibration: {
    brier_calibrated: number;
    brier_uncalibrated: number;
    reliability: {
      bin_lower: number;
      bin_upper: number;
      mean_predicted: number;
      observed_rate: number;
      count: number;
    }[];
  };
}

export interface ScopeMatrix {
  matrix: Record<string, Record<string, number>>;
  collapse: Record<string, boolean>;
  status: Record<
    string,
    { rows: number; positives: number; party_id: string | null; status: string; detail?: string }
  >;
}

export interface Latency {
  source: string;
  path: string;
  p50_ms: number;
  p95_ms: number;
  p99_ms: number;
  budget_ms: number;
  iterations: number;
  warmup: number;
  host: string;
  targets: Record<string, number>;
  feature_lookup: {
    source: 'measured' | 'unavailable';
    reason?: string;
    target_ms: number;
    p50_ms?: number;
    p95_ms?: number;
    p99_ms?: number;
  };
}

export interface GnnResult {
  enabled: boolean;
  measured_lift_pr_auc: number | null;
  kill_threshold: number;
}

export interface Histogram {
  edges: number[];
  density: number[];
}

export interface Distributions {
  amount: { real: Histogram; synthetic: Histogram };
  hour_of_day: { real: Histogram; synthetic: Histogram };
  interarrival: { real: Histogram; synthetic: Histogram };
  merchant_degree: { real: Histogram; synthetic: Histogram; power_law_alpha: number };
}

export interface SseRecord {
  event: string;
  data: Record<string, unknown>;
}

export const loadManifest = () => readJson<Manifest>('manifest.json');
export const loadCoverage = () => readJson<Coverage>('coverage.json');
export const loadVectors = () => readJson<VectorEntry[]>('vectors.json');
export const loadRounds = () => readJsonl<RoundRecord>('rounds.jsonl');
export const loadFidelityReport = () => readJson<FidelityReport>('fidelity_report.json');
export const loadAblation = () => readJson<AblationPayload>('ablation.json');
export const loadDistributions = () => readJson<Distributions>('distributions.json');
export const loadAlerts = () => readJsonl<Alert>('alerts.jsonl');
export const loadPerVectorRecall = () => readJson<PerVectorRecall>('per_vector_recall.json');
export const loadScopeMatrix = () => readJson<ScopeMatrix>('scope_matrix.json');
export const loadLatency = () => readJson<Latency>('latency.json');
export const loadGnn = () => readJson<GnnResult>('gnn.json');
export const loadSseLog = () => readJsonl<SseRecord>('sse_log.jsonl');
