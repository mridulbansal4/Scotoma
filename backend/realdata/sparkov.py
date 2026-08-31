"""Sparkov (kartik2112/fraud-detection) into the CES column names the detector expects.

Sparkov is card-not-present retail traffic with a card key, a merchant key, both geo
endpoints and a real timestamp. It carries no device, no IP and no agent, so three of the
six velocity key families are unavailable rather than empty. That distinction is enforced
in featurize, not here.

The file ships pre-split as fraudTrain.csv / fraudTest.csv and that split is temporal.
partition() preserves it: the train file becomes calib + floor, the test file becomes
blind in its entirety, so the holdout is genuinely later in time than everything else.
"""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from backend.runtime.errors import RegistryInvalid

CALIB = "calib"
FLOOR = "floor"
BLIND = "blind"
PARTITIONS: tuple[str, ...] = (CALIB, FLOOR, BLIND)

# Sparkov's own header. A missing column here means the download is not Sparkov.
REQUIRED_COLUMNS: tuple[str, ...] = (
    "trans_date_trans_time",
    "cc_num",
    "merchant",
    "category",
    "amt",
    "lat",
    "long",
    "merch_lat",
    "merch_long",
    "city_pop",
    "trans_num",
    "is_fraud",
)

# Sparkov's ~14 retail categories mapped onto MCC ranges. The CES adapter needs an MCC,
# and category is the only usable analogue in this corpus.
CATEGORY_TO_MCC: dict[str, int] = {
    "entertainment": 7996,
    "food_dining": 5812,
    "gas_transport": 5541,
    "grocery_net": 5411,
    "grocery_pos": 5411,
    "health_fitness": 8099,
    "home": 5200,
    "kids_pets": 5995,
    "misc_net": 5399,
    "misc_pos": 5399,
    "personal_care": 7230,
    "shopping_net": 5651,
    "shopping_pos": 5651,
    "travel": 4722,
}
UNKNOWN_MCC = 5999


@dataclass(frozen=True)
class PartitionReport:
    """What partition() wrote, for the assertion and the model card."""

    rows: dict[str, int]
    frauds: dict[str, int]
    boundaries: dict[str, tuple[str, str]]

    def prevalence(self, name: str) -> float:
        total = self.rows.get(name, 0)
        return float(self.frauds.get(name, 0)) / total if total else 0.0

    def as_payload(self) -> dict:
        return {
            "rows": dict(self.rows),
            "frauds": dict(self.frauds),
            "prevalence": {name: round(self.prevalence(name), 6) for name in self.rows},
            "boundaries": {name: list(span) for name, span in self.boundaries.items()},
        }


def read_sparkov(path: Path) -> pd.DataFrame:
    """Load one Sparkov CSV and rename it into CES columns."""
    frame = pd.read_csv(path, low_memory=False)
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise RegistryInvalid(f"{path.name} is not Sparkov; missing columns: {missing}")
    return to_ces(frame)


def to_ces(frame: pd.DataFrame) -> pd.DataFrame:
    """Sparkov columns to the internal event schema.

    merchant fills both merchant_id and payee_entity_id: in a card-present-style retail
    corpus the acceptor and the payee are the same party. Documenting the substitution is
    the point, not hiding it.
    """
    out = pd.DataFrame(index=frame.index)
    out["event_ts"] = pd.to_datetime(frame["trans_date_trans_time"], utc=True)
    out["event_id"] = frame["trans_num"].astype("string")
    out["pan_token"] = frame["cc_num"].astype("string")
    out["merchant_id"] = frame["merchant"].astype("string")
    out["payee_entity_id"] = frame["merchant"].astype("string")
    out["payer_entity_id"] = frame["cc_num"].astype("string")
    out["amount"] = pd.to_numeric(frame["amt"], errors="coerce").astype("float64")
    out["mcc"] = (
        frame["category"].astype("string").map(CATEGORY_TO_MCC).fillna(UNKNOWN_MCC).astype("int32")
    )
    out["payer_lat"] = pd.to_numeric(frame["lat"], errors="coerce")
    out["payer_lon"] = pd.to_numeric(frame["long"], errors="coerce")
    out["payee_lat"] = pd.to_numeric(frame["merch_lat"], errors="coerce")
    out["payee_lon"] = pd.to_numeric(frame["merch_long"], errors="coerce")
    out["city_pop"] = pd.to_numeric(frame["city_pop"], errors="coerce")
    # Sparkov records no authorisation outcome. declrate would otherwise read as a
    # constant zero and look like a real signal; it is absent, and featurize marks it so.
    out["response_code"] = pd.NA
    # Sparkov is retail card-not-present throughout, so the rail is a constant and saying
    # so is accurate. The joint layer reads it as a categorical.
    out["rail"] = "CARD_CNP"
    out["is_fraud"] = pd.to_numeric(frame["is_fraud"], errors="coerce").fillna(0).astype("int8")
    return out.sort_values("event_ts").reset_index(drop=True)


def partition(
    train_csv: Path,
    test_csv: Path,
    out_dir: Path,
    calib_fraction: float = 0.60,
) -> PartitionReport:
    """Split by time, once, into calib / floor / blind and write parquet.

    calib is what the generator is allowed to see. floor is the fidelity gate reference
    and the generator never sees it. blind is TSTR and nothing touches it until final
    scoring. If calibration and the gate reference overlap, the gate passes trivially.
    """
    if not 0.0 < calib_fraction < 1.0:
        raise ValueError(f"calib_fraction must be in (0, 1), got {calib_fraction}")

    train = read_sparkov(train_csv)
    blind = read_sparkov(test_csv)

    cut = int(len(train) * calib_fraction)
    if cut == 0 or cut == len(train):
        raise ValueError("calib_fraction leaves one side of the split empty")
    # The frame is already sorted by event_ts, so a positional cut is a temporal cut.
    calib = train.iloc[:cut].reset_index(drop=True)
    floor = train.iloc[cut:].reset_index(drop=True)

    out_dir.mkdir(parents=True, exist_ok=True)
    frames = {CALIB: calib, FLOOR: floor, BLIND: blind}
    for name, part in frames.items():
        part.to_parquet(out_dir / f"{name}.parquet", index=False)

    assert_disjoint(frames)
    return PartitionReport(
        rows={name: len(part) for name, part in frames.items()},
        frauds={name: int(part["is_fraud"].sum()) for name, part in frames.items()},
        boundaries={
            name: (str(part["event_ts"].min()), str(part["event_ts"].max()))
            for name, part in frames.items()
        },
    )


def assert_disjoint(frames: dict[str, pd.DataFrame]) -> None:
    """No event may appear in two partitions. This is the assertion A.4 asks for."""
    seen: dict[str, str] = {}
    for name, part in frames.items():
        ids = part["event_id"].astype("string")
        duplicated_within = ids.duplicated().sum()
        if duplicated_within:
            raise RegistryInvalid(f"{name} contains {duplicated_within} duplicate event ids")
        for event_id in ids:
            other = seen.get(event_id)
            if other is not None:
                raise RegistryInvalid(f"event {event_id} appears in both {other} and {name}")
            seen[event_id] = name


def load_partition(out_dir: Path, name: str) -> pd.DataFrame:
    if name not in PARTITIONS:
        raise ValueError(f"unknown partition {name!r}; expected one of {PARTITIONS}")
    target = out_dir / f"{name}.parquet"
    if not target.exists():
        raise FileNotFoundError(f"{target} is missing; run the prepare step first")
    return pd.read_parquet(target)
