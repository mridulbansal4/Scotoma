# Sparkov partitions and the real-data Channel A fit

Status: **pipeline built and verified end to end on a shaped fixture. Not yet run on real
Sparkov, because the dataset is not on this machine.** Everything below is code that
exists and tests that pass. No number in the "results" sense is claimed yet.

---

## 1. What was blocked, and why

Sparkov is not downloaded here. There is no `kaggle` package in the venv and no
`~/.kaggle/kaggle.json`. Kaggle requires an authenticated account to download
`kartik2112/fraud-detection`, so this step needs you, not me.

Rather than stop, the whole pipeline was built and proven against a Sparkov-shaped
fixture. When the two CSVs land, three commands produce partitions, weights and a
transfer number.

### To unblock

Either download `fraudTrain.csv` and `fraudTest.csv` from
`kaggle.com/datasets/kartik2112/fraud-detection` by hand and drop them in
`data/real/raw/`, or install the CLI and place your own API token:

```bash
.venv/Scripts/python.exe -m pip install kaggle
# put your kaggle.json at C:\Users\<you>\.kaggle\kaggle.json yourself
kaggle datasets download -d kartik2112/fraud-detection -p data/real/raw --unzip
```

Do not paste the token into a chat. It is a credential; put the file in place yourself.

---

## 2. What was built

| Path | Job |
|---|---|
| `backend/realdata/sparkov.py` | Sparkov CSV to internal CES columns, temporal partition, disjointness guard |
| `backend/realdata/featurize.py` | The feature subset Sparkov can actually support |
| `backend/realdata/train.py` | Channel A fit, honest calibration metrics, weights export |
| `scripts/sparkov_pipeline.py` | `prepare` / `train` / `tstr` subcommands |
| `tests/test_realdata.py` | 9 tests, all passing |

Three commands:

```bash
python scripts/sparkov_pipeline.py prepare   # writes calib/floor/blind parquet
python scripts/sparkov_pipeline.py train     # fits Channel A, exports weights/
python scripts/sparkov_pipeline.py tstr      # scores calib-trained model on blind
```

---

## 3. The partition (A.4)

`fraudTrain.csv` is cut at 60% by time into `calib/` and `floor/`. `fraudTest.csv`
becomes `blind/` in its entirety. Sparkov's own split is already temporal, so this
preserves it and gives a holdout genuinely later than everything else.

```
data/real/
  calib/    generator sees this
  floor/    fidelity gate reference. generator never sees it
  blind/    TSTR only. nothing touches it until final scoring
```

`assert_disjoint()` runs inside `partition()` and raises `RegistryInvalid` if any
`event_id` appears in two partitions, or is duplicated inside one. This is the assertion
A.4 asks for, and `test_overlap_assertion_actually_fires` proves it can fail. A guard that
cannot fail is decoration.

Verified on the fixture:

```
calib  rows=36,000  frauds=193  prevalence=0.00536  2019-01-01 .. 2019-05-01
floor  rows=24,000  frauds=135  prevalence=0.00562  2019-05-01 .. 2019-07-19
blind  rows=20,000  frauds=117  prevalence=0.00585  2020-08-01 .. 2021-02-16
partition-overlap assertion passed
```

---

## 4. The feature count: 69, not 73

My earlier estimate said 73 of 151 features were recoverable from Sparkov.
**69 are implemented.** The correction:

| Group | Count | Status |
|---|---|---|
| Velocity on `pan_token`, `merchant_id`, `payee_entity_id` (3 keys x 5 windows x 4 aggs) | 60 | built |
| Geo, temporal and per-entity deviations | 9 | built |
| Graph features: `payer_pagerank`, `payee_pagerank`, `payee_bank_degree`, `component_size` | 4 | **deferred** |
| Velocity on `device_id`, `ip`, `agent_id` | 60 | absent from corpus |
| Session, 3DS, CES and agentic fields | 18 | absent from corpus |

The four graph features are genuinely derivable from a card-to-merchant bipartite graph.
They are not built because they need the graph construction path, which is a separate
job from this one. Counting them as delivered would have been dishonest, so the number
is 69 and this row exists.

The 9 that are built: `impossible_travel_kmh`, `first_time_payee`, `payee_age_hours`,
`mcc_novelty_for_entity`, `circadian_loglik`, `amount_z_vs_entity_history`,
`merchant_benford_dev_24h`, `fanin_payee_24h`, `fanout_payer_24h`.

### Absent means NaN, not zero

The existing `velocity_features()` zero-fills missing key families. For real data that is
wrong: a zero in `cnt_device_id_1h` is a claim that the device made no prior transactions,
when the truth is that Sparkov has no device column at all. The adapter emits NaN instead.
LightGBM splits on missing natively, so it costs the fit nothing and stops the model
learning from a constant. `test_absent_key_families_are_nan_not_zero` locks this.

