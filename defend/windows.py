"""The single implementation of time-window aggregation in PayLoop.

defend/features.py and fidelity/behavioral.py both import from here. A second
implementation anywhere else is a build error.
"""

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

Aggregation = Literal["count", "sum", "mean", "std"]

MISSING_KEY_SENTINEL: str = "__missing__"


@dataclass(frozen=True)
class WindowBounds:
    """Half-open [lo, hi) index ranges into the key-then-time sorted view of a frame."""

    order: np.ndarray
    inverse: np.ndarray
    lo: np.ndarray
    hi: np.ndarray

    def restore(self, sorted_values: np.ndarray) -> np.ndarray:
        return sorted_values[self.inverse]


def window_bounds(frame: pd.DataFrame, key: str, window: str) -> WindowBounds:
    """Index ranges covering [t - window, t) within each key group.

    Groups are separated on a synthetic axis wide enough that a single global
    searchsorted can never reach across a group boundary, which keeps the whole
    computation vectorised instead of looping over millions of groups.
    """
    span_ns = int(pd.Timedelta(window).value)
    timestamps = (
        pd.to_datetime(frame["event_ts"], utc=True).to_numpy("datetime64[ns]").astype("int64")
    )
    codes = pd.factorize(frame[key].astype("object").fillna(MISSING_KEY_SENTINEL))[0]

    order = np.lexsort((timestamps, codes))
    inverse = np.empty_like(order)
    inverse[order] = np.arange(order.size)

    sorted_ts = timestamps[order]
    sorted_codes = codes[order].astype("int64")
    stride = int(sorted_ts.max() - sorted_ts.min()) + 2 * span_ns + 1 if sorted_ts.size else 1
    axis = sorted_codes * stride + sorted_ts

    lo = np.searchsorted(axis, axis - span_ns, side="left")
    # closed='left' excludes the current row, and every row sharing its timestamp, from
    # its own window. Omitting this is how a velocity feature leaks its own label.
    hi = np.searchsorted(axis, axis, side="left")
    return WindowBounds(order=order, inverse=inverse, lo=lo, hi=hi)


def _prefix(values: np.ndarray) -> np.ndarray:
    out = np.zeros(values.size + 1, dtype="float64")
    np.cumsum(values, out=out[1:])
    return out


def rolling_by_key(
    frame: pd.DataFrame,
    key: str,
    window: str,
    value_column: str,
    aggregation: Aggregation,
) -> pd.Series:
    """Point-in-time aggregation. closed='left' excludes the current row from its own window."""
    bounds = window_bounds(frame, key, window)
    values = pd.to_numeric(frame[value_column], errors="coerce").to_numpy("float64")[bounds.order]
    present = np.isfinite(values)
    filled = np.where(present, values, 0.0)

    counts = _prefix(present.astype("float64"))
    counts = counts[bounds.hi] - counts[bounds.lo]

    if aggregation == "count":
        result = counts
    else:
        sums = _prefix(filled)
        sums = sums[bounds.hi] - sums[bounds.lo]
        if aggregation == "sum":
            result = sums
        elif aggregation == "mean":
            with np.errstate(invalid="ignore", divide="ignore"):
                result = np.where(counts > 0, sums / counts, np.nan)
        else:
            squares = _prefix(filled * filled)
            squares = squares[bounds.hi] - squares[bounds.lo]
            with np.errstate(invalid="ignore", divide="ignore"):
                variance = (squares - (sums * sums) / np.where(counts > 0, counts, 1.0)) / np.where(
                    counts > 1, counts - 1, np.nan
                )
            result = np.sqrt(np.clip(variance, 0.0, None))

    return pd.Series(
        bounds.restore(result), index=frame.index, name=f"{aggregation}_{key}_{window}"
    )


def rolling_category_counts(
    frame: pd.DataFrame, key: str, window: str, category_codes: np.ndarray, n_categories: int
) -> np.ndarray:
    """Per-row counts of each category value inside [t - window, t).

    Returns an (n_rows, n_categories) array."""
    bounds = window_bounds(frame, key, window)
    sorted_codes = category_codes[bounds.order]
    out = np.zeros((frame.shape[0], n_categories), dtype="float64")
    for category in range(n_categories):
        prefix = _prefix((sorted_codes == category).astype("float64"))
        out[:, category] = bounds.restore(prefix[bounds.hi] - prefix[bounds.lo])
    return out


def rolling_distinct(frame: pd.DataFrame, key: str, pair_key: str, window: str) -> pd.Series:
    """Approximate distinct count of pair_key values per key inside the window.

    A row counts as a new value when the previous event sharing the same (key, pair_key)
    is older than the window. This is the batch counterpart of the HyperLogLog counter the
    hot path reads, and carries error of the same order.
    """
    span = pd.Timedelta(window)
    pair = (
        frame[key].astype("object").fillna(MISSING_KEY_SENTINEL).astype(str)
        + "|"
        + frame[pair_key].astype("object").fillna(MISSING_KEY_SENTINEL).astype(str)
    )
    working = pd.DataFrame(
        {"event_ts": pd.to_datetime(frame["event_ts"], utc=True), "pair": pair, key: frame[key]},
        index=frame.index,
    )
    ordered = working.sort_values("event_ts", kind="mergesort")
    gap = ordered.groupby("pair", sort=False)["event_ts"].diff()
    is_new = (gap.isna() | (gap >= span)).astype("float64")
    working["is_new"] = is_new.reindex(working.index)
    return rolling_by_key(working, key, window, "is_new", "sum")
