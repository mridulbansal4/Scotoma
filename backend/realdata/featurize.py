"""The 73 features of the 151 that Sparkov can actually support.

The other 78 are not zero, they are absent, and the difference matters. A zero in
device_age_hours is a claim that the device is new; NaN is the truth that Sparkov has no
device column at all. LightGBM splits on missing natively, so absent features cost the fit
nothing and stop the model learning a constant.

Velocity reuses rolling_by_key so the closed="left" semantics come from the same tested
code path the synthetic pipeline uses. That exclusion of the current row is the whole
ballgame: include it and every count leaks its own label.
"""

import numpy as np
import pandas as pd

from backend.defend.features import (
    VELOCITY_AGGREGATIONS,
    VELOCITY_KEYS,
    VELOCITY_WINDOWS,
)
from backend.defend.windows import rolling_by_key

# Sparkov carries a card key and a merchant key. It has no device, no IP, no agent.
SUPPORTED_KEYS: tuple[str, ...] = ("pan_token", "merchant_id", "payee_entity_id")
ABSENT_KEYS: tuple[str, ...] = tuple(key for key in VELOCITY_KEYS if key not in SUPPORTED_KEYS)

EARTH_RADIUS_KM: float = 6371.0
MIN_TRAVEL_HOURS: float = 1.0 / 60.0

DERIVED_FEATURES: tuple[str, ...] = (
    "impossible_travel_kmh",
    "first_time_payee",
    "payee_age_hours",
    "mcc_novelty_for_entity",
    "circadian_loglik",
    "amount_z_vs_entity_history",
    "merchant_benford_dev_24h",
    "fanin_payee_24h",
    "fanout_payer_24h",
)


def supported_velocity_names() -> tuple[str, ...]:
    return tuple(
        f"{agg}_{key}_{window}"
        for key in SUPPORTED_KEYS
        for window in VELOCITY_WINDOWS
        for agg in VELOCITY_AGGREGATIONS
    )


def absent_velocity_names() -> tuple[str, ...]:
    return tuple(
        f"{agg}_{key}_{window}"
        for key in ABSENT_KEYS
        for window in VELOCITY_WINDOWS
        for agg in VELOCITY_AGGREGATIONS
    )


SHARED_FEATURE_NAMES: tuple[str, ...] = supported_velocity_names() + DERIVED_FEATURES


def _velocity(frame: pd.DataFrame) -> dict[str, np.ndarray]:
    columns: dict[str, np.ndarray] = {}
    for key in SUPPORTED_KEYS:
        for window in VELOCITY_WINDOWS:
            columns[f"cnt_{key}_{window}"] = rolling_by_key(
                frame, key, window, "amount", "count"
            ).to_numpy()
            columns[f"sum_{key}_{window}"] = rolling_by_key(
                frame, key, window, "amount", "sum"
            ).to_numpy()
            columns[f"amtstd_{key}_{window}"] = rolling_by_key(
                frame, key, window, "amount", "std"
            ).to_numpy()
            # Sparkov records no authorisation outcome, so a decline rate cannot be
            # computed. NaN rather than 0.0: a constant zero would look like a signal.
            columns[f"declrate_{key}_{window}"] = np.full(len(frame), np.nan, dtype="float32")
    return columns


def _haversine_kmh(frame: pd.DataFrame) -> np.ndarray:
    """Speed implied between a card's consecutive transaction locations."""
    lat = np.radians(pd.to_numeric(frame["payer_lat"], errors="coerce").to_numpy("float64"))
    lon = np.radians(pd.to_numeric(frame["payer_lon"], errors="coerce").to_numpy("float64"))
    stamps = pd.to_datetime(frame["event_ts"], utc=True).to_numpy("datetime64[ns]").astype("int64")
    speeds = np.zeros(len(frame), dtype="float64")

    for _, positions in frame.groupby("pan_token", sort=False).indices.items():
        if len(positions) < 2:
            continue
        order = positions[np.argsort(stamps[positions])]
        prev, cur = order[:-1], order[1:]
        dlat = lat[cur] - lat[prev]
        dlon = lon[cur] - lon[prev]
        haversine = (
            np.sin(dlat / 2) ** 2 + np.cos(lat[prev]) * np.cos(lat[cur]) * np.sin(dlon / 2) ** 2
        )
        km = 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(haversine, 0.0, 1.0)))
        hours = (stamps[cur] - stamps[prev]) / 3.6e12
        speeds[cur] = km / np.maximum(hours, MIN_TRAVEL_HOURS)
    return speeds


def _first_seen(frame: pd.DataFrame, left: str, right: str) -> tuple[np.ndarray, np.ndarray]:
    """First-time flag and hours since first sighting, per (left, right) pair."""
    stamps = pd.to_datetime(frame["event_ts"], utc=True).to_numpy("datetime64[ns]").astype("int64")
    pair = frame[left].astype("string") + "|" + frame[right].astype("string")
    order = np.argsort(stamps, kind="stable")
    codes = pd.factorize(pair)[0][order]
    first_at = np.full(codes.max() + 1 if len(codes) else 0, -1, dtype="int64")
    is_first = np.zeros(len(frame), dtype="float32")
    age_hours = np.zeros(len(frame), dtype="float64")
    for position, code in zip(order, codes):
        if first_at[code] < 0:
            first_at[code] = stamps[position]
            is_first[position] = 1.0
        else:
            age_hours[position] = (stamps[position] - first_at[code]) / 3.6e12
    return is_first, age_hours


