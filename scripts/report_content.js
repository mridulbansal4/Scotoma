const K = require("./build_report.js");
const {
  P, RUNS, HEAD, SUB, BULLET, NOTE, IMG, FIGCAP, TABCAP, TBL,
  Document, Packer, Paragraph, TextRun, AlignmentType, Header, Footer, PageNumber, BorderStyle,
  F, T_TITLE, T_SUB, T_META, T_BODY, T_FOOT, T_CAP, BLACK, TABLE_W, fs, path, ROOT,
} = K;

const C = [];
const add = (...x) => x.forEach(i => C.push(i));

/* ------------------------------------------------------------- title block */
add(
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 },
    children: [new TextRun({ text: "SOLUTION WALKTHROUGH", font: F, size: T_TITLE, bold: true, color: BLACK })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 },
    children: [new TextRun({ text: "Scotoma  |  Team Scotoma", font: F, size: T_SUB, bold: true, color: BLACK })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 },
    children: [new TextRun({ text: "A Closed Adversarial Loop for Measuring Fraud-Detection Blind Spots", font: F, size: T_META, italics: true, color: BLACK })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 320 },
    children: [new TextRun({ text: "Run 2026-08-31-final  |  Seed 42  |  180 Simulated Days  |  Prototype Submission", font: F, size: T_META, color: BLACK })] }),
  new Paragraph({ spacing: { after: 240 }, border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: BLACK } },
    children: [new TextRun({ text: "", font: F, size: 2 })] }),
);

/* --------------------------------------------------------------- 1 purpose */
add(
  HEAD("1. PURPOSE AND SCOPE"),
  P("This document describes Scotoma, an offline adversarial testing layer for payment fraud detection, and reports what was measured on a committed run. Scotoma generates attacks across six payment rails, refuses to score them unless they survive a six-layer realism gate, detects them with a calibrated three-channel model, and returns whatever evaded into the next round. The output is a blind-spot map with numbers attached."),
  RUNS([["The claim defended here is deliberately narrow. ", {}],
        ["Scotoma measures and shrinks a detector's blind spots. It does not claim to make anyone monotonically safer.", { b: true }],
        [" Every figure in this document comes from a committed run artefact or a committed model artefact. Where a quantity was not measured, the text says so rather than estimating it.", {}]]),
  P("Scotoma is not a live fraud blocker and is not a replacement for a mature fraud decisioning system such as Mastercard Decision Intelligence. It is a testing and validation layer intended to sit beside one."),

  HEAD("2. PROBLEM AND ECONOMIC CONTEXT"),
  P("A fraud model is validated against the fraud that has already been seen. That is a sound way to measure yesterday and a poor way to anticipate tomorrow. A detector can hold excellent aggregate metrics while being structurally blind to an attack class that no historical label covers, and the blind spot is usually discovered only when it is exploited at volume."),
  P("Two conditions sharpen this. Attack surface is expanding across rails that share entities but not visibility, so a campaign distributed across card, instant-payment and agentic channels can appear unremarkable to any single participant. Separately, agent-initiated commerce has introduced payment mandates, attestations and cart hashes, for which no historical corpus exists at all."),
  RUNS([["The economics argue against blunt defences. Global card fraud losses reached 33.41 billion dollars in 2024 on 51.92 trillion dollars of volume, while ", {}],
        ["false declines cost merchants 50.7 billion dollars across four markets in 2022", { b: true }],
        [". The larger number sits with customers who were refused wrongly. That is why this system reports cost per 100,000 events rather than a catch rate, and why nothing below the top decision band blocks autonomously.", {}]]),
);

