"""Layer 1: per-column two-sample KS, plus Benford first-digit conformity on amount."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp

from runtime.config import PayLoopConfig

FIDELITY_KS_MAX: float = 0.10
FIDELITY_KS_COLUMN_PASS_FRAC: float = 0.90
KS_MIN_P_VALUE: float = 0.05
# The two-sample KS critical value at alpha 0.05 is about 1.36 * sqrt(2/n). At n = 500 that
# lands near 0.086, just inside the declared 0.10 effect size, so the statistic and the
# p-value agree. At tens of thousands of rows the test rejects a 0.02 difference and the
# threshold in the specification would mean nothing.
KS_SAMPLE_ROWS: int = 500
KS_REPEATS: int = 9

# Benford critical value at 8 degrees of freedom and alpha 0.05.
BENFORD_CHI2_MAX: float = 15.507
BENFORD_MAD_MAX: float = 0.006
# The chi-square statistic scales linearly with n, so at millions of rows it rejects any
# distribution that is not exactly Benford. Nigrini's own guidance is to read MAD at scale;
# the statistic is therefore computed on a fixed-size sample and MAD on the whole frame.
BENFORD_CHI2_SAMPLE_ROWS: int = 5_000
BENFORD_EXPECTED: np.ndarray = np.log10(1.0 + 1.0 / np.arange(1, 10))

NUMERIC_SOURCE_COLUMNS: tuple[str, ...] = ("amount", "amount_inr", "browser_tz_offset")
MIN_LEGITIMATE_ROWS: int = 200


def legitimate_view(frame: pd.DataFrame) -> pd.DataFrame:
    """The rows a distribution-level comparison against a legitimate reference can speak to.

    A campaign is meant to depart from the legitimate amount and code distributions; that
    departure is the detection signal, not a fidelity defect. Layers 1 and 2 therefore read
    the legitimate portion of a batch, and layers 3 to 6 read all of it."""
    if "is_fraud" not in frame.columns:
        return frame
    legitimate = frame[~frame["is_fraud"].astype(bool)]
    return legitimate if len(legitimate) >= MIN_LEGITIMATE_ROWS else frame


@dataclass(frozen=True)
class LayerResult:
    name: str
    passed: bool
    metrics: dict[str, float]
    detail: str


def numeric_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """The shared numeric view every distribution-level fidelity layer reads."""
    if frame.empty:
        return pd.DataFrame()
    event_ts = pd.to_datetime(frame["event_ts"], utc=True)
    amount = pd.to_numeric(frame["amount"], errors="coerce")
    columns = {
        "amount": amount,
        "log_amount": np.log10(amount.clip(lower=0.01)),
        "hour_of_day": event_ts.dt.hour.astype("float64"),
        "day_of_week": event_ts.dt.dayofweek.astype("float64"),
        "cross_border_num": frame["cross_border"].astype("float64"),
        "is_decline": (
            frame.get("response_code", pd.Series(index=frame.index)).fillna("00") != "00"
        ).astype("float64"),
    }
    for column in NUMERIC_SOURCE_COLUMNS:
        if column in frame.columns:
            columns[column] = pd.to_numeric(frame[column], errors="coerce")
    return pd.DataFrame(columns).replace([np.inf, -np.inf], np.nan)


def _sample(values: np.ndarray, limit: int, rng: np.random.Generator) -> np.ndarray:
    values = values[np.isfinite(values)]
    if values.size <= limit:
        return values
    return rng.choice(values, size=limit, replace=False)


def first_digits(amount: np.ndarray) -> np.ndarray:
    positive = amount[np.isfinite(amount) & (amount > 0)]
    if positive.size == 0:
        return np.empty(0, dtype="int64")
    leading = positive / np.power(10.0, np.floor(np.log10(positive)))
    return np.clip(np.floor(leading).astype("int64"), 1, 9)


def benford_statistics(amount: np.ndarray, rng: np.random.Generator) -> tuple[float, float]:
    digits = first_digits(amount)
    if digits.size == 0:
        return float("inf"), float("inf")
    observed = np.array([(digits == value).mean() for value in range(1, 10)])
    mad = float(np.abs(observed - BENFORD_EXPECTED).mean())

    sample = (
        digits
        if digits.size <= BENFORD_CHI2_SAMPLE_ROWS
        else rng.choice(digits, size=BENFORD_CHI2_SAMPLE_ROWS, replace=False)
    )
    counts = np.array([(sample == value).sum() for value in range(1, 10)], dtype="float64")
    expected = BENFORD_EXPECTED * sample.size
    chi2 = float(((counts - expected) ** 2 / expected).sum())
    return chi2, mad


def evaluate(batch: pd.DataFrame, reference: pd.DataFrame, config: PayLoopConfig) -> LayerResult:
    from runtime.seeding import rng_for

    rng = rng_for("fidelity:marginal")
    batch = legitimate_view(batch)
    batch_numeric, reference_numeric = numeric_frame(batch), numeric_frame(reference)
    shared = [c for c in batch_numeric.columns if c in reference_numeric.columns]

    passing = 0
    worst_statistic = 0.0
    for column in shared:
        # Repeated draws so a single unlucky sample cannot decide a column.
        statistics, p_values = [], []
        for _ in range(KS_REPEATS):
            left = _sample(batch_numeric[column].to_numpy("float64"), KS_SAMPLE_ROWS, rng)
            right = _sample(reference_numeric[column].to_numpy("float64"), KS_SAMPLE_ROWS, rng)
            if left.size < 2 or right.size < 2:
                continue
            statistic, p_value = ks_2samp(left, right)
            statistics.append(float(statistic))
            p_values.append(float(p_value))
        if not statistics:
            continue
        statistic = float(np.median(statistics))
        p_value = float(np.median(p_values))
        worst_statistic = max(worst_statistic, statistic)
        if statistic < config.fidelity_ks_max and p_value > KS_MIN_P_VALUE:
            passing += 1
    column_pass_frac = passing / len(shared) if shared else 0.0

    chi2, mad = benford_statistics(
        pd.to_numeric(batch["amount"], errors="coerce").to_numpy("float64"), rng
    )
    ks_ok = column_pass_frac >= FIDELITY_KS_COLUMN_PASS_FRAC
    benford_ok = chi2 < BENFORD_CHI2_MAX and mad <= BENFORD_MAD_MAX
    return LayerResult(
        name="marginal",
        passed=bool(ks_ok and benford_ok),
        metrics={
            "ks_column_pass_frac": round(column_pass_frac, 4),
            "ks_worst_statistic": round(worst_statistic, 4),
            "benford_chi2": round(chi2, 4),
            "benford_mad": round(mad, 6),
        },
        detail=(
            f"{passing}/{len(shared)} columns within KS {config.fidelity_ks_max}; "
            f"benford chi2 {chi2:.2f} mad {mad:.4f}"
        ),
    )
