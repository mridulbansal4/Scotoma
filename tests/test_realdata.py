"""The partition discipline that makes the real-data fidelity floor mean anything.

If calibration rows reach the gate reference, the gate scores the generator against data
the generator was fitted on and passes trivially. These tests are the guard.
"""

import numpy as np
import pandas as pd
import pytest

from backend.realdata import sparkov
from backend.realdata.featurize import (
    ABSENT_KEYS,
    SHARED_FEATURE_NAMES,
    SUPPORTED_KEYS,
    absent_velocity_names,
    build_features,
)
from backend.runtime.errors import RegistryInvalid

SHARED_FEATURE_COUNT: int = 69
ABSENT_FEATURE_COUNT: int = 60


def _sparkov_frame(rows: int, offset: int, start: str) -> pd.DataFrame:
    rng = np.random.default_rng(7 + offset)
    stamps = pd.to_datetime(start) + pd.to_timedelta(
        np.sort(rng.integers(0, 3600 * 24 * 90, rows)), unit="s"
    )
    latitude = rng.uniform(25, 48, rows)
    longitude = rng.uniform(-124, -70, rows)
    return pd.DataFrame(
        {
            "trans_date_trans_time": stamps.strftime("%Y-%m-%d %H:%M:%S"),
            "cc_num": rng.choice([f"41{i:014d}" for i in range(20)], rows),
            "merchant": rng.choice([f"m_{i}" for i in range(8)], rows),
            "category": rng.choice(["grocery_pos", "travel", "misc_net"], rows),
            "amt": np.round(rng.lognormal(3.5, 1.0, rows), 2),
            "lat": latitude,
            "long": longitude,
            "merch_lat": latitude + rng.normal(0, 0.4, rows),
            "merch_long": longitude + rng.normal(0, 0.4, rows),
            "city_pop": rng.integers(500, 500000, rows),
            "trans_num": [f"{offset}{i:07d}" for i in range(rows)],
            "unix_time": stamps.astype("int64") // 10**9,
            "is_fraud": (rng.random(rows) < 0.02).astype(int),
        }
    )


@pytest.fixture
def partitions(tmp_path):
    train = tmp_path / "fraudTrain.csv"
    test = tmp_path / "fraudTest.csv"
    _sparkov_frame(600, 1, "2019-01-01").to_csv(train, index=False)
    _sparkov_frame(200, 2, "2020-06-01").to_csv(test, index=False)
    report = sparkov.partition(train, test, tmp_path / "real", calib_fraction=0.6)
    return tmp_path / "real", report


def test_partitions_do_not_share_events(partitions) -> None:
    out_dir, _ = partitions
    seen: dict[str, str] = {}
    for name in sparkov.PARTITIONS:
        for event_id in sparkov.load_partition(out_dir, name)["event_id"]:
            assert event_id not in seen, f"{event_id} in both {seen.get(event_id)} and {name}"
            seen[event_id] = name


def test_blind_is_strictly_later_than_calib_and_floor(partitions) -> None:
    """A holdout that overlaps training in time is not a holdout."""
    out_dir, _ = partitions
    blind_start = sparkov.load_partition(out_dir, sparkov.BLIND)["event_ts"].min()
    for name in (sparkov.CALIB, sparkov.FLOOR):
        assert sparkov.load_partition(out_dir, name)["event_ts"].max() < blind_start


def test_floor_follows_calib_in_time(partitions) -> None:
    out_dir, _ = partitions
    calib = sparkov.load_partition(out_dir, sparkov.CALIB)
    floor = sparkov.load_partition(out_dir, sparkov.FLOOR)
    assert calib["event_ts"].max() < floor["event_ts"].min()


def test_overlap_assertion_actually_fires() -> None:
    """The guard is worthless if it cannot fail."""
    frame = sparkov.to_ces(_sparkov_frame(50, 3, "2019-01-01"))
    with pytest.raises(RegistryInvalid, match="appears in both"):
        sparkov.assert_disjoint({sparkov.CALIB: frame, sparkov.FLOOR: frame})