/* ---------------------------------------------------------- 3 architecture */
add(
  HEAD("3. SOLUTION ARCHITECTURE"),
  RUNS([["Four stages run in sequence, all offline, closed by a loop controller. The organising rule is that ", {}],
        ["all heavy cognition is offline and the live rail is arithmetic", { b: true }],
        [". Language-model reasoning, parameter search, graph simulation, fidelity testing and model retraining are batch work. The inline scoring path holds a compiled model, a probabilistic-structure lookup and a hash comparison.", {}]]),
  IMG("fig1_architecture.png", 610, 310),
  FIGCAP("The closed loop. The fidelity gate sits between generation and scoring, so unrealistic traffic never reaches the detector."),
  P("The ordering carries the argument. If generated traffic went straight to the detector, the loop would converge on attacks that are easy to generate rather than attacks that are realistic, and every downstream metric would describe an artefact. Placing the gate before the detector means a batch must first look like plausible payment traffic and only then gets to be difficult."),
  TABCAP("Implemented components and their delivery status."),
  TBL([2700, 4260, 2400], [
    ["Component", "Implementation", "Status"],
    ["Attack registry", "32 machine-readable vectors across 6 rails", "Built"],
    ["Simulator", "8 injector modules, 12 injector classes", "Built"],
    ["Fidelity gate", "6 layers, 1 rotated into shadow each round", "Built"],
    ["Channel A", "Gradient boosting over 151 features", "Built"],
    ["Channel B", "Neighbour aggregation over the entity graph", "Built, auto-disabled"],
    ["Channel C", "Isolation forest on legitimate traffic only", "Built"],
    ["Loop controller", "6-round default, hardest-campaign retention", "Built"],
    ["Party-scope projection", "Issuer, acquirer and network masks", "Built"],
    ["Red agent", "LLM proposals, offline evolutionary fallback", "Built, offline in this run"],
  ], ["l", "l", "l"]),
);

/* ------------------------------------------------------------- 4 diversity */
add(
  HEAD("4. ATTACK COVERAGE"),
  P("The registry holds 32 vectors across six rails: card-not-present (19), UPI (12), ACH (9), SEPA Instant (8), card-present (6) and agentic (5). Vectors appear on more than one rail where the attack genuinely crosses rails."),
  RUNS([["Twelve of the 32 have live simulators, which is ", {}], ["37.5 percent coverage", { b: true }],
        [". The remaining twenty are registry entries with validated schemas and no generator behind them. That distinction is enforced in the product rather than described in prose: the coverage screen greys the undelivered rows and prints the ratio, so the gap is displayed rather than implied away.", {}]]),
  TABCAP("The twelve vectors with live simulators. V07 is additionally held out of every training pool."),
  TBL([1000, 4200, 2900, 1260], [
    ["ID", "Attack", "Rails", "Tier"],
    ["V01", "PAN and CVV enumeration", "CARD_CNP", "1"],
    ["V02", "BIN attack", "CARD_CNP", "1"],
    ["V05", "Authorised push payment scam", "UPI, SEPA, ACH", "1"],
    ["V06", "UPI collect-request and mandate abuse", "UPI", "1"],
    ["V07", "Synthetic identity at scale", "CNP, UPI, SEPA, ACH", "2"],
    ["V18", "Delegated agent credential abuse", "AGENTIC", "1"],
    ["V19", "Prompt injection against agent checkout", "AGENTIC", "1"],
    ["V20", "Agent impersonation", "AGENTIC", "1"],
    ["V21", "Mandate replay and forgery", "AGENTIC", "1"],
    ["V22", "Adversarial evasion of the scorer", "CNP, UPI, AGENTIC", "2"],
    ["V28", "Mule-network orchestration", "UPI, SEPA, ACH", "1"],
    ["V31", "Cross-border SCA-gap exploitation", "CARD_CNP", "2"],
  ], ["l", "l", "l", "r"]),
  P("Four of the twelve are agentic. That concentration is deliberate and it carries the heaviest honesty burden: no public transaction corpus contains a payment mandate, an attestation or a cart hash, because the standards defining them are still arriving. Those vectors are generated from protocol structure rather than fitted to observed data."),
);

