from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class TimeWindow:
    start: datetime
    end: datetime

    def duration_seconds(self) -> float:
        return (self.end - self.start).total_seconds()

    def contains(self, ts: datetime) -> bool:
        return self.start <= ts < self.end


def round_window(round_index: int, sim_start: datetime, sim_days: int, rounds: int) -> TimeWindow:
    """Round r occupies the r-th equal slice of the simulated span."""
    slice_days = sim_days / rounds
    start = sim_start + timedelta(days=slice_days * round_index)
    return TimeWindow(start=start, end=start + timedelta(days=slice_days))
