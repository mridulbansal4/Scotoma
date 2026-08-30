"""The twelve realism assertions. All must pass before the pipeline proceeds."""

import numpy as np
import pandas as pd
import powerlaw
from scipy.stats import kurtosis

from backend.fidelity.behavioral import lag1_iet_autocorrelation
from backend.fidelity.marginal import BENFORD_CHI2_MAX, BENFORD_EXPECTED, benford_statistics, first_digits
from backend.generate.declines import mix_for
from backend.runtime.seeding import rng_for
from tests import fixture_world

NIGRINI_ACCEPTABLE_MAD: float = 0.012
NIGHT_HOURS: tuple[int, ...] = (2, 3, 4, 5)
NIGHT_TROUGH_FRACTION: float = 0.25
APPROVAL_BAND: tuple[float, float] = (0.88, 0.93)
CARD_PREVALENCE_BAND: tuple[float, float] = (0.0010, 0.0020)
UPI_PREVALENCE_BAND: tuple[float, float] = (0.0035, 0.0050)
POWER_LAW_BAND: tuple[float, float] = (1.5, 3.0)
DECLINE_SHARE_TOLERANCE: float = 0.05
SOFT_DECLINE_BAND: tuple[float, float] = (0.68, 0.82)
MIN_EVENTS_PER_ENTITY: int = 5


def test_benford_chi2_on_amount() -> None:
    world = fixture_world()
    chi2, _ = benford_statistics(
        world.legit["amount"].to_numpy("float64"), rng_for("pytest:benford")
    )
    assert chi2 < BENFORD_CHI2_MAX


def test_benford_mad_on_amount() -> None:
    world = fixture_world()
    digits = first_digits(world.legit["amount"].to_numpy("float64"))
    observed = np.array([(digits == value).mean() for value in range(1, 10)])
    assert float(np.abs(observed - BENFORD_EXPECTED).mean()) <= NIGRINI_ACCEPTABLE_MAD


def test_hour_of_day_night_trough() -> None:
    world = fixture_world()
    shares = pd.to_datetime(world.legit["event_ts"], utc=True).dt.hour.value_counts(normalize=True)
    night = float(shares.reindex(NIGHT_HOURS).mean())
    assert night < NIGHT_TROUGH_FRACTION * float(shares.max())


def test_population_approval_rate() -> None:
    world = fixture_world()
    rate = float((world.legit["response_code"] == "00").mean())
    assert APPROVAL_BAND[0] <= rate <= APPROVAL_BAND[1]


def test_interarrival_kurtosis() -> None:
    world = fixture_world()
    deltas = (
        world.legit.sort_values("event_ts")
        .groupby("payer_entity_id", sort=False)["event_ts"]
        .diff()
        .dt.total_seconds()
        .dropna()
    )
    assert float(kurtosis(deltas, fisher=False)) > 3.0


def test_card_fraud_prevalence() -> None:
    world = fixture_world()
    card = world.pool[world.pool["rail"].isin(["CARD_CNP", "CARD_CP"])]
    prevalence = float(card["is_fraud"].mean())
    assert CARD_PREVALENCE_BAND[0] <= prevalence <= CARD_PREVALENCE_BAND[1]


def test_upi_fraud_prevalence() -> None:
    world = fixture_world()
    upi = world.pool[world.pool["rail"] == "UPI"]
    prevalence = float(upi["is_fraud"].mean())
    assert UPI_PREVALENCE_BAND[0] <= prevalence <= UPI_PREVALENCE_BAND[1]


def test_merchant_degree_power_law() -> None:
    world = fixture_world()
    degree = world.legit["merchant_id"].dropna().value_counts().to_numpy("float64")
    fit = powerlaw.Fit(degree, verbose=False)
    assert POWER_LAW_BAND[0] <= float(fit.alpha) <= POWER_LAW_BAND[1]


def test_de39_decline_mix() -> None:
    world = fixture_world()
    mix = mix_for(world.config.decline_mix_region)
    declines = world.legit.loc[world.legit["response_code"] != "00", "response_code"]
    observed = declines.value_counts(normalize=True)
    for code in ("05", "51"):
        assert abs(float(observed.get(code, 0.0)) - mix[code]) <= DECLINE_SHARE_TOLERANCE
    combined = float(observed.get("05", 0.0) + observed.get("51", 0.0))
    assert SOFT_DECLINE_BAND[0] <= combined <= SOFT_DECLINE_BAND[1]


def test_within_entity_iet_autocorrelation() -> None:
    """The direct demonstration that the simulator produces the positive within-entity
    autocorrelation row-independent generators provably cannot. Same statistic the
    behavioural fidelity layer reads, so there is one definition of it in the project."""
    world = fixture_world()
    assert lag1_iet_autocorrelation(world.legit, "pan_token") > 0.0


def test_fraud_burstiness() -> None:
    world = fixture_world()
    fraud = world.pool[world.pool["is_fraud"]].sort_values("event_ts")
    scores = []
    for _, group in fraud.groupby("campaign_id", sort=False):
        deltas = group["event_ts"].diff().dt.total_seconds().dropna().to_numpy("float64")
        if deltas.size < MIN_EVENTS_PER_ENTITY:
            continue
        mean, deviation = float(deltas.mean()), float(deltas.std())
        if mean + deviation <= 0:
            continue
        scores.append((deviation - mean) / (deviation + mean))
    assert float(np.mean(scores)) > 0.0


def test_blind_holdout_disjoint() -> None:
    world = fixture_world()
    assert set(world.blind["event_id"]).isdisjoint(set(world.pool["event_id"]))
    assert set(world.blind["payer_entity_id"]).isdisjoint(set(world.pool["payer_entity_id"]))