/* -------------------------------------------------------------- 5 fidelity */
add(
  HEAD("5. SIMULATION FIDELITY"),
  RUNS([["Generated attack traffic is worthless as a test if it does not resemble payment traffic, and the usual failure is subtle: marginal distributions match while the sequence structure inside an entity is destroyed. This is a measured property of a class of generators. A 2026 benchmark shows ", {}],
        ["row-independent generators degrade behavioural fraud signal 24 to 100 times while train-synthetic-test-real AUROC stays near baseline", { b: true }],
        [", so the standard quality check passes while the property a fraud model actually needs has been destroyed.", {}]]),
  P("The gate therefore checks six properties and a batch passes only if every active layer passes. One of the marginal, joint and adversarial layers is rotated into shadow each round, evaluated and reported but not enforced, so a generator cannot be tuned against a fixed set of six checks."),
  TABCAP("The six-layer gate on Scotoma traffic against a GaussianCopula ablation fitted on 50,000 rows of the same population."),
  TBL([1900, 2900, 1500, 1560, 1500], [
    ["Layer", "Statistic", "Threshold", "Scotoma", "Ablation"],
    ["Marginal", "Worst KS statistic", "0.10", "0.0117", "0.1970"],
    ["Joint", "Pairwise correlation difference", "0.15", "0.0200", "0.0442"],
    ["Joint", "Max Cramer V delta", "Reported", "0.0028", "0.5444"],
    ["Behavioural", "Composite degradation ratio", "10.0", "1.0389", "20.0"],
    ["Behavioural", "Lag-1 IET autocorrelation", "Positive", "0.0843", "-0.1192"],
    ["Adversarial", "Discriminator AUC", "0.65", "0.5176", "0.9599"],
    ["Privacy", "Membership inference AUC", "0.55", "0.5009", "Reported"],
    ["Utility", "TSTR ratio", "0.90", "0.9998", "Reported"],
  ], ["l", "l", "r", "r", "r"]),
  RUNS([["The ablation is the load-bearing evidence, because it is a test the gate could have failed and did not. A GaussianCopula synthesiser trained on the same population ", {}],
        ["fails five of the six layers", { b: true }],
        [". Its discriminator AUC of 0.9599 means a classifier separates its output from real traffic almost perfectly, and its lag-1 inter-event-time autocorrelation is negative at -0.1192 against 0.0847 for the reference. Row-independent generation does not merely weaken within-entity timing structure, it inverts it. The gate rejects that batch.", {}]]),
  SUB("5.1 Checking the gate against an external corpus"),
  P("A gate whose reference is the system's own output is marking its own homework. The reference was therefore replaced with a partition of the Sparkov corpus, which this project did not generate, and three rounds were run against it. Every round was rejected, at composite 13.20 to 13.33 against a threshold of 10.0."),
  NOTE("Interpretation note", "That rejection is not yet a fidelity verdict, and the reason is reported rather than omitted. The Sparkov partition carries 939 cards at 2.6985 events per card per day; the Scotoma frame carries 34,152 cards at 0.2966. Each external card is roughly nine times busier, so comparing inter-event-time spread across the two measures the population density gap first and realism second. The scale-free autocorrelation ratio sits at 1.40, close to parity. A density-normalised comparison is required before this number can be read as a statement about realism, and it is not built."),
);

