"""Temporal split and label embargo. A random split is a build error."""

from dataclasses import dataclass
from datetime import datetime, timedelta

import pandas as pd

from runtime.config import PayLoopConfig
from schema.ces import apply_label_embargo

LABEL_EMBARGO_DAYS: int = 30
TRAIN_END_DAY: int = 150
VALIDATION_FRACTION: float = 0.20


@dataclass(frozen=True)
class TemporalSplit:
    train: pd.DataFrame
    validation: pd.DataFrame
    test: pd.DataFrame
    cutoff_ts: datetime


def training_cutoff(sim_start: datetime, config: PayLoopConfig) -> datetime:
    """Labels are visible only once the embargo has elapsed by the end of the train window."""
    return sim_start + timedelta(days=config.sim_days - config.label_embargo_days)


def temporal_split(
    frame: pd.DataFrame, sim_start: datetime, config: PayLoopConfig
) -> TemporalSplit:
    working = frame.copy()
    working["event_ts"] = pd.to_datetime(working["event_ts"], utc=True)
    boundary = pd.Timestamp(sim_start) + pd.Timedelta(days=TRAIN_END_DAY)

    train_window = working[working["event_ts"] < boundary]
    test = working[working["event_ts"] >= boundary].reset_index(drop=True)

    cutoff = training_cutoff(sim_start, config)
    embargoed = apply_label_embargo(train_window, cutoff).sort_values("event_ts")
    split_at = int(len(embargoed) * (1.0 - VALIDATION_FRACTION))
    return TemporalSplit(
        train=embargoed.iloc[:split_at].reset_index(drop=True),
        validation=embargoed.iloc[split_at:].reset_index(drop=True),
        test=test,
        cutoff_ts=cutoff,
    )
