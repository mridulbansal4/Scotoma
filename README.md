# PayLoop — Closed-Loop Adversarial Fraud Engine

PayLoop is an offline adversarial testing lab. It manufactures its own fraud, measures where a
detector is blind, and shows which attacks are structurally invisible to a single institution.

**What PayLoop is not:** a live fraud blocker, a security guarantee, or a claim that the detector
improves monotonically. It measures and shrinks blind spots. Nothing heavy runs in the
authorisation path.

---

## What is in the box

| Deliverable | Where it lives |
|---|---|
| 32 machine-readable attack vectors and a coverage matrix | `registry/vectors.yaml`, `runs/<run_id>/coverage.json`, screen `/atlas` |
| Entity-aware simulator with 12 realism assertions | `generate/`, `pytest tests/test_realism.py` |
| Six-layer self-rejecting fidelity gate and its GaussianCopula ablation | `fidelity/`, `runs/<run_id>/ablation.json`, screen `/fidelity` |
| Three-channel detector, Elkan cost threshold, TreeSHAP reason codes | `defend/`, `runs/<run_id>/per_vector_recall.json`, screen `/soc` |
| Loop controller with a blind holdout and a co-reported fidelity composite | `loop/`, `runs/<run_id>/rounds.jsonl`, screen `/loop` |
| Party-Scope Projection matrix | `runs/<run_id>/scope_matrix.json`, screen `/loop` |
| FastAPI service, 7 endpoints plus an SSE stream | `api/` |
| Five-screen frontend that makes zero network calls | `web/` |

## Built vs narrative

| Element | Status | Spoken form |
|---|---|---|
| Entity-aware simulator, 12 injector classes | **BUILT** | "Twelve vectors have live simulators. Twenty more are registry entries. We show the gap." |
| Six-layer fidelity gate + GaussianCopula ablation | **BUILT** | "The gate rejected our own ablation data. Here is the report." |
| LightGBM Channel A + Isolation Forest Channel C | **BUILT** | "Two channels ship. Here are their numbers." |
| Graph Channel B (PageRank + neighbour aggregation → LightGBM) | **BUILT, offline batch** | "The graph channel runs as an offline batch job here. In production it sits on a stream at 30 s to 5 minutes of lag." |
| GraphSAGE / PyTorch Geometric GNN | **NOT BUILT** | "We set a three-point PR-AUC bar for a deep graph model and scoped it out. GADBench shows neighbour-aggregated features beating the best GNN, so we built that instead." |
| ONNX-compiled inline scorer + measured p50/p99 | **BUILT** | "Here is the p99 we measured on our hardware. The sub-millisecond figures you see quoted elsewhere are targets, not measurements." |
| Redis HyperLogLog feature serving (`distinct_pan_per_device`) | **BUILT, one feature family** | "One feature family is served from HyperLogLog. Here is the measured lookup latency." |
| Count-Min Sketch frequency serving | **NARRATIVE** | "Count-Min Sketch is the production answer for frequency counts. We used HyperLogLog for distinct counts in this prototype." |
| Kafka / Flink streaming infrastructure | **NARRATIVE** | "Channel B is a batch job here. The streaming deployment is the production shape, not something we built this week." |
| Four-tier mitigation ladder | **BUILT** | "Four bands, no autonomous blocking below 0.90, human in the loop for the consequential action." |
| 30-day label embargo | **BUILT** | "We train only on labels that would actually have been available." |
| Party-Scope Projection matrix | **BUILT** | "Same detector, three visibility masks. We operationalise a known asymmetry — we did not discover it." |
| Blind holdout | **BUILT, per R-A** | "One attack family and one entity cohort, neither of which enters any training pool. Not independently generated." |
| Threat Intel Compiler (A1), Forensic Reporter (A3) | **NARRATIVE** | "Two of the three agents are design surface. One LLM runs in the loop: the red agent." |
| Media-layer detection (deepfake KYC, voice clone) | **NOT BUILT, registry only** | "We see the transaction, not the video call. Those vectors are documented, not detected." |

## The three rulings

**R-A · Blind holdout.** The holdout is one attack family (V07 synthetic-identity rings) plus the
last 10% of cardholders by index, together with every device, IP and account bound exclusively to
them. The cohort is built with divergent profile parameters — Dirichlet α 0.25 against 0.40,
lognormal μ + 0.35, and exclusion from the merchant preferential-attachment step — not a random
split. Neither the family nor the cohort enters any training pool. It is **not** an independently
generated holdout, and the strength of the circularity defence is bounded by that.
Enforced by `tests/test_holdout.py` and `tests/test_claims.py::test_no_banned_phrases`.

**R-B · Behavioural degradation.** The published literature figure is quoted as a range across
row-independent generators, with no figure attributed to a named generator, because two sources
disagree on which generator produced which number. `registry/claims.yaml` holds the single approved
string. Naming GaussianCopula as PayLoop's *own* ablation baseline is a statement about this
repository and is permitted. Enforced by `tests/test_claims.py::test_no_generator_attribution`.