/* ------------------------------------------------------------- 6 detection */
add(
  HEAD("6. DETECTION"),
  P("Three channels, of which two ship. Channel A is a gradient-boosted decision tree over 151 features. Channel C is an isolation forest fitted only on legitimate traffic, which is what makes an anomaly score mean anything: a model shown fraud during fitting learns that fraud is ordinary. Channel B aggregates neighbour features over the entity graph and is gated on measured lift."),
  P("The feature set is dominated by point-in-time velocity: seven entity keys by five windows by four aggregations. Every window is computed with the current row excluded. That single decision is the difference between a velocity feature and a label leak, and it is asserted in the test suite rather than assumed. Training respects a 30-day label embargo, so the model is fitted only on labels that would actually have been available at the time of the decision."),
  SUB("6.1 Calibration and the operating point"),
  P("Scores become decisions through an Elkan cost-sensitive threshold derived from a 25.00 chargeback fee, a 0.22 merchant margin, a 0.32 attrition probability and an 1,800.00 customer lifetime value. A threshold derived from miscalibrated posteriors is wrong, and every cost figure derived from it is wrong with it, so calibration is measured rather than assumed."),
  IMG("fig4_calibration.png", 590, 251),
  FIGCAP("Left: reliability on the simulated corpus, bins with at least 30 events, Brier improving from 0.003029 to 0.001320 under Platt scaling. Right: the calibrator choice measured on ULB, the one genuinely observed corpus used in this work."),
  RUNS([["Platt scaling was chosen over isotonic regression and the choice was tested rather than asserted. On ULB, at a real 0.173 percent base rate, isotonic costs ", {}],
        ["0.0251 PR-AUC", { b: true }],
        [" because it is not monotonic and therefore does not preserve ranking, it is worse on mass-weighted calibration error at 0.000181 against 0.000172, and it pins 2.56 percent of scores at exactly zero or one. A posterior of exactly one asserts certainty, and a cost-sensitive threshold cannot price certainty.", {}]]),
  P("Decisions fall into four bands: approve below 0.30, step up to 3-D Secure to 0.70, hold to 0.90, and decline with a SAR queue entry above 0.90. Nothing below 0.90 blocks autonomously, so the consequential action always has a human in the loop. Given the false-decline economics in Section 2, autonomous blocking destroys more value than it saves."),
  P("Every alert carries reason codes. TreeSHAP runs on the production model itself rather than on a surrogate, and the top contributing features are mapped through a fixed dictionary to a fixed sentence, so two analysts reading the same alert see the same explanation. A surrogate model would explain a different model from the one that made the decision, which is not an explanation."),
);