def _expanding_novelty(frame: pd.DataFrame, key: str, value: str) -> np.ndarray:
    """1.0 when this key has never been seen with this value before, strictly prior."""
    stamps = pd.to_datetime(frame["event_ts"], utc=True).to_numpy("datetime64[ns]").astype("int64")
    order = np.argsort(stamps, kind="stable")
    keys = frame[key].astype("string").to_numpy()
    values = frame[value].astype("string").to_numpy()
    seen: dict[str, set] = {}
    novelty = np.zeros(len(frame), dtype="float32")
    for position in order:
        bucket = seen.setdefault(keys[position], set())
        if values[position] not in bucket:
            novelty[position] = 1.0
            bucket.add(values[position])
    return novelty


def _expanding_amount_z(frame: pd.DataFrame) -> np.ndarray:
    """Amount z-score against the card's own prior history. Prior only, never the row."""
    stamps = pd.to_datetime(frame["event_ts"], utc=True).to_numpy("datetime64[ns]").astype("int64")
    amount = pd.to_numeric(frame["amount"], errors="coerce").to_numpy("float64")
    order = np.argsort(stamps, kind="stable")
    codes = pd.factorize(frame["pan_token"])[0]
    n = codes.max() + 1 if len(codes) else 0
    count = np.zeros(n, dtype="float64")
    total = np.zeros(n, dtype="float64")
    total_sq = np.zeros(n, dtype="float64")
    z = np.zeros(len(frame), dtype="float64")
    for position in order:
        code = codes[position]
        if count[code] >= 2:
            mean = total[code] / count[code]
            variance = max(total_sq[code] / count[code] - mean * mean, 0.0)
            std = np.sqrt(variance)
            z[position] = (amount[position] - mean) / std if std > 1e-9 else 0.0
        count[code] += 1.0
        total[code] += amount[position]
        total_sq[code] += amount[position] * amount[position]
    return z


def _circadian_loglik(frame: pd.DataFrame) -> np.ndarray:
    """Log-likelihood of this hour under the card's own prior hour-of-day distribution.

    A von Mises would be tighter, but a 24-bin expanding histogram needs no fitting and
    Sparkov gives 24 months per card, which is plenty of mass.
    """
    stamps = pd.to_datetime(frame["event_ts"], utc=True)
    hours = stamps.dt.hour.to_numpy("int64")
    order = np.argsort(stamps.to_numpy("datetime64[ns]").astype("int64"), kind="stable")
    codes = pd.factorize(frame["pan_token"])[0]
    n = codes.max() + 1 if len(codes) else 0
    histogram = np.ones((n, 24), dtype="float64")  # Laplace prior, so log is always finite
    loglik = np.zeros(len(frame), dtype="float64")
    for position in order:
        code = codes[position]
        row = histogram[code]
        loglik[position] = float(np.log(row[hours[position]] / row.sum()))
        row[hours[position]] += 1.0
    return loglik


def _benford_deviation(frame: pd.DataFrame) -> np.ndarray:
    """Per-merchant deviation of leading-digit mix from Benford, over prior 24h."""
    amount = pd.to_numeric(frame["amount"], errors="coerce").to_numpy("float64")
    leading = np.where(amount > 0, np.floor(amount / (10 ** np.floor(np.log10(np.maximum(amount, 1e-9))))), 0)
    working = frame.copy()
    expected = np.log10(1.0 + 1.0 / np.arange(1, 10))
    deviation = np.zeros(len(frame), dtype="float64")
    for digit in range(1, 10):
        working["_is_digit"] = (leading == digit).astype("float64")
        share = rolling_by_key(working, "merchant_id", "24h", "_is_digit", "mean").to_numpy()
        deviation += np.abs(np.nan_to_num(share) - expected[digit - 1])
    return deviation


def build_features(frame: pd.DataFrame, include_absent: bool = True) -> pd.DataFrame:
    """Feature matrix for a Sparkov partition.

    include_absent adds the 78 unavailable features as all-NaN columns so the matrix is
    column-compatible with the synthetic detector. Set it False to train a real-data-only
    model on the 73 that exist.
    """
    working = frame.sort_values("event_ts").reset_index(drop=True)
    columns: dict[str, np.ndarray] = dict(_velocity(working))

    columns["impossible_travel_kmh"] = _haversine_kmh(working)
    first_time, age = _first_seen(working, "pan_token", "payee_entity_id")
    columns["first_time_payee"] = first_time
    columns["payee_age_hours"] = age
    columns["mcc_novelty_for_entity"] = _expanding_novelty(working, "pan_token", "mcc")
    columns["circadian_loglik"] = _circadian_loglik(working)
    columns["amount_z_vs_entity_history"] = _expanding_amount_z(working)
    columns["merchant_benford_dev_24h"] = _benford_deviation(working)
    columns["fanin_payee_24h"] = rolling_by_key(
        working, "payee_entity_id", "24h", "amount", "count"
    ).to_numpy()
    columns["fanout_payer_24h"] = rolling_by_key(
        working, "pan_token", "24h", "amount", "count"
    ).to_numpy()

    matrix = pd.DataFrame(columns, index=working.index).astype("float32")
    if include_absent:
        for name in absent_velocity_names():
            matrix[name] = np.nan
    return matrix