Same reasoning kills the decline-rate family. Sparkov records no authorisation outcome, so
all 15 `declrate_*` columns are NaN rather than a constant 0.0 that would look like signal.

### `closed="left"` is preserved

Velocity reuses `rolling_by_key` from `backend/defend/windows.py` rather than
reimplementing it, so the point-in-time semantics come from the same tested code path the
synthetic pipeline uses. `test_velocity_excludes_the_current_row` asserts that a card's
first ever transaction has a 7-day prior count of zero. Include the current row and every
count leaks its own label.

---

## 5. Calibration discipline (A.8)

The appendix's warning is the one thing in the fit that is easy to get wrong and fatal
when you do. It is implemented as follows.

- Negatives are downsampled to 10:1 **for the booster fit only**.
- The validation slice, which is what Platt is fitted on, stays at the true base rate.
- The two prevalences are reported separately so the difference is visible, not implied.

From the fixture run:

```
prevalence_source        0.005361   the corpus
prevalence_fit           0.090909   after 10:1 downsampling, booster only
prevalence_calibration   0.005000   untouched, Platt sees this
brier_uncalibrated       0.013178
brier_calibrated         0.004900   Platt improves calibration ~2.7x
```

If Platt were fitted on the downsampled frame instead, the posteriors would describe a
10:1 world that does not exist, the Elkan threshold derived from them would be wrong, and
every `cost_per_100k` figure on `/soc` would be wrong.

`scale_pos_weight` is set, `is_unbalance` is not. `fit_channel_a` already enforces this.

---

## 6. What the fixture numbers are and are not

The fixture is randomly generated data whose only fraud signal is a shifted amount
distribution. Its `pr_auc` of 0.0205 measures nothing about fraud detection. It proves
the pipeline runs, the calibration split behaves, and the artefacts write.

**Do not quote any number from section 5 as a result.** They are plumbing evidence. Real
numbers require the real CSVs.

---

## 7. Weights bundle

`train` writes into `weights/`:

```
channel_a_lgbm.txt         native booster text, version-portable, not pickle
feature_spec.json          the 69 ordered names, order_is_significant
channel_a_metrics.json     prevalences, PR-AUC, ROC-AUC, Brier pair, reliability curve
shap_background.parquet    2,000 rows, required by interventional TreeSHAP at reload
```

`tstr` additionally writes `tstr_baseline.json`.

Already shipped elsewhere in the repo and not duplicated here: `artifacts/model.onnx`,
`artifacts/threshold.json` (which already carries `feature_names` and the Elkan
threshold), and `artifacts/reason_dictionary.json`.

Still missing from the A.8 manifest: `channel_c_iforest.joblib` (the IsolationForest is
fitted but never persisted) and `MODEL_CARD.md`.

`weights/` is gitignored except a keep-file. A weights bundle fitted on a fixture is
worse than no bundle, so the fixture-trained one produced during this work was deleted
rather than left on disk.

---

## 8. Tests

`tests/test_realdata.py`, 9 tests, all passing:

| Test | Guards |
|---|---|
| `test_partitions_do_not_share_events` | no event in two partitions |
| `test_blind_is_strictly_later_than_calib_and_floor` | the holdout is a holdout |
| `test_floor_follows_calib_in_time` | gate reference is later than what the generator saw |
| `test_overlap_assertion_actually_fires` | the guard can fail |
| `test_rejects_a_csv_that_is_not_sparkov` | wrong download fails loudly |
| `test_absent_key_families_are_nan_not_zero` | absent stays absent |
| `test_decline_rate_is_absent_because_sparkov_has_no_response_code` | no fake signal |
| `test_feature_counts_match_the_documented_split` | 69 and 60 stay true |
| `test_velocity_excludes_the_current_row` | `closed="left"` |

`backend/realdata` was added to `PACKAGE_DIRS` in `tests/test_schema.py`, so the new code
is held to the same conventions as the rest of the tree. It passes.

Full suite is unchanged otherwise, including the one known failure
`test_loop_completes_minimum_rounds` (asserts 5 rounds, the last run was 3 for time).

---

## 9. Not done

- The fidelity floor is **not yet wired**. `_split_reference_and_carrier()` in
  `backend/loop/controller.py` still splits synthetic traffic for the gate reference.
  Pointing it at `floor/` is the next change and the highest-value one.
- The four graph features are deferred, see section 4.
- The TSTR command currently reports the **real-to-real baseline** only. The synthetic-to-real
  half needs a synthetic-trained detector scored on `blind/`, which depends on the feature
  bridge between the two corpora.
- No `MODEL_CARD.md`.

---

## 10. The gap to state out loud

Channel A fitted on Sparkov has zero coverage of the agentic surface: V19 prompt
injection, cart-hash mismatch, mandate-scope breach. No public corpus contains a Payment
Mandate, an attestation or a cart hash, so this is not fixable by choosing a different
dataset. Say it before a judge finds it.