/* -------------------------------------------------------------- 7 efficacy */
add(
  HEAD("7. MEASURED EFFICACY"),
  P("What follows is measured on run 2026-08-31-final: 180 simulated days, three loop rounds, seed 42."),
  RUNS([["ROC-AUC is deliberately not the headline, and there is a published figure that shows why. On the ULB dataset the same model scores ", {}],
        ["0.957 ROC-AUC against 0.708 PR-AUC", { b: true }],
        [". At fraud prevalence the two metrics tell different stories, and only one of them moves when the alert queue becomes unusable.", {}]]),
  TABCAP("Headline detection metrics. The latency rows cover model scoring only and exclude feature assembly."),
  TBL([3600, 2200, 3560], [
    ["Metric", "Value", "Operational reading"],
    ["Precision at K", "0.8650", "Alert queue quality"],
    ["Recall at 95 percent precision", "0.7554", "Recall at a usable operating point"],
    ["False positive to true positive", "0.0210", "Review burden per catch"],
    ["False positive rate, legitimate", "0.000171", "Round 0"],
    ["Brier score, uncalibrated", "0.003029", "Before Platt scaling"],
    ["Brier score, calibrated", "0.001320", "After Platt scaling"],
    ["Model scoring p50", "0.0255 ms", "Measured, ONNX plus Platt"],
    ["Model scoring p99", "0.0939 ms", "Measured, ONNX plus Platt"],
  ], ["l", "r", "l"]),
  P("Recall of 0.7554 at 95 percent precision is the number an operations team would care about most: roughly three quarters of fraud caught at a precision level where the alert queue remains workable. The FP to TP ratio of 0.021 is favourable against a production benchmark of 13 false positives per true positive, with the caveat that it is measured against generated campaigns at this run's realised prevalence rather than a live portfolio mix. The direction is meaningful; the absolute value is not transferable."),
  SUB("7.1 Per-vector recall, including where it fails"),
  P("Aggregate metrics hide exactly the failure this system exists to find, so the per-vector view is the more important one."),
  IMG("fig2_per_vector_recall.png", 570, 302),
  FIGCAP("Recall by vector on the active campaign. V07 is the blind holdout vector and never enters any training pool."),
  P("The pattern is coherent rather than random. High-volume vectors with a sharp local signature are caught: enumeration at 0.9114, BIN attack at 0.8810, authorised push payment scam at 0.9722 and UPI mandate abuse at 0.9729 all clear the bar. These attacks concentrate activity on one entity in a short window, which is precisely what point-in-time velocity features are shaped to see."),
  RUNS([["Four vectors fail badly and they fail for one reason. ", {}],
        ["Mule-network orchestration at 0.0099", { b: true }],
        [", agent impersonation at 0.0561, adversarial evasion at 0.1841 and prompt injection at 0.2009 all distribute activity across many entities so that no single entity exceeds a velocity threshold. Transaction-local features are structurally insufficient against attacks whose signal lives in the relationships between entities rather than within any one of them. That is the finding, and it is also the argument for the graph channel that Section 7.4 shows did not clear its own bar.", {}]]),
  RUNS([["The blind holdout is the strictest test in the run. V07 never enters any training pool, and neither does the last ten percent of cardholders by index together with every device, IP and account bound only to them. Recall on V07 is ", {}],
        ["0.2050", { b: true }],
        [". A detector that had memorised the generator rather than learned behaviour would score near zero here; one with no generalisation problem would score near the vectors it trains on. Neither is true, and 0.2050 is the honest middle.", {}]]),
  SUB("7.2 Round progression and the circularity check"),
  TABCAP("Three rounds, with blind-holdout evasion reported beside active evasion."),
  TBL([1100, 1800, 1700, 1700, 1560, 1500], [
    ["Round", "PR-AUC active", "Evasion active", "Evasion blind", "FPR legit", "Cost per 100k"],
    ["0", "0.5036", "0.8644", "0.8447", "0.000171", "81,080"],
    ["1", "0.7972", "1.0000", "1.0000", "0.000000", "834,633"],
    ["2", "0.2754", "0.9264", "0.8012", "0.000230", "94,102"],
  ], ["l", "r", "r", "r", "r", "r"]),
  RUNS([["The blind column answers the circularity objection, and it is reported because it is unflattering. Evasion on the blind holdout stays between ", {}],
        ["0.8012 and 1.0000", { b: true }],
        [" across all three rounds, so the loop is not driving blind evasion down. A system reporting only the active campaign could show a curve bending in the right direction while the holdout never moved. The fidelity composite is co-reported at 1.0389, 1.0439 and 1.0341, so all three batches were realistic by the gate's own measure.", {}]]),
  P("Active PR-AUC moves from 0.5036 to 0.7972 and then falls to 0.2754. The loop is adversarial, so this is expected behaviour rather than instability: the controller feeds the hardest surviving campaigns into the next training pool and conditions the next proposals on what evaded. Round 2 is a harder examination than round 0. It does mean a single round-over-round series is not by itself evidence of improvement, and this document does not present it as such."),
  NOTE("Round 1, the instructive failure", "PR-AUC is high at 0.7972 while evasion is 1.0000 and the false positive rate is zero. The model ranked that round's campaigns well and still placed its threshold such that nothing was actioned, and the cost per 100,000 events rose to 834,633 against 81,080 in round 0. Ranking quality and operating point are different properties. A system that reported only PR-AUC would have called round 1 its best result."),
  SUB("7.3 Visibility asymmetry across parties"),
  P("The same detector was refitted under three visibility masks, each seeing only the fields one party would actually hold. This operationalises a known industry asymmetry rather than discovering it."),
  IMG("fig3_party_scope.png", 350, 229),
  FIGCAP("Per-vector recall under issuer, acquirer and network visibility. Blank cells are vectors the party cannot observe at all."),
  P("UPI mandate abuse reaches 0.7354 at network scope and is not observable at issuer or acquirer scope. BIN attack is visible to all three but weakly, at 0.1456 for the network and 0.0002 for the issuer. The operational reading is that several of these attacks are not detectable by any single institution regardless of model quality, which is a statement about data access rather than about modelling."),
  SUB("7.4 The graph channel and its measured negative result"),
  RUNS([["Channel B is built and it disabled itself. The configured bar is a 0.03 PR-AUC lift; the measured lift in this run was ", {}],
        ["-0.2092", { b: true }],
        [", so the channel was switched off automatically. It was then scoped against IBM AML HI-Small, a corpus with labelled laundering motifs that this project did not generate: 515,080 accounts and 5,078,345 edges. Laundering sources carry 1.42 times the out-degree of legitimate ones, so the aggregate structure genuinely differs, but a degree and reciprocity baseline separates individual edges at only ", {}],
        ["0.0074 PR-AUC lift", { b: true }],
        [" over the base rate, roughly four times short of the same bar.", {}]]),
  P("This is consistent with the published finding that boosted trees on neighbour-aggregated features beat the best graph neural network by 2.0 points of AUROC and 12.9 percent of AUPRC on a graph anomaly benchmark, which is why the built channel aggregates neighbour features rather than training a deep graph model. Publishing that number is more useful than shipping a decorative graph model with an unmeasured lift."),
  SUB("7.5 External corpora and their provenance"),
  TABCAP("Public corpora used, and what each was used for."),
  TBL([2700, 1900, 1900, 2860], [
    ["Corpus", "Rows", "Provenance", "Role in this work"],
    ["Sparkov", "1,852,394", "Generated", "External detector fit, gate reference"],
    ["ULB creditcardfraud", "284,807", "Observed", "Calibrator selection"],
    ["IBM AML HI-Small", "5,078,345", "Generated", "Graph channel scoping"],
  ], ["l", "r", "l", "l"]),
  P("Only ULB is observed transaction data. Sparkov is described by its publisher as simulated transactions produced by the Sparkov generator, and IBM AML is a generated benchmark. On the Sparkov partitions a detector fitted on 778,005 rows reaches PR-AUC 0.2898 against a 0.60 percent base rate, roughly a 48-fold lift, and transfers to a strictly later holdout at PR-AUC 0.0653. That fall across a six to twelve month gap is genuine temporal drift, and it is reported because it is the baseline any train-on-generated claim has to be measured against."),
  P("The value of an external corpus here is not that it is real. It is that this project did not produce it, which is what breaks the circularity in a fidelity comparison."),
);

