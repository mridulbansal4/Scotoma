"""The GaussianCopula ablation: PayLoop's own baseline pushed through PayLoop's own gate.

The expected result is that the utility layer passes and the behavioural layer fails. If
the ablation clears the gate, the behavioural threshold is too loose and gets tightened
before the demo; skipping the ablation is not an option.
"""

import numpy as np
import pandas as pd

from backend.fidelity.gate import GateResult, run_gate
from backend.runtime.config import PayLoopConfig, load_config
from backend.runtime.seeding import rng_for, seeded_uuid

ABLATION_FIT_ROWS: int = 50_000
ABLATION_SAMPLE_ROWS: int = 50_000
ABLATION_ROUND_INDEX: int = 0
ABLATION_GENERATOR: str = "GaussianCopulaSynthesizer"

# Columns the copula is fitted on. Entity ids are carried through unchanged so the batch
# still has aggregation keys; the point of the ablation is that a row-independent model
# cannot reproduce the sequence structure attached to those keys.
ABLATION_COLUMNS: tuple[str, ...] = (
    "amount",
    "amount_inr",
    "rail",
    "currency",
    "mcc",
    "response_code",
    "pos_entry_mode",
    "threeds_flow",
    "cross_border",
    "payer_country",
    "payee_country",
)
MISSING_TOKEN: str = "__missing__"
MARGINAL_SHARE_COLUMNS: tuple[str, ...] = ("rail", "response_code", "currency", "mcc")


def _fit_sample(reference: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    size = min(ABLATION_FIT_ROWS, len(reference))
    positions = rng.choice(len(reference), size=size, replace=False)
    return reference.iloc[positions].reset_index(drop=True)


def synthesize(reference: pd.DataFrame) -> pd.DataFrame:
    """Fit a Gaussian copula on the reference columns and sample rows independently.

    Row independence is the defining property of the baseline: every field of every row is
    drawn without reference to any other row, so no entity has a history. The carried
    identifier and timestamp columns are therefore resampled column by column rather than
    row by row, which is what a row-independent generator actually produces."""
    from sdv.metadata import SingleTableMetadata
    from sdv.single_table import GaussianCopulaSynthesizer

    rng = rng_for("fidelity:ablation")
    training = _fit_sample(reference, rng)
    available = [column for column in ABLATION_COLUMNS if column in training.columns]
    fit_frame = training[available].copy()
    for column in available:
        if fit_frame[column].dtype == object:
            fit_frame[column] = fit_frame[column].astype("object").fillna(MISSING_TOKEN).astype(str)

    metadata = SingleTableMetadata()
    metadata.detect_from_dataframe(fit_frame)
    synthesizer = GaussianCopulaSynthesizer(metadata)
    synthesizer.fit(fit_frame)
    rows = min(ABLATION_SAMPLE_ROWS, len(reference))
    sampled = synthesizer.sample(num_rows=rows)

    batch = pd.DataFrame(index=range(rows))
    for column in reference.columns:
        if column in available:
            batch[column] = sampled[column].to_numpy()
        else:
            source = reference[column].to_numpy()
            batch[column] = source[rng.integers(0, source.size, size=rows)]
    batch["event_id"] = [str(seeded_uuid("fidelity:ablation", index)) for index in range(rows)]
    batch["event_ts"] = pd.to_datetime(batch["event_ts"], utc=True)
    batch["is_fraud"] = False
    return batch.reset_index(drop=True)


def marginal_shares(batch: pd.DataFrame, reference: pd.DataFrame) -> dict:
    """How closely the baseline reproduces each column on its own.

    This is the other half of the argument. A row-independent generator can match every
    column marginal to within a fraction of a point and still carry none of the structure
    that links them, so the per-column agreement is reported next to the layers it fails."""
    shares: dict[str, dict] = {}
    for column in MARGINAL_SHARE_COLUMNS:
        if column not in batch.columns or column not in reference.columns:
            continue
        left = batch[column].astype("object").fillna(MISSING_TOKEN).value_counts(normalize=True)
        right = (
            reference[column].astype("object").fillna(MISSING_TOKEN).value_counts(normalize=True)
        )
        aligned = left.reindex(right.index).fillna(0.0)
        shares[column] = {
            "max_abs_difference": round(float((aligned - right).abs().max()), 4),
            "batch_top": {str(k): round(float(v), 4) for k, v in left.head(4).items()},
            "reference_top": {str(k): round(float(v), 4) for k, v in right.head(4).items()},
        }
    shares["decline_rate_by_rail"] = {
        "batch": _decline_by_rail(batch),
        "reference": _decline_by_rail(reference),
    }
    return shares


def _decline_by_rail(frame: pd.DataFrame) -> dict[str, float]:
    # An external reference corpus may carry neither column. Absent is not zero, so the
    # answer is an empty mapping rather than a fabricated all-approved rail.
    if "rail" not in frame.columns or "response_code" not in frame.columns:
        return {}
    declined = frame["response_code"].astype("object").fillna("00").ne("00")
    return {
        str(rail): round(float(value), 4)
        for rail, value in declined.groupby(frame["rail"]).mean().items()
    }


def run_ablation(
    fit_source: pd.DataFrame, reference: pd.DataFrame, config: PayLoopConfig | None = None
) -> tuple[GateResult, dict]:
    """The copula is fitted on one legitimate partition and gated against a disjoint one,
    exactly as a round's campaign batch is."""
    config = config or load_config()
    batch = synthesize(fit_source)
    result = run_gate(batch, reference, ABLATION_ROUND_INDEX, config)
    payload = {
        "generator": ABLATION_GENERATOR,
        "marginal_shares": marginal_shares(batch, reference),
        "fit_rows": min(ABLATION_FIT_ROWS, len(fit_source)),
        "sample_rows": len(batch),
        "behavioral_max": config.fidelity_behavioral_max,
        "tstr_min_ratio": config.fidelity_tstr_min_ratio,
        **result.as_payload(),
    }
    return result, payload
