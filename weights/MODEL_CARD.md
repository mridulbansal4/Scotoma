# Model card: Scotoma Channel A and Channel C, external-corpus fit

Trained 31 Aug 2026 on the Sparkov card-not-present corpus. Every number below is
measured, not projected. Where a number is weak it is printed anyway.

> ## Read this before quoting any number here
>
> **Sparkov is not real transaction data.** Kaggle's own listing subtitles it *"Simulated
> Credit Card Transactions generated using Sparkov"*, a generator written by Brandon
> Harris. It is not production traffic and must never be described as such.
>
> What it is, and why it still matters: it is data produced by a generator that is not
> ours. That is what breaks the circularity. A fidelity gate whose reference is Scotoma's
> own output is marking its own homework; a gate whose reference is an independent
> generator is measuring something. The correct claim is **"an independent generator's
> traffic"**, not "the real-data noise floor".
>
> Of the three corpora in the data appendix, only ULB `creditcardfraud` is genuinely
> observed transactions, and its features are PCA components, so it is useful for
> calibration and nothing else. There is no public corpus that is simultaneously real,
> feature-readable and card-not-present.

---

## What this is

Two of Scotoma's three detection channels, fitted on the Sparkov card-not-present corpus
(`kartik2112/fraud-detection`, 1,852,394 transactions, Jan 2019 to Dec 2020, simulated).

| File | What it is |
|---|---|
| `channel_a_lgbm.txt` | LightGBM booster, native text format. Version-portable, unlike a pickle |
| `channel_c_iforest.joblib` | IsolationForest, fitted on legitimate rows only |
| `feature_spec.json` | The 69 feature names, in order. Order is significant at reload |
| `shap_background.parquet` | 2,000 rows. Interventional TreeSHAP will not run without it |
| `channel_a_metrics.json` | Everything in the results section below, machine readable |
| `tstr_baseline.json` | The same-corpus transfer baseline |

The calibrated scorer, Elkan threshold and reason dictionary already ship in `artifacts/`
(`model.onnx`, `threshold.json`, `reason_dictionary.json`) and are not duplicated here.

---

## Training corpus and partition

Split once by time, before anything was fitted. Sparkov's own train/test split is already
temporal and was preserved rather than reshuffled.

| Partition | Rows | Frauds | Prevalence | Span | Who may see it |
|---|---:|---:|---:|---|---|
| `calib` | 778,005 | 4,585 | 0.589% | 2019-01-01 to 2019-11-29 | generator and Channel A |
| `floor` | 518,670 | 2,921 | 0.563% | 2019-11-29 to 2020-06-21 | fidelity gate reference only |
| `blind` | 555,719 | 2,145 | 0.386% | 2020-06-21 to 2020-12-31 | nothing until final scoring |

Partitions are disjoint by `event_id`, asserted in code rather than assumed
(`backend/realdata/sparkov.py::assert_disjoint`, exercised by `tests/test_realdata.py`).
`blind` is strictly later in time than both others, so the holdout is a holdout.

Prevalence falls from 0.589% to 0.386% across the year. That drift is in the corpus, not
introduced by the split, and it matters for the transfer number below.

---

## Prevalence at fit time versus calibration time

This is the single easiest thing to get wrong in a rare-event model, so it is stated
explicitly.

| Stage | Prevalence | Rows |
|---|---:|---:|
| Source corpus | 0.5893% | 778,005 |
| Booster fit, after 10:1 negative downsampling | 9.0909% | 40,128 |
| Platt calibration slice, untouched | 0.6022% | 155,601 |

Negatives were downsampled for the booster only. The Platt layer was fitted on a held-out
temporal slice left at the true base rate. Had it been fitted on the downsampled frame,
the posteriors would describe a 10:1 world that does not exist, the Elkan threshold
derived from them would be wrong, and every cost-per-100k figure in the product would be
wrong with it.

`scale_pos_weight` is set. `is_unbalance` is not. Never both.

---

## Results

### Channel A, in-period (last 20% of `calib`, held out temporally)

| Metric | Value |
|---|---:|
| PR-AUC | **0.2898** |
| ROC-AUC | 0.9444 |
| Brier, uncalibrated | 0.013344 |
| Brier, calibrated | **0.005108** |

PR-AUC 0.2898 against a 0.6022% base rate is roughly a 48x lift. Platt improves the Brier
score by 2.6x, which is the number that licenses the cost matrix.

ROC-AUC 0.9444 is reported second and deliberately so. At this prevalence ROC-AUC flatters
every model; PR-AUC is the one that moves when the model is actually wrong.

