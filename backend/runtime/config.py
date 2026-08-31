"""The only module in PayLoop that reads environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class PayLoopConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", frozen=True)

    redis_url: str = "redis://localhost:6379/0"
    duckdb_path: str = "./data/payloop.db"
    run_id: str = "2026-08-31-final"
    api_port: int = 8000
    web_port: int = 3000

    gemini_api_key: str = ""
    red_agent_model: str = "gemini-2.5-flash"
    red_agent_mode: str = "offline"
    red_agent_timeout_s: float = 30.0

    population_seed: int = 42
    sim_days: int = 180
    n_cardholders: int = 50000
    n_merchants: int = 4000
    n_devices: int = 65000
    n_ips: int = 12000
    n_accounts: int = 50000
    n_agents: int = 800
    target_events: int = 2000000
    decline_mix_region: str = "GLOBAL"

    target_fraud_rate_card: float = 0.0015
    target_fraud_rate_upi: float = 0.0040
    target_fraud_rate_rtp: float = 0.0010
    target_fraud_rate_agentic: float = 0.0050
    prevalence_hard_cap: float = 0.01

    # "synthetic" splits legitimate traffic for the gate reference, which means the gate
    # compares the generator against its own output. "real" points the reference at the
    # Sparkov floor partition, which is what makes a degradation ratio mean anything.
    fidelity_floor_source: str = "synthetic"
    real_data_dir: str = "./data/real"

    fidelity_ks_max: float = 0.10
    fidelity_pcd_max: float = 0.15
    fidelity_behavioral_max: float = 10.0
    fidelity_tstr_min_ratio: float = 0.90
    fidelity_discriminator_auc_max: float = 0.65
    fidelity_mia_auc_max: float = 0.55
    mia_min_rows: int = 5000

    label_embargo_days: int = 30
    blind_holdout_vectors: str = "V07"
    blind_holdout_entity_frac: float = 0.10

    loop_rounds: int = 6
    loop_proposals_per_round: int = 6
    loop_hardest_k: int = 3

    gnn_enabled: bool = True
    gnn_min_lift_prauc: float = 0.03
    lgbm_learning_rate: float = 0.03
    lgbm_num_leaves: int = 63
    lgbm_min_child_samples: int = 256
    lgbm_early_stopping_rounds: int = 32
    iforest_contamination: float = 0.008

    cost_chargeback_fee: float = 25.0
    cost_merchant_margin: float = 0.22
    cost_p_attrition: float = 0.32
    cost_customer_ltv: float = 1800.0

    ladder_approve_max: float = 0.30
    ladder_stepup_max: float = 0.70
    ladder_hold_max: float = 0.90

    scoring_latency_budget_ms: float = 50.0
    bench_iterations: int = 10000
    bench_warmup: int = 500

    hll_ttl_seconds: int = 86400

    party_issuer_id: str = "ISS_007"
    party_acquirer_id: str = "ACQ_014"

    @property
    def blind_holdout_vector_ids(self) -> list[str]:
        return [v.strip() for v in self.blind_holdout_vectors.split(",") if v.strip()]


@lru_cache(maxsize=1)
def load_config() -> PayLoopConfig:
    return PayLoopConfig()
