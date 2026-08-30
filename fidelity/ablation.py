"""The GaussianCopula ablation: PayLoop's own baseline pushed through PayLoop's own gate.

The expected result is that the utility layer passes and the behavioural layer fails. If
the ablation clears the gate, the behavioural threshold is too loose and gets tightened
before the demo; skipping the ablation is not an option.
"""

import numpy as np
import pandas as pd

from fidelity.gate import GateResult, run_gate
from runtime.config import PayLoopConfig, load_config
from runtime.seeding import rng_for, seeded_uuid

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
            fit_frame[column] = (
                fit_frame[column].astype("object").fillna(MISSING_TOKEN).astype(str)
            )

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
        "fit_rows": min(ABLATION_FIT_ROWS, len(fit_source)),
        "sample_rows": len(batch),
        "behavioral_max": config.fidelity_behavioral_max,
        "tstr_min_ratio": config.fidelity_tstr_min_ratio,
        **result.as_payload(),
    }
    return result, payload
