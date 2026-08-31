"""ULB and IBM AML: the two corpora used for evidence rather than for training.

ULB settles the Platt-versus-isotonic ruling on observed data. IBM AML measures whether
account-graph structure clears the Channel B lift bar. Neither trains a shipped model, so
what these tests guard is that the measurements stay honest.
"""

import numpy as np
import pandas as pd
import pytest

from backend.realdata import aml, ulb
from backend.runtime.config import PayLoopConfig
from backend.runtime.errors import RegistryInvalid


def _ulb_frame(rows: int = 4000) -> pd.DataFrame:
    rng = np.random.default_rng(11)
    features = {f"V{i}": rng.normal(0, 1, rows) for i in range(1, 29)}
    label = (rng.random(rows) < 0.02).astype(int)
    # A separable signal, so the calibrators have something real to disagree about.
    features["V1"] = features["V1"] + label * 2.5
    return pd.DataFrame(
        {
            "Time": np.sort(rng.integers(0, 172800, rows)).astype(float),
            **features,
            "Amount": rng.lognormal(3, 1, rows),
            "Class": label,
        }
    )


def _aml_frame(rows: int = 3000) -> pd.DataFrame:
    rng = np.random.default_rng(13)
    accounts = [f"800{i:05X}" for i in range(300)]
    stamps = pd.to_datetime("2022-09-01") + pd.to_timedelta(
        np.sort(rng.integers(0, 86400 * 20, rows)), unit="s"
    )
    return pd.DataFrame(
        {
            "Timestamp": stamps.strftime("%Y/%m/%d %H:%M"),
            "From Bank": rng.integers(1, 50, rows),
            "Account": rng.choice(accounts, rows),
            "To Bank": rng.integers(1, 50, rows),
            "Account.1": rng.choice(accounts, rows),
            "Amount Received": rng.lognormal(6, 1.5, rows).round(2),
            "Receiving Currency": rng.choice(["US Dollar", "Euro"], rows),
            "Amount Paid": rng.lognormal(6, 1.5, rows).round(2),
            "Payment Currency": rng.choice(["US Dollar", "Euro", "Bitcoin"], rows),
            "Payment Format": rng.choice(["Cheque", "Credit Card", "Reinvestment"], rows),
            "Is Laundering": (rng.random(rows) < 0.04).astype(int),
        }
    )


# --- ULB ----------------------------------------------------------------------------


def test_ulb_rejects_a_csv_that_is_not_ulb(tmp_path) -> None:
    path = tmp_path / "wrong.csv"
    pd.DataFrame({"a": [1]}).to_csv(path, index=False)
    with pytest.raises(RegistryInvalid, match="not ULB"):
        ulb.read_ulb(path)


def test_calibration_error_is_weighted_by_bin_mass() -> None:
    """An unweighted worst-bin figure is decided by bins holding one or two events, and
    it ranked the two calibrators backwards on the real corpus before this was fixed."""
    curve = [
        {"mean_predicted": 0.001, "observed_rate": 0.001, "count": 100_000},
        {"mean_predicted": 0.20, "observed_rate": 1.00, "count": 2},
    ]
    assert ulb._expected_calibration_error(curve) < 0.0001
    # The two-event bin is below the population floor, so it cannot set the worst bin.
    assert ulb._worst_populated_bin(curve) == pytest.approx(0.0, abs=1e-9)


def test_worst_populated_bin_is_nan_when_no_bin_qualifies() -> None:
    assert np.isnan(ulb._worst_populated_bin([{"mean_predicted": 0.5, "observed_rate": 0.1, "count": 3}]))


def test_saturated_fraction_counts_hard_zero_and_one() -> None:
    """Isotonic emits step-function certainty. Elkan cannot price a posterior of 1.0."""
    assert ulb._saturated_fraction(np.array([0.0, 0.5, 1.0, 0.2])) == pytest.approx(0.5)
    assert ulb._saturated_fraction(np.array([0.3, 0.5])) == 0.0


def test_ulb_comparison_reports_both_calibrators() -> None:
    payload = ulb.compare_calibrators(_ulb_frame(), PayLoopConfig())
    assert payload["is_observed_data"] is True
    for method in ("uncalibrated", "sigmoid", "isotonic"):
        assert method in payload["results"]
    assert "pr_auc_cost_of_isotonic" in payload


def test_ulb_split_is_temporal_not_random() -> None:
    frame = _ulb_frame()
    train_x, train_y, valid_x, valid_y, test_x, test_y = ulb._splits(frame)
    assert len(train_y) + len(valid_y) + len(test_y) == len(frame)
    # Time is sorted ascending, so the split boundaries must not interleave.
    times = frame["Time"].to_numpy()
    assert times[len(train_y) - 1] <= times[len(train_y)]


# --- IBM AML ------------------------------------------------------------------------


def test_aml_rejects_a_csv_that_is_not_aml(tmp_path) -> None:
    path = tmp_path / "wrong.csv"
    pd.DataFrame({"a": [1]}).to_csv(path, index=False)
    with pytest.raises(RegistryInvalid, match="not IBM AML"):
        aml.read_aml(path)


def test_currency_is_normalised_before_any_amount_feature() -> None:
    """Summing dollars and bitcoin into one total produces a number that means nothing."""
    frame = pd.DataFrame(
        {"Amount Paid": [100.0, 1.0], "Payment Currency": ["US Dollar", "Bitcoin"]}
    )
    normalised = aml.normalise_amount(frame)
    assert normalised[0] == pytest.approx(100.0)
    assert normalised[1] == pytest.approx(60000.0)


def test_unknown_currency_falls_back_rather_than_producing_nan() -> None:
    frame = pd.DataFrame({"Amount Paid": [50.0], "Payment Currency": ["Galactic Credit"]})
    assert aml.normalise_amount(frame)[0] == pytest.approx(50.0)


def test_motif_census_splits_by_label() -> None:
    census = aml.motif_census(_aml_frame())
    assert census["edges"] == 3000
    assert census["laundering"]["edges"] + census["legitimate"]["edges"] == 3000
    for label in ("laundering", "legitimate"):
        assert 0.0 <= census[label]["reciprocated_share"] <= 1.0


def test_graph_features_are_all_present_and_finite() -> None:
    matrix = aml.build_graph_features(_aml_frame())
    assert list(matrix.columns) == list(aml.GRAPH_FEATURES)
    assert np.isfinite(matrix.to_numpy("float64")).all()


def test_scoping_reports_lift_against_the_configured_bar() -> None:
    scoping = aml.scope_channel_b(_aml_frame(6000), min_lift=0.03)
    assert scoping["lift_bar"] == 0.03
    assert scoping["clears_lift_bar"] == (scoping["lift_over_base_rate"] >= 0.03)
    assert scoping["is_observed_data"] is False