/* --------------------------------------------------------------- 8 novelty */
add(
  HEAD("8. WHAT IS DIFFERENT"),
  P("The individual components are established. Gradient boosting on velocity features, isolation forests, cost-sensitive thresholds and synthetic data quality metrics are all known techniques. The contribution is the arrangement: a realism gate that can reject the project's own output, positioned between generation and detection, with the survivors driving the next round and a visibility mask applied to the measurement."),
  P("The gate rejects its own side. The GaussianCopula ablation is not a straw man run for this document; it is a batch produced by the project, submitted to the project's own gate, and refused on five of six layers. A quality gate that has never rejected anything is a decoration."),
  RUNS([["Two further pieces are concrete rather than architectural. The cart-hash comparison turns prompt injection into a decidable question: an agent-initiated purchase carries a hash of the cart at the moment of intent and again at settlement, and ", {}],
        ["if the two hashes differ, the cart changed between the user agreeing and the payment completing", { b: true }],
        [". That is a deterministic boolean, not a probability, and it costs a hash comparison on the inline path. Party-scope projection is the second, quantifying which vectors an issuer simply cannot see.", {}]]),
);

/* ----------------------------------------------------------- 9 feasibility */
add(
  HEAD("9. REAL-WORLD FEASIBILITY"),
  P("The deployment question is not whether the loop can run inside a payment network. It cannot, and it does not need to. The question is which parts could sit near an authorisation path and which must stay offline."),
  TABCAP("Workload separation between offline machinery and the inline scoring path."),
  TBL([2700, 2400, 4260], [
    ["Workload", "Where it runs", "Constraint"],
    ["Campaign generation and gate", "Offline batch", "Minutes per round, no latency budget"],
    ["Detector fitting and refits", "Offline batch", "55 s per fit measured on the external corpus"],
    ["Feature assembly", "Streaming or online store", "Not measured in this run"],
    ["Model scoring", "Inline, ONNX", "0.0255 ms p50, 0.0939 ms p99, measured"],
    ["Threshold and ladder", "Inline", "Four arithmetic operations"],
    ["Graph channel", "Offline batch", "30 s to 5 min lag in a production shape"],
  ], ["l", "l", "l"]),
  NOTE("Latency disclosure", "Scoring latency was measured over 10,000 iterations with 500 warmup for the compiled model plus Platt calibration. It excludes feature assembly and the feature-store lookup, which could not be measured in this run because the Redis instance was unreachable. The 50 ms inline budget and the 5 ms feature-lookup target are design constraints, not measured results. The measurement was taken on a single Intel laptop core running Python 3.11, which is not production hardware. A complete inline latency claim requires the feature path to be measured on representative infrastructure, and this document does not make one."),
  SUB("9.1 Where this would sit"),
  P("Scotoma would sit beside an existing fraud decisioning system, consume its model artefacts and report where they are blind. The practical uses are:"),
  BULLET("Model validation. Generate campaigns against a candidate model before promotion and report per-vector recall rather than a single aggregate score."),
  BULLET("Blind-spot discovery. The per-vector table in Section 7.1 is the deliverable: it names which attack classes a current model cannot see."),
  BULLET("Regression testing. Campaigns that once evaded become fixed test cases, so a model change that reopens a closed blind spot is caught before promotion."),
  BULLET("New payment paradigms. Agentic vectors can be tested before enough live fraud exists to train on, which is the case where historical validation has nothing to offer."),
  BULLET("Data-sharing arguments. The party-scope matrix quantifies what a single institution cannot see, turning a qualitative argument for consortium data into a measured one."),
  SUB("9.2 Operational requirements not yet met"),
  P("A production deployment would need several things this prototype does not have. Model rollback and artefact versioning exist only as file outputs. Drift monitoring is not implemented, since the loop measures degradation against its own campaigns rather than against live traffic. Feature availability at scoring time is assumed rather than verified. Reason codes are produced through TreeSHAP and are readable, but they have not been reviewed by an operations team for actionability, which is a different standard from being technically correct."),
);

