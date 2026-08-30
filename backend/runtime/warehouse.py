from pathlib import Path
from typing import Literal

import duckdb
import pandas as pd

from backend.runtime.config import load_config
from backend.runtime.errors import WarehouseUnavailable

SCHEMA_DDL: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS entities (
      entity_id     VARCHAR PRIMARY KEY,
      entity_type   VARCHAR NOT NULL,
      created_ts    TIMESTAMP NOT NULL,
      home_country  CHAR(2)  NOT NULL,
      in_blind_cohort BOOLEAN NOT NULL DEFAULT FALSE,
      attributes    JSON     NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS edges (
      src_id VARCHAR NOT NULL, dst_id VARCHAR NOT NULL, edge_type VARCHAR NOT NULL,
      first_seen_ts TIMESTAMP NOT NULL, last_seen_ts TIMESTAMP NOT NULL, weight INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS campaigns (
      campaign_id UUID PRIMARY KEY, vector_id VARCHAR NOT NULL, round INTEGER NOT NULL,
      params JSON NOT NULL, agent_rationale TEXT, n_events INTEGER NOT NULL,
      evasion_rate DOUBLE, fidelity_passed BOOLEAN, in_training_pool BOOLEAN NOT NULL DEFAULT FALSE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS round_metrics (
      run_id VARCHAR NOT NULL, round INTEGER NOT NULL, status VARCHAR NOT NULL,
      pr_auc DOUBLE, pr_auc_blind DOUBLE, fpr_legit DOUBLE,
      evasion_active DOUBLE, evasion_blind DOUBLE,
      fidelity_composite DOUBLE, cost_per_100k DOUBLE, coverage_pct DOUBLE,
      threshold DOUBLE, latency_p99_ms DOUBLE,
      PRIMARY KEY (run_id, round)
    )
    """,
)


def open_warehouse(path: str | None = None) -> duckdb.DuckDBPyConnection:
    target = Path(path or load_config().duckdb_path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        return duckdb.connect(str(target))
    except (OSError, duckdb.Error) as exc:
        raise WarehouseUnavailable(f"cannot open duckdb at {target}: {exc}") from exc


def initialise_schema(conn: duckdb.DuckDBPyConnection) -> None:
    for statement in SCHEMA_DDL:
        conn.execute(statement)


def query_frame(
    conn: duckdb.DuckDBPyConnection, sql: str, params: dict[str, object] | None = None
) -> pd.DataFrame:
    return conn.execute(sql, params or {}).fetch_df()


def write_frame(
    conn: duckdb.DuckDBPyConnection,
    table: str,
    frame: pd.DataFrame,
    mode: Literal["append", "replace"] = "append",
) -> int:
    conn.register("_incoming", frame)
    if mode == "replace":
        conn.execute(f"DELETE FROM {table}")
    conn.execute(f"INSERT INTO {table} SELECT * FROM _incoming")
    conn.unregister("_incoming")
    return len(frame)