**R-C · Latency honesty.** No sub-millisecond figure appears anywhere. Engineering targets are round
numbers suffixed `_TARGET_MS` in `defend/bench.py`; measurements come only from
`runs/<run_id>/latency.json`, produced by 10,000 single-row scoring calls after 500 warm-up calls.
Every latency figure on screen carries a `MEASURED`, `TARGET` or `NOT MEASURED` badge, and the
measured figure names the segment it covers — ONNX model scoring plus Platt calibration — so it
cannot be read as the whole inline path.
Enforced by `tests/test_claims.py::test_no_unbadged_latency`.

## Running it

```bash
make setup       # venv, pinned dependencies, DuckDB schema
make loop        # population, campaigns, gate, detector, six rounds, artefacts
make web-data    # copy runs/<run_id> into web/data/run and render the registry to JSON
make web         # npm install && next build && next start
make test        # pytest across the whole suite
make demo        # setup -> loop -> web-data -> web, end to end from a clean clone
```

Individual stages — `make generate`, `make inject`, `make fidelity`, `make defend`, `make scopes`,
`make bench`, `make report` — each run standalone. Bootstrap is deterministic given
`POPULATION_SEED`, so a standalone stage rebuilds exactly the population and pool the full run used.

The API runs with `uvicorn api.app:app`, or through `docker compose up` alongside Redis and the web
service. Redis is required only for the job queue and the HyperLogLog feature counters; every read
route and `/detect/score` work without it.

## Reading the numbers

Every externally quotable figure lives in `registry/claims.yaml` with its provenance and its
approved phrasing. Vendor-originated figures carry `provenance: vendor` and render with a
`vendor-reported` suffix; commissioned research renders as `vendor-commissioned`. Adding a number to
the UI without adding it to `claims.yaml` fails `tests/test_claims.py`.

Run artefacts under `runs/<run_id>/` are the only source of results. No artefact is hand-edited:
`manifest.json` records the seed, the config hash and the git SHA, so an edit is visible.

## Limitations, stated first

1. There is no real seed data. Every fidelity claim is validated against PayLoop's own held-out
   legitimate population and public benchmark statistics, not production traffic. The IEEE-CIS
   reference the design contemplated is not redistributable, so the gate's reference frame is a
   held-out partition of PayLoop's own legitimate output throughout.
2. The behavioural-fidelity result the design rests on is a single 2026 study with formal proofs
   that has not yet been independently replicated.
3. Media-layer vectors — deepfake KYC, voice cloning, document forgery — are registry entries, not
   detections. PayLoop sees the transaction, never the video call.
4. Agentic protocol details are months old and moving. The CES agentic field names are PayLoop's
   modelling of concepts in the AP2 and ACP specifications, not verbatim spec fields. The underlying
   primitive is real: the cart hash is bound into the Payment Mandate, so post-approval mutation
   breaks signature verification.
5. The blind holdout is one attack family and one entity cohort from the same generator with
   divergent parameters. It is not an independently generated holdout.
6. Latency figures are measured on a single developer machine at batch size one. They are a
   feasibility signal, not a production benchmark. The HyperLogLog feature-lookup path is built
   and benchmarked, but Redis was not reachable on the machine that produced the committed run,
   so `latency.json` reports that path as `unavailable` rather than carrying a number nobody
   measured. Start Redis and re-run `make bench` to fill it in.
7. The loop measures and shrinks blind spots. It does not claim to make anyone monotonically safer.
8. The agentic rail is deliberately over-sampled relative to real-world volume because it is the
   novelty surface. It is excluded from any population-level prevalence claim.
9. The committed run simulates 1,200,000 events, not the 2,000,000 the design targets. The
   population is the full specified one — 50,000 cardholders, 4,000 merchants, 65,000 devices,
   50,000 accounts, 800 agents — but the event frame costs about 836 bytes per row and the
   machine that produced this run had 3.3 GB of free memory. `TARGET_EVENTS` is a configuration
   value: re-run with `TARGET_EVENTS=2000000` on a machine with more headroom and every artefact
   regenerates at the design volume.
10. Distinct IP addresses are capped at 762. RFC 5737 reserves exactly three documentation /24s
   and the simulator will not emit a routable address, so heavy address sharing is a structural
   property of the population rather than a modelling choice. It is also the realistic shape:
   consumer traffic arrives through carrier-grade NAT.
11. `POST /detect/score` returns one channel score, not three. Channel A is the only channel
   permitted inline: a multi-hop graph fetch cannot meet an authorisation sub-budget, and the
   isolation forest is an offline channel. Its reason codes carry no SHAP value either, because
   per-event attribution needs the training background sample and the frozen artefact set
   deliberately does not carry it. The SOC alert queue does carry real interventional TreeSHAP,
   computed against the training data at run time.