def test_rejects_a_csv_that_is_not_sparkov(tmp_path) -> None:
    path = tmp_path / "wrong.csv"
    pd.DataFrame({"a": [1], "b": [2]}).to_csv(path, index=False)
    with pytest.raises(RegistryInvalid, match="not Sparkov"):
        sparkov.read_sparkov(path)


def test_absent_key_families_are_nan_not_zero(partitions) -> None:
    """A zero device count is a claim. Sparkov has no device column, so NaN is the truth."""
    out_dir, _ = partitions
    matrix = build_features(sparkov.load_partition(out_dir, sparkov.CALIB), include_absent=True)
    for name in absent_velocity_names():
        assert matrix[name].isna().all(), f"{name} should be absent, not zero-filled"


def test_decline_rate_is_absent_because_sparkov_has_no_response_code(partitions) -> None:
    out_dir, _ = partitions
    matrix = build_features(sparkov.load_partition(out_dir, sparkov.CALIB), include_absent=False)
    for key in SUPPORTED_KEYS:
        assert matrix[f"declrate_{key}_1h"].isna().all()


def test_feature_counts_match_the_documented_split(partitions) -> None:
    out_dir, _ = partitions
    matrix = build_features(sparkov.load_partition(out_dir, sparkov.CALIB), include_absent=True)
    assert len(SHARED_FEATURE_NAMES) == SHARED_FEATURE_COUNT
    assert len(absent_velocity_names()) == ABSENT_FEATURE_COUNT
    assert set(SHARED_FEATURE_NAMES) <= set(matrix.columns)
    assert len(ABSENT_KEYS) == 3


def test_velocity_excludes_the_current_row(partitions) -> None:
    """closed='left'. A card's first ever transaction has no prior history to count."""
    out_dir, _ = partitions
    frame = sparkov.load_partition(out_dir, sparkov.CALIB).sort_values("event_ts")
    matrix = build_features(frame, include_absent=False)
    first_rows = frame.reset_index(drop=True).groupby("pan_token", sort=False).head(1).index
    assert (matrix.loc[first_rows, "cnt_pan_token_7d"] == 0).all()


def test_floor_reference_returns_the_real_partition(tmp_path) -> None:
    """The caller must branch on `is not None`. `x or y` raises on a DataFrame, which is
    how the first wiring of this broke a full loop run at bootstrap."""
    from backend.loop import controller
    from backend.runtime.config import PayLoopConfig

    frame = sparkov.to_ces(_sparkov_frame(80, 9, "2019-01-01"))
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    frame.to_parquet(real_dir / "floor.parquet", index=False)

    config = PayLoopConfig(fidelity_floor_source="real", real_data_dir=str(real_dir))
    loaded = controller._real_floor_reference(config)
    assert loaded is not None
    assert len(loaded) == len(frame)
    assert {"event_ts", "amount", "is_fraud", "pan_token", "mcc"} <= set(loaded.columns)


def test_bootstrap_does_not_use_truthiness_on_the_floor_frame() -> None:
    """Guards the exact defect: `_real_floor_reference(config) or reference` raises."""
    import inspect

    from backend.loop import controller

    source = inspect.getsource(controller.bootstrap)
    assert "_real_floor_reference(config) or" not in source


def test_floor_reference_falls_back_when_real_data_is_absent(tmp_path) -> None:
    from backend.loop import controller
    from backend.runtime.config import PayLoopConfig

    config = PayLoopConfig(fidelity_floor_source="real", real_data_dir=str(tmp_path / "nope"))
    assert controller._real_floor_reference(config) is None


def test_floor_reference_is_off_by_default() -> None:
    from backend.loop import controller
    from backend.runtime.config import PayLoopConfig

    assert controller._real_floor_reference(PayLoopConfig()) is None