/* ------------------------------------------------------------ 10 & 11 */
add(
  HEAD("10. LIMITATIONS"),
  P("These are stated because a reviewer will find them, and because the boundary between what was measured and what was assumed is the most useful part of this document."),
  BULLET("The loop trains and evaluates on traffic this project generates. External corpora anchor and cross-check it but do not replace it, and the agentic vectors have no external anchor at all because no public corpus contains a payment mandate, an attestation or a cart hash."),
  BULLET("Coverage is 12 of 32 vectors. The other twenty are documented registry entries with no generator behind them and are not claimed as tested."),
  BULLET("The external-reference gate run rejected all three rounds, and the population density gap described in Section 5.1 means that result cannot yet be read as a fidelity verdict in either direction."),
  BULLET("Inline latency is measured for model scoring only. The feature-store path is unmeasured, so no end-to-end authorisation latency is claimed."),
  BULLET("The blind holdout is one attack family and one entity cohort, built with divergent population parameters. It is not an independently generated holdout, and the strength of the circularity defence is bounded by that."),
  BULLET("Round-over-round PR-AUC is not evidence of improvement on its own, because campaign difficulty rises with each round. A fixed benchmark evaluated at every round would be required to separate the two effects, and it is not built."),
  BULLET("Three rounds were run in the reported configuration; the default is six. The label embargo, the cost constants and the ladder bands are configuration and have not been tuned against an institution's actual loss experience."),
  P("Production validation would require a shadow deployment against live traffic with a measured feature path, a fixed external benchmark scored at every round, and a density-normalised fidelity reference. None of those are present here."),

  HEAD("11. SUMMARY"),
  P("Scotoma generates attacks across six payment rails, refuses to score them unless they survive a gate that provably rejects a weaker generator, detects them with a calibrated three-channel model, and reports where it fails at the granularity of individual attack vectors. It catches high-velocity attacks at 0.9114 to 0.9729 recall and fails on distributed low-velocity attacks at 0.0099 to 0.2009, for a reason the architecture explains. It measures its own graph channel and switches it off. It quantifies what a single institution cannot see."),
  P("The contribution is the loop, not a leaderboard position. The most valuable output is not the aggregate score; it is the list of attacks the detector cannot see and the evidence for why."),

  HEAD("12. REFERENCES"),
  ...[
    "C. Elkan. The Foundations of Cost-Sensitive Learning. IJCAI, 2001.",
    "E. Altman et al. Realistic Synthetic Financial Transactions for Anti-Money Laundering Models. NeurIPS Datasets and Benchmarks, 2023.",
    "A. Dal Pozzolo et al. Calibrating Probability with Undersampling for Unbalanced Classification. IEEE SSCI, 2015.",
    "B. Harris. Sparkov Data Generation. Kaggle dataset kartik2112/fraud-detection, simulated credit card transactions.",
    "S. Lundberg and S. Lee. A Unified Approach to Interpreting Model Predictions. NeurIPS, 2017.",
    "J. Tang et al. GADBench: Revisiting and Benchmarking Supervised Graph Anomaly Detection. NeurIPS, 2023.",
  ].map((t, i) => new Paragraph({
    alignment: AlignmentType.LEFT,
    spacing: { after: 80, line: 260 },
    indent: { left: 340, hanging: 340 },
    children: [new TextRun({ text: `[${i + 1}]  ${t}`, font: F, size: T_CAP, color: BLACK })],
  })),
);