12. Layers 1 and 2 of the fidelity gate read the legitimate portion of a batch. A campaign is meant
   to depart from the legitimate amount and response-code distributions, and that departure is the
   detection signal rather than a fidelity defect; layers 3 to 6 read the whole batch.

## Three-minute walkthrough

Every figure spoken here is read off the screen in front of you. Nothing in this script is a
number to memorise; the artefacts carry them.

| # | Time | Screen | The point |
|---|---|---|---|
| 1 | 0:00–0:25 | `/atlas` | The industry refuses more good revenue than it loses to fraud. Both figures are on screen with their provenance labels — one of them is vendor-commissioned and says so. |
| 2 | 0:25–0:45 | `/atlas` | Thirty-two vectors, weighted to where the money actually leaks: mule networks, authorised push payment scams, agentic commerce. Twelve have live simulators in eight modules. The greyed rows are documented, not simulated. We show the gap rather than implying we built all thirty-two. |
| 3 | 0:45–1:35 | `/redteam` then `/loop` | The agent reads the detector's own SHAP values and proposes campaigns. Watch one get rejected by the constraint validator. Then the money chart: evasion on the active campaign against the blue line, which is the blind holdout. The orange line is the fidelity composite, co-reported so you can see we did not buy the drop by degrading our own data. |
| 4 | 1:35–2:00 | `/fidelity` | We ran a GaussianCopula ablation through our own gate. Its utility layer passed and its behavioural layer failed, because a row-independent generator has no within-entity inter-event-time structure at all. We rejected our own data. |
| 5 | 2:00–2:35 | `/loop` scope matrix | Same detector, three visibility masks. Mule fan-in does not merely get harder at issuer scope — it collapses, and it recovers at network scope. We operationalise a known asymmetry; we did not discover one. |
| 6 | 2:35–2:55 | `/soc` | Attestation valid. Signature valid. Amount inside the mandate cap. Payee unchanged. Merchant on the allowlist. Every conventional check passes. The only thing that fires is cart-hash-at-intent against cart-hash-at-settle. |
| 7 | 2:55–3:00 | `/soc` cost dial and latency card | This is the number a CFO cares about. And that p99 is measured on this laptop, for the model step specifically — the sub-millisecond figures quoted elsewhere in this space are targets, not measurements, and ours are labelled. |

If running long, cut beat 7. Never cut beats 4 or 5.

**If the network is unavailable:** nothing changes. Every screen reads committed artefacts and the
red-team console replays `sse_log.jsonl` from disk. The `AGENT: OFFLINE — evolutionary search` badge
is the reproducibility answer, not an apology: Optuna searches the same parameter space the LLM
would have proposed into.

## Judged criteria

| Criterion | Screen | Artefact | The one-line proof |
|---|---|---|---|
| Diversity of attacks identified | `/atlas` | `coverage.json`, `vectors.yaml` | 32 machine-readable vectors across six rails, 12 with live injectors, and the gap displayed rather than hidden |
| Fidelity of attacks in simulation | `/fidelity` | `fidelity_report.json`, `ablation.json` | Our own ablation passed the utility layer and failed the behavioural layer. We rejected it. |
| Detection algorithm efficacy | `/soc` | `per_vector_recall.json`, `reason_codes.json` | PR-AUC, per-vector recall including the weak ones, precision@k, FP:TP, cost per 100k, and a published negative result on the graph channel |
| Novelty of the overall solution | `/loop` | `rounds.jsonl`, `scope_matrix.json` | A self-rejecting fidelity gate, a code-level party-scope mask, and a deterministic agentic-injection primitive |
| Real-world feasibility | `/soc` | `latency.json`, `manifest.json` | Nothing heavy is in the authorisation path. Nothing blocks autonomously below 0.90. Here is the p99 we measured. |

## Repository map

```
registry/   32 vectors, every quotable claim, and the coverage matrix
schema/     the Canonical Event Schema, party-scope masks, ISO 8583 / pacs.008 / UPI / AP2 mappings
generate/   population, behaviour, graph, declines, prevalence, holdout, 12 injectors, red agent
fidelity/   six gate layers, the rotation rule, and the GaussianCopula ablation
defend/     features, temporal split, three channels, cost matrix, ladder, SHAP, scopes, benchmark
loop/       round orchestration and telemetry
api/        seven endpoints, the SSE stream, and the single error envelope
web/        five screens, reading committed artefacts, making no network calls
runs/       committed run artefacts
```

## Defensive framing

PayLoop is a defensive research tool. The registry documents mechanism, observable signals and
countermeasure; it contains no operational instructions, and `tests/test_schema.py` fails on any
mechanism field longer than 200 characters or containing an imperative. Every PAN is synthesised
inside designated test BIN ranges, which is also what keeps the project outside PCI scope. The red
agent proposes parameter settings for pre-built, sandboxed simulators and never ingests untrusted
free text. The mitigation ladder tops out at a human review queue: nothing blocks autonomously.
