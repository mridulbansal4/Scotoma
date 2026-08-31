# Sparkov partitions and the Channel A fit

Status: **done. Downloaded, partitioned, trained, transferred, exported.** Every number
below is measured on the full 1.85M-row corpus, not projected.

> ### One correction before anything else
>
> **Sparkov is simulated data.** Kaggle's own listing subtitles it *"Simulated Credit Card
> Transactions generated using Sparkov"*, a generator written by Brandon Harris. Appendix
> A calls this a "real-data noise floor" and that phrasing is wrong.
>
> The value survives the correction, but the claim has to change. Sparkov is traffic from
> a generator that is **not ours**, and that is what breaks the circularity: a fidelity
> gate whose reference is Scotoma's own output is marking its own homework, while a gate
> referenced against an independent generator is measuring something. Say **"an
> independent generator's traffic"**. Never say "real transaction data".
>
> Of the appendix's three Tier 1 corpora, only ULB `creditcardfraud` is genuinely observed
> transactions, and its features are PCA components. There is no public corpus that is
> simultaneously real, feature-readable and card-not-present.

---

## 1. Getting the data

No Kaggle credential exists on this machine, but the download endpoint serves anonymously:

```bash
curl -sSL -o data/real/raw/sparkov.zip \
  "https://www.kaggle.com/api/v1/datasets/download/kartik2112/fraud-detection"
```

202 MB zipped, 479 MB unpacked. `fraudTrain.csv` 1,296,675 rows, `fraudTest.csv` 555,719
rows, 1,852,394 total, matching the documented size.

---

## 2. What was built

| Path | Job |
|---|---|
| `backend/realdata/sparkov.py` | CSV to internal CES columns, temporal partition, disjointness guard |
| `backend/realdata/featurize.py` | The 69 features Sparkov can actually support |
| `backend/realdata/train.py` | Channel A fit, Channel C fit, calibration metrics, weights export |
| `scripts/sparkov_pipeline.py` | `prepare` / `train` / `tstr` |
| `tests/test_realdata.py` | 9 tests |
| `backend/loop/controller.py` | `_real_floor_reference()`, the gate wiring |
| `weights/` | The shipped bundle, including `MODEL_CARD.md` |

```bash
python scripts/sparkov_pipeline.py prepare   # 13 s
python scripts/sparkov_pipeline.py train     # 55 s including Channel C
python scripts/sparkov_pipeline.py tstr      # 44 s
```

---

## 3. The partition

`fraudTrain.csv` cut at 60% by time into `calib` and `floor`; `fraudTest.csv` becomes
`blind` whole. Sparkov's own split is already temporal and was preserved.

| Partition | Rows | Frauds | Prevalence | Span |
|---|---:|---:|---:|---|
| `calib` | 778,005 | 4,585 | 0.589% | 2019-01-01 to 2019-11-29 |
| `floor` | 518,670 | 2,921 | 0.563% | 2019-11-29 to 2020-06-21 |
| `blind` | 555,719 | 2,145 | 0.386% | 2020-06-21 to 2020-12-31 |

`blind` is strictly later than both others. Prevalence drifts down by a third across the
year, which is in the corpus rather than introduced by the split, and it explains the
transfer number in section 5.

`assert_disjoint()` runs inside `partition()` and raises on any `event_id` in two
partitions. `test_overlap_assertion_actually_fires` proves the guard can fail; a guard
that cannot fail is decoration.

---

## 4. Feature coverage: 69 of 151

| Group | Count | Status |
|---|---:|---|
| Velocity on `pan_token`, `merchant_id`, `payee_entity_id` | 60 | built |
| Geo, temporal, per-entity deviations | 9 | built |
| Graph features (2 pageranks, bank degree, component size) | 4 | derivable, not built |
| Velocity on `device_id`, `ip`, `agent_id` | 60 | absent from corpus |
| Session, 3DS, CES, agentic fields | 18 | absent from corpus |

My earlier estimate of 73 counted the four graph features as available. They are
derivable from a card-to-merchant bipartite graph but were not built, so the delivered
number is 69.

Absent families are **NaN, not zero**. A zero in `cnt_device_id_1h` claims the device had
no prior activity; the truth is Sparkov has no device column. Same for all 15 `declrate_*`
columns, since Sparkov records no authorisation outcome. LightGBM splits on missing
natively, so this costs the fit nothing and stops the model learning a constant.

Velocity reuses `rolling_by_key`, so `closed="left"` comes from the same tested path the
synthetic pipeline uses. A card's first transaction has a prior 7-day count of zero,
asserted in tests.

---

## 5. Results

### Channel A, in-period (last 20% of `calib`, held out temporally)