const doc = new Document({
  creator: "Team Scotoma",
  lastModifiedBy: "Team Scotoma",
  title: "Scotoma Solution Walkthrough",
  description: "Prototype submission, solution walkthrough",
  styles: { default: { document: { run: { font: F, size: T_BODY, color: BLACK },
                                   paragraph: { spacing: { line: 276 } } } } },
  sections: [{
    properties: {
      page: { size: { width: 12240, height: 15840 },
              margin: { top: 1440, right: 1440, bottom: 1440, left: 1440, header: 708, footer: 708 } },
    },
    headers: { default: new Header({ children: [
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 40 },
        border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: BLACK } },
        children: [new TextRun({ text: "SCOTOMA   |   SOLUTION WALKTHROUGH", font: F, size: T_FOOT, bold: true, color: BLACK })],
      })] }) },
    footers: { default: new Footer({ children: [
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: 40 },
        border: { top: { style: BorderStyle.SINGLE, size: 6, color: BLACK } },
        children: [
          new TextRun({ text: "Team Scotoma   |   Prototype Submission   |   Page ", font: F, size: T_FOOT, color: BLACK }),
          new TextRun({ children: [PageNumber.CURRENT], font: F, size: T_FOOT, color: BLACK }),
        ],
      })] }) },
    children: C,
  }],
});

Packer.toBuffer(doc).then(buf => {
  const out = path.join(ROOT, "SCOTOMA_Solution_Walkthrough.docx");
  fs.writeFileSync(out, buf);
  console.log("wrote", out, buf.length, "bytes");
});