### Channel A, transferred to `blind` (same-corpus baseline)

| Metric | Value |
|---|---:|
| PR-AUC | **0.0653** |
| ROC-AUC | 0.8665 |
| Rows | 555,719 |
| Prevalence | 0.386% |

**PR-AUC falls from 0.2898 to 0.0653 across a six to twelve month gap.** This is the most
important number in the card and it is a bad one. It is reported because it is the honest
baseline that any train-on-synthetic-test-on-real claim has to be measured against. A
synthetic-trained detector scoring 0.05 on `blind` would be doing 77% as well as a
Sparkov-trained model, and that ratio only means something because this denominator was
measured rather than assumed.

The drop is genuine temporal drift, not a bug: prevalence falls by a third across the same
window, and the fit never sees a single row from it.

### Calibration reliability

Three populated bins on the calibration slice:

| Predicted | Observed | n |
|---:|---:|---:|
| 0.0018 | 0.0017 | 151,000 |
| 0.1364 | 0.0988 | 4,121 |
| 0.2202 | 0.5833 | 480 |

The low bin, which carries 97% of the mass, is well calibrated. The top bin is
**over-confident in the wrong direction**: the model predicts 0.22 where the observed rate
is 0.58, so it under-scores its own strongest cases. With 480 rows this is thin, but it is
a real weakness and it argues for treating the highest band as a floor, not a ceiling.

### Channel C

Fitted on 773,420 legitimate rows. 4,585 fraud rows excluded. Contamination 0.008.

Fitting an anomaly detector on fraud teaches it that fraud is normal, which is the one
thing it exists not to believe. Zero-day recall only means something if the model has
never been shown the thing it is asked to find surprising.

---

## Feature coverage, and what is missing

69 features of the detector's full 151.

| Group | Count | Present |
|---|---:|---|
| Velocity on `pan_token`, `merchant_id`, `payee_entity_id` | 60 | yes |
| Geo, temporal and per-entity deviations | 9 | yes |
| Graph features (`payer_pagerank`, `payee_pagerank`, `payee_bank_degree`, `component_size`) | 4 | derivable, not built |
| Velocity on `device_id`, `ip`, `agent_id` | 60 | absent from corpus |
| Session, 3DS, CES and agentic fields | 18 | absent from corpus |

Absent families are encoded NaN, never zero. A zero in `cnt_device_id_1h` asserts that the
device had no prior activity; the truth is that Sparkov has no device column. LightGBM
splits on missing natively, so the distinction costs the fit nothing and stops the model
learning from a constant. The same applies to all 15 `declrate_*` columns: Sparkov records
no authorisation outcome.

Velocity uses `closed="left"`, so an event never counts itself. A card's first ever
transaction has a prior 7-day count of zero, asserted in tests. Include the current row and
every count leaks its own label.

### Substitutions, stated rather than implied

- `merchant` fills both `merchant_id` and `payee_entity_id`. In retail card traffic the
  acceptor and the payee are the same party.
- Sparkov's 14 retail categories are hand-mapped to MCC ranges. `category` is the only MCC
  analogue in the corpus.
- There is no device telemetry here. `cc_num` plus geography is the closest available
  proxy and it is not the same thing.

---

## The agentic gap

**This model has zero coverage of the agentic attack surface.** No prompt injection, no
cart-hash mismatch, no mandate-scope breach, no attestation failure.

That is not an oversight and it cannot be fixed by choosing a different dataset. No public
corpus contains a Payment Mandate, an attestation, or a cart hash, because the standards
that define them are still arriving. The real data anchors the legitimate manifold and the
classical card-not-present vectors. The agentic surface is necessarily synthetic, and that
gap is the reason the project exists.

---

## Reproducing

```bash
kaggle datasets download -d kartik2112/fraud-detection -p data/real/raw --unzip
python scripts/sparkov_pipeline.py prepare
python scripts/sparkov_pipeline.py train
python scripts/sparkov_pipeline.py tstr
```

Deterministic given `population_seed`. Partition 13 s, fit 55 s including Channel C,
transfer scoring 44 s, on a 4-core Windows laptop.

The 55 s fit is comfortably inside the 90 s budget the loop needs, since the controller
refits once per round plus once at init.

---

## Known limitations

1. The transfer number is same-corpus only. The synthetic-to-real half needs a feature
   bridge between the two corpora and is not built.
2. The top calibration bin is under-confident on 480 rows.
3. Four graph features are derivable and not built.
4. Sparkov is simulated, see the banner at the top. Independent of Scotoma, not real.