| Metric | Value |
|---|---:|
| PR-AUC | **0.2898** |
| ROC-AUC | 0.9444 |
| Brier, uncalibrated | 0.013344 |
| Brier, calibrated | **0.005108** |

PR-AUC 0.2898 against a 0.6022% base rate is about a 48x lift. Platt improves Brier 2.6x,
which is the number that licenses the cost matrix.

### Channel A, transferred to `blind`

| Metric | Value |
|---|---:|
| PR-AUC | **0.0653** |
| ROC-AUC | 0.8665 |

**The drop from 0.2898 to 0.0653 is the most important number produced tonight, and it is
a bad one.** It is genuine temporal drift across a six to twelve month gap on data the fit
never saw. It is reported because it is the denominator every train-on-synthetic claim has
to be measured against. A synthetic-trained detector reaching 0.05 on `blind` would be at
77% of this baseline, and that ratio only means something because the baseline was
measured rather than assumed.

### Calibration

| Predicted | Observed | n |
|---:|---:|---:|
| 0.0018 | 0.0017 | 151,000 |
| 0.1364 | 0.0988 | 4,121 |
| 0.2202 | 0.5833 | 480 |

The low bin carries 97% of the mass and is well calibrated. The top bin is wrong in the
under-confident direction: predicted 0.22 against an observed 0.58. Thin at 480 rows, but
real, and it argues for treating the highest ladder band as a floor rather than a ceiling.

### Prevalence discipline

| Stage | Prevalence | Rows |
|---|---:|---:|
| Source corpus | 0.5893% | 778,005 |
| Booster fit, after 10:1 downsampling | 9.0909% | 40,128 |
| Platt calibration slice, untouched | 0.6022% | 155,601 |

Negatives downsampled for the booster only; Platt fitted at the true base rate. The other
way round and the Elkan threshold, and every cost-per-100k figure on `/soc`, would be wrong.

### Channel C

773,420 legitimate rows, 4,585 fraud rows excluded, contamination 0.008. Fitting an
anomaly detector on fraud teaches it that fraud is normal.

---

## 6. The fidelity floor is wired

`_real_floor_reference()` in `backend/loop/controller.py` replaces the synthetic gate
reference with the `floor` partition when `FIDELITY_FLOOR_SOURCE=real`. Default stays
`synthetic`, and a missing file logs a warning and falls back rather than crashing a run.

Verified: 60,000 rows load carrying `event_ts`, `amount`, `is_fraud`, `pan_token` and
`mcc`, which covers the columns the marginal, joint and behavioural layers read. The
behavioural layer keys inter-event autocorrelation on `pan_token`, which Sparkov has.

The head of the partition is used rather than a random sample, because the behavioural
layer measures within-card sequence structure and random thinning destroys it.

```bash
FIDELITY_FLOOR_SOURCE=real python -c "from backend.loop.controller import run; run()"
```

---

## 7. Weights bundle

```
weights/
  channel_a_lgbm.txt          native booster text, version-portable
  channel_c_iforest.joblib    IsolationForest, legitimate rows only
  feature_spec.json           69 ordered names
  shap_background.parquet     2,000 rows for interventional TreeSHAP
  channel_a_metrics.json      all metrics above, machine readable
  tstr_baseline.json          the transfer baseline
  MODEL_CARD.md               corpus, partitions, prevalences, results, gaps
```

Already in `artifacts/` and not duplicated: `model.onnx`, `threshold.json` (which carries
`feature_names` and the Elkan threshold), `reason_dictionary.json`.

---

## 8. Tests

`tests/test_realdata.py`, 9 passing: partition disjointness, blind strictly later, floor
after calib, the guard actually firing, non-Sparkov CSV rejection, absent-means-NaN,
declrate absence, feature counts, and `closed="left"`.

`backend/realdata` was added to `PACKAGE_DIRS` in `tests/test_schema.py`, so the new code
is held to the same conventions as the rest of the tree.

---

## 9. Not done

- **Synthetic-to-real TSTR.** The baseline half is measured; the synthetic-trained half
  needs a feature bridge between the two corpora.
- **Four graph features**, see section 4.
- **A loop run against the real floor.** The wiring is in and verified; the run itself is
  the next thing to spend 45 minutes on.
- `test_loop_completes_minimum_rounds` still fails, asserting 5 rounds where the last run
  was 3 for time. Unrelated to this work.

---

## 10. The gap to state out loud

Channel A here has zero coverage of the agentic surface: V19 prompt injection, cart-hash
mismatch, mandate-scope breach. No public corpus contains a Payment Mandate, an
attestation or a cart hash, because the standards defining them are still arriving. Not
fixable by picking a different dataset. Say it before a judge finds it.
