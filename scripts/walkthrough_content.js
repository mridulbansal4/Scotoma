// Content and assembly for SCOTOMA_Solution_Walkthrough.docx.
const K = require("./build_walkthrough.js");
const {
  p, rich, h1, h2, bullet, caption, figure, table, rule,
  Document, Packer, Paragraph, TextRun, AlignmentType, PageBreak, Footer, PageNumber,
  FONT, BODY, TITLE, SMALL, LINE, ACC, INK, fs, path, ROOT,
} = K;

const W3 = [3400, 3000, 2960];
const W4 = [2500, 2400, 2300, 2160];
const W5 = [2100, 1900, 1800, 1800, 1760];

const children = [];
const add = (...xs) => xs.forEach(x => children.push(x));

/* ---------------------------------------------------------------- cover */
add(
  new Paragraph({ spacing: { before: 1600, after: 0 }, alignment: AlignmentType.LEFT,
    children: [new TextRun({ text: "SCOTOMA", font: FONT, size: 56, bold: true, color: INK })] }),
  new Paragraph({ spacing: { before: 60, after: 320 }, alignment: AlignmentType.LEFT,
    children: [new TextRun({ text: "A closed adversarial loop for measuring fraud-detection blind spots",
      font: FONT, size: 28, color: ACC })] }),
  rule(),
  p("Solution walkthrough, prepared for technical review.", { align: AlignmentType.LEFT }),
  p("Scotoma manufactures its own fraud, refuses to use it unless it survives a six-layer realism gate, scores it with a three-channel detector, and feeds whatever evaded back into the next round. It measures where a detector is blind and shows which attacks are structurally invisible to a single institution. It is an offline testing layer, not a live fraud blocker, and nothing in the loop sits in the authorisation path.",
    { align: AlignmentType.LEFT }),
  p("Every figure in this document comes from a committed run or a committed model artefact. Where a number was not measured, the text says so.",
    { align: AlignmentType.LEFT, italics: true }),
  new Paragraph({ spacing: { before: 600, after: 0 },
    children: [new TextRun({ text: "Run 2026-08-31-final  |  population seed 42  |  180 simulated days  |  three loop rounds",
      font: FONT, size: SMALL, color: "6E6862" })] }),
  new Paragraph({ children: [new PageBreak()] }),
);

/* ------------------------------------------------------------- 1 problem */
add(
  h1("1. The gap this addresses"),
  p("A fraud model is validated against the fraud that has already been seen. That is a sound way to measure yesterday and a poor way to anticipate tomorrow. The failure mode is specific: a detector can hold excellent aggregate metrics while being structurally blind to an attack class that no historical label covers, and nobody discovers the blind spot until it is exploited at volume."),
  p("Two conditions make this worse in current payments. Attack surface is expanding across rails that share entities but not visibility, so a campaign can be distributed across card, instant-payment and agentic channels and appear unremarkable to any single participant. And agent-initiated commerce introduces vectors, including payment mandates, attestations and cart hashes, for which no historical corpus exists at all."),
  p("Scotoma addresses the measurement problem rather than the blocking problem. It generates adversarial traffic, tests whether that traffic is realistic enough to be worth scoring, measures precisely which vectors the detector misses, and repeats with the survivors. The output is a blind-spot map with numbers attached."),

  h1("2. System architecture"),
  p("Four stages run in sequence, all offline. The loop controller closes them."),
  figure("fig1_architecture.png", 600, 305),
  caption("fig", "The closed loop. The fidelity gate sits between generation and scoring so that unrealistic traffic never reaches the detector, which is what stops the loop optimising against its own artefacts."),
  p("The ordering carries the argument. If generated traffic went straight to the detector, the loop would converge on attacks that are easy to generate rather than attacks that are realistic, and every downstream metric would describe an artefact. Placing the gate before the detector means a batch must first look like plausible payment traffic and only then gets to be difficult."),
  table(W3, [
    ["Component", "Implementation", "Status"],
    ["Attack registry", "32 machine-readable vectors, 6 rails", "built"],
    ["Simulator", "8 injector modules, 12 injector classes", "built"],
    ["Fidelity gate", "6 layers, 1 rotated into shadow per round", "built"],
    ["Channel A", "gradient boosting, 151 features", "built"],
    ["Channel B", "neighbour aggregation over the entity graph", "built, auto-disabled"],
    ["Channel C", "isolation forest on legitimate traffic", "built"],
    ["Loop controller", "6-round default, hardest-campaign retention", "built"],
    ["Party-scope projection", "issuer, acquirer and network masks", "built"],
    ["Red agent", "LLM proposals with offline evolutionary fallback", "built, offline in this run"],
  ], ["l","l","l"]),
  caption("tab", "Implemented components. Channel B is built and was disabled by its own lift bar during this run, which Section 6.5 quantifies."),
);

/* ------------------------------------------------------- 3 attack surface */
add(
  h1("3. Attack coverage"),
  p("The registry holds 32 vectors across six rails: card-not-present (19), UPI (12), ACH (9), SEPA Instant (8), card-present (6) and agentic (5). Vectors appear on more than one rail where the attack genuinely crosses rails."),
  rich([["Twelve of the 32 have live simulators, which is ", {}], ["37.5 percent coverage", { b: true }],
        [". The remaining twenty are registry entries with schemas and no generator behind them. That distinction is enforced in the product rather than described in prose: the coverage screen greys the undelivered rows and prints the ratio, so the gap is displayed rather than implied away.", {}]]),
  table(W4, [
    ["Vector", "Attack", "Rails", "Tier"],
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
  ], ["l","l","l","r"]),
  caption("tab", "The twelve vectors with live simulators. V07 is additionally held out of every training pool as the blind vector."),
  p("Four of the twelve are agentic. That concentration is deliberate and it is also where the honesty burden is highest: no public transaction corpus contains a payment mandate, an attestation or a cart hash, because the standards that define them are still arriving. Those four vectors are therefore generated from protocol structure rather than fitted to observed data, and Section 9 states the consequence for the detector."),
  p("The registry is validated at import. A malformed vector, a duplicate identifier or a count other than the declared 32 aborts the process rather than degrading quietly."),
);

/* ---------------------------------------------------------- 4 fidelity */
add(
  h1("4. Simulation fidelity"),
  p("Generated attack traffic is worthless as a test if it does not resemble payment traffic, and the usual failure is subtle: marginal distributions match while the sequence structure inside an entity is destroyed. The gate therefore checks six properties, and a batch passes only if every active layer passes."),
  p("One of the marginal, joint and adversarial layers is rotated into shadow each round. A shadow layer is evaluated and reported but not enforced, so a generator cannot be tuned against a fixed set of six checks."),
  table(W5, [
    ["Layer", "Statistic", "Threshold", "Scotoma", "Ablation"],
    ["Marginal", "worst KS", "0.10", "0.0117", "0.1970"],
    ["Joint", "pairwise corr. diff", "0.15", "0.0200", "0.0442"],
    ["Joint", "max Cramer V delta", "reported", "0.0028", "0.5444"],
    ["Behavioural", "composite ratio", "10.0", "1.0389", "20.0"],
    ["Behavioural", "lag-1 IET autocorr.", "positive", "0.0843", "-0.1192"],
    ["Adversarial", "discriminator AUC", "0.65", "0.5176", "0.9599"],
    ["Privacy", "membership inference AUC", "0.55", "0.5009", "reported"],
    ["Utility", "TSTR ratio", "0.90", "0.9998", "reported"],
  ], ["l","l","r","r","r"]),
  caption("tab", "The six-layer gate on Scotoma traffic against a GaussianCopula ablation fitted on 50,000 rows of the same population. Lower is better for every row except the TSTR ratio and the autocorrelation."),
  rich([["The ablation is the load-bearing evidence here, because it is a test the gate could have failed and did not. A GaussianCopula synthesiser trained on the same population ", {}],
        ["fails five of the six layers", { b: true }],
        [". Its discriminator AUC of 0.9599 means a classifier separates its output from real traffic almost perfectly. Its lag-1 inter-event-time autocorrelation is ", {}],
        ["negative at -0.1192", { b: true }],
        [", against 0.0847 for the reference: row-independent generation does not merely weaken within-entity timing structure, it inverts it. The gate rejects that batch, which is the demonstration that the gate discriminates rather than approves.", {}]]),
  h2("4.1 Checking the gate against an external generator"),
  p("A gate whose reference is the system's own output is marking its own homework. To test that, the reference was replaced with a partition of the Sparkov corpus, which is traffic Scotoma did not produce, and three rounds were run against it."),
  rich([["Every round was rejected, at composite 13.20 to 13.33 against a threshold of 10.0. That result is reported here rather than buried, and so is the reason it is ", {}],
        ["not yet a fidelity verdict", { b: true }],
        [". The two comparable velocity ratios are 48.97 on the card key and 83.62 on the merchant key, but the two corpora describe different worlds: the Sparkov partition carries 939 cards at 2.6985 events per card per day, while the Scotoma frame carries 34,152 cards at 0.2966. Each external card is roughly nine times busier. Comparing inter-event-time spread across populations of that density measures the density gap first and realism second. The autocorrelation ratio, which is scale-free, sits at 1.40 and is close to parity.", {}]]),
  p("The correct reading is that the gate detects two different populations, and that a density-normalised comparison is required before the number can be read as a realism statement. That work is not done."),
);

/* ---------------------------------------------------------- 5 detection */
add(
  h1("5. Detection"),
  p("Three channels, of which two ship. Channel A is a gradient-boosted decision tree over 151 features. Channel C is an isolation forest fitted only on legitimate traffic, which is what makes an anomaly score mean anything: a model shown fraud during fitting learns that fraud is ordinary. Channel B aggregates neighbour features over the entity graph and is gated on measured lift."),
  p("The feature set is dominated by point-in-time velocity: seven entity keys by five windows by four aggregations. Every window is computed with the current row excluded. That single decision is the difference between a velocity feature and a label leak, and it is asserted in the test suite rather than assumed."),
  p("Training respects a 30-day label embargo, so the model is fitted only on labels that would actually have been available at the time of the decision. Chargeback labels arrive late in practice, and a model trained on labels from the future reports a score it could never have achieved in production."),
  h2("5.1 Calibration and the operating point"),
  p("Scores are converted to decisions through an Elkan cost-sensitive threshold derived from four constants: a 25.00 chargeback fee, a 0.22 merchant margin, a 0.32 attrition probability and an 1,800.00 customer lifetime value. A threshold derived from miscalibrated posteriors is wrong, and every cost figure derived from it is wrong with it, so calibration is measured rather than assumed."),
  figure("fig4_calibration.png", 600, 256),
  caption("fig", "Left: reliability on the simulated corpus, bins with at least 30 events, Brier improving from 0.003029 to 0.001320 under Platt scaling. Right: the calibrator choice measured on ULB, the one genuinely observed corpus used in this work."),
  rich([["Platt scaling was chosen over isotonic regression, and the choice was tested rather than asserted. On ULB, at a real 0.173 percent base rate, isotonic costs ", {}],
        ["0.0251 PR-AUC", { b: true }],
        [" because it is not monotonic and therefore does not preserve ranking, it is worse on mass-weighted calibration error (0.000181 against 0.000172), and it pins 2.56 percent of scores at exactly zero or one. A posterior of exactly one asserts certainty, and a cost-sensitive threshold cannot price certainty.", {}]]),
  p("Decisions fall into four bands: approve below 0.30, step-up to 3-D Secure to 0.70, hold to 0.90, and decline with a SAR queue entry above 0.90. Nothing below 0.90 blocks autonomously, so the consequential action always has a human in the loop."),
);

/* ----------------------------------------------------------- 6 efficacy */
add(
  new Paragraph({ children: [new PageBreak()] }),
  h1("6. Efficacy"),
  p("What follows is measured on run 2026-08-31-final: 180 simulated days, three loop rounds, seed 42. Detection is reported on precision-oriented metrics. ROC-AUC is omitted from the headline deliberately, because at fraud prevalence it flatters every model and moves very little when the model is operationally wrong."),
  h2("6.1 Headline detection metrics"),
  table(W3, [
    ["Metric", "Value", "Reading"],
    ["Precision at K", "0.8650", "alert queue quality"],
    ["Recall at 95 percent precision", "0.7554", "recall at a usable operating point"],
    ["False positive to true positive", "0.0210", "review burden per catch"],
    ["False positive rate on legitimate traffic", "0.000171", "round 0"],
    ["Brier, uncalibrated", "0.003029", "before Platt"],
    ["Brier, calibrated", "0.001320", "after Platt"],
    ["Model scoring p50", "0.0255 ms", "measured, ONNX plus Platt"],
    ["Model scoring p99", "0.0939 ms", "measured, ONNX plus Platt"],
  ], ["l","r","l"]),
  caption("tab", "Headline metrics. The two latency rows cover model scoring only and exclude feature assembly and the feature-store lookup, which Section 8 addresses."),
  p("Recall of 0.7554 at 95 percent precision is the number an operations team would care about most: it says roughly three quarters of fraud is caught at a precision level where the alert queue remains workable. The FP to TP ratio of 0.021 says the same thing from the other side, at roughly one false positive per fifty catches."),

  h2("6.2 Per-vector recall, including where it fails"),
  p("Aggregate metrics hide exactly the failure this system exists to find. The per-vector view is therefore the more important one."),
  figure("fig2_per_vector_recall.png", 590, 313),
  caption("fig", "Recall by vector on the active campaign. Green clears the 0.60 bar, orange falls below 0.25. V07 is the blind holdout vector and never enters any training pool."),
  p("The pattern is coherent rather than random, and it is the main analytical result of the run. High-volume vectors with a sharp local signature are caught: enumeration at 0.9114, BIN attack at 0.8810, APP scam at 0.9722 and UPI mandate abuse at 0.9729 all clear the bar comfortably. These attacks concentrate activity on one entity in a short window, which is precisely what point-in-time velocity features are shaped to see."),
  rich([["Four vectors fail badly, and they fail for one reason. ", {}],
        ["Mule-network orchestration at 0.0099", { b: true }],
        [", agent impersonation at 0.0561, adversarial evasion at 0.1841 and prompt injection at 0.2009 all distribute activity across many entities so that no single entity exceeds a velocity threshold. Transaction-local features are structurally insufficient against attacks whose signal lives in the relationships between entities rather than within any one of them. That is the finding, and it is also the argument for the graph channel that Section 6.5 shows did not clear its own bar.", {}]]),
  rich([["The blind holdout is the strictest test in the run. V07 never enters any training pool, and neither does the last ten percent of cardholders by index, together with every device, IP and account bound only to them. Recall on V07 is ", {}],
        ["0.2050", { b: true }],
        [". A detector that had memorised the generator rather than learned behaviour would score near zero here; a detector with no generalisation problem would score near the vectors it trains on. Neither is true, and 0.2050 is the honest middle.", {}]]),

  h2("6.3 Round progression"),
  table(W5, [
    ["Round", "PR-AUC active", "PR-AUC blind", "Evasion active", "FPR legit"],
    ["0", "0.5036", "0.0123", "0.8644", "0.000171"],
    ["1", "0.7972", "0.0009", "1.0000", "0.000000"],
    ["2", "0.2754", "0.0051", "0.9264", "0.000230"],
  ], ["l","r","r","r","r"]),
  caption("tab", "Three rounds. Evasion is the share of campaign events that stayed under the decision threshold. The fidelity composite held at 1.0389, 1.0439 and 1.0341, so all three batches were realistic by the gate's own measure."),
  p("This table is reported as measured and it does not show clean monotonic improvement. Two things in it deserve direct comment."),
  p("First, PR-AUC on the active campaign moves from 0.5036 to 0.7972 and then falls to 0.2754. The loop is adversarial, so this is expected behaviour rather than instability: the controller feeds the hardest surviving campaigns into the next training pool, and the red agent conditions the next proposals on what evaded. Round 2 is a harder examination than round 0, and a falling score against a rising difficulty is not the same as a degrading model. It does mean that a single round-over-round PR-AUC series is not by itself evidence of improvement, and this document does not present it as such."),
  rich([["Second, round 1 is the instructive failure. PR-AUC is high at 0.7972 while evasion is ", {}], ["1.0000", { b: true }],
        [" and the false positive rate is zero. The model ranked that round's campaigns well and still placed its threshold such that nothing was actioned, and the cost per 100,000 events rose to 834,633 against 81,080 in round 0. Ranking quality and operating point are different properties, and a system that reported only PR-AUC would have called round 1 its best result.", {}]]),

  h2("6.4 Visibility asymmetry"),
  p("The same detector was refitted under three visibility masks, each seeing only the fields one party would actually hold. This operationalises a known asymmetry rather than discovering it."),
  figure("fig3_party_scope.png", 400, 261),
  caption("fig", "Per-vector recall under issuer, acquirer and network visibility. Blank cells are vectors the party cannot observe at all."),
  p("UPI mandate abuse reaches 0.7354 at network scope and is not observable at issuer or acquirer scope. BIN attack is visible to all three but weakly, at 0.1456 for the network and 0.0002 for the issuer. The operational reading is that several of these attacks are not detectable by any single institution regardless of model quality, which is a statement about data access rather than about modelling."),

  h2("6.5 The graph channel, and its measured negative result"),
  rich([["Channel B is built and it disabled itself. The configured bar is a 0.03 PR-AUC lift; the measured lift in this run was ", {}],
        ["-0.2092", { b: true }],
        [", so the channel was switched off automatically. It was then scoped against IBM AML HI-Small, a corpus with labelled laundering motifs that Scotoma did not generate: 515,080 accounts and 5,078,345 edges. Laundering sources there carry 1.42 times the out-degree of legitimate ones, so the aggregate structure genuinely differs, but a degree and reciprocity baseline separates individual edges at only ", {}],
        ["0.0074 PR-AUC lift", { b: true }],
        [" over the base rate, roughly four times short of the same 0.03 bar.", {}]]),
  p("The conclusion is that a graph channel would have to beat simple structural features fourfold before it earns its complexity here. Publishing that number is more useful than shipping a decorative graph model with an unmeasured lift, and it is consistent with the vectors in Section 6.2 that need relational signal: the requirement is real, and the current evidence says a naive graph model does not meet it."),

  h2("6.6 External corpora"),
  p("Three public corpora were used, and their provenance differs in a way that matters for how each result should be read."),
  table(W4, [
    ["Corpus", "Rows", "Provenance", "Role"],
    ["Sparkov", "1,852,394", "generated", "external detector fit and gate reference"],
    ["ULB creditcardfraud", "284,807", "observed", "calibrator selection"],
    ["IBM AML HI-Small", "5,078,345", "generated", "graph channel scoping"],
  ], ["l","r","l","l"]),
  caption("tab", "External corpora. Only ULB is observed transaction data. Sparkov is described by its publisher as simulated transactions produced by the Sparkov generator, and IBM AML is a generated benchmark."),
  p("On the Sparkov partitions, a detector fitted on 778,005 rows reaches PR-AUC 0.2898 against a 0.60 percent base rate, roughly a 48-fold lift, and transfers to a strictly later holdout at PR-AUC 0.0653. That fall across a six to twelve month gap is genuine temporal drift, and it is reported because it is the baseline any train-on-generated claim has to be measured against."),
  p("The value of an external corpus here is not that it is real. It is that Scotoma did not produce it, which is what breaks the circularity in a fidelity comparison. Where this document refers to external traffic it means traffic from an independent generator, except for ULB, which is observed."),
);

/* ------------------------------------------------------------ 7 novelty */
add(
  h1("7. What is different"),
  p("The individual components are established. Gradient boosting on velocity features, isolation forests, cost-sensitive thresholds and synthetic data quality metrics are all known techniques. The contribution is the arrangement, and specifically three properties of it."),
  p("The gate sits before the detector, so difficulty and realism are separated. A generated batch can only become part of the test if it first passes as plausible traffic, which removes the standard failure of adversarial generation where the system converges on artefacts that are hard to detect precisely because they are unrealistic."),
  p("The gate rejects its own side. The GaussianCopula ablation is not a straw man run for the report; it is a batch produced by the project, submitted to the project's own gate, and refused on five of six layers. A quality gate that has never rejected anything is a decoration."),
  p("Failures are retained rather than discarded. The controller keeps the hardest surviving campaigns, adds them to the training pool, and conditions the next round's proposals on exactly what evaded. The measurement is not an evaluation appended to the end of a pipeline, it is the input to the next iteration."),
  p("The claim is not that no one has built adversarial testing for fraud. It is that this specific combination, a realism gate that can reject its own output, positioned between generation and detection, with the survivors driving the next round, is a workflow that produces a blind-spot map instead of a leaderboard score."),
);

/* -------------------------------------------------------- 8 feasibility */
add(
  h1("8. Production feasibility"),
  p("The deployment question is not whether the loop can run in a payment network. It cannot, and it does not need to. The question is which parts of this system could sit near an authorisation path and which parts must stay offline."),
  table(W3, [
    ["Workload", "Where it runs", "Constraint"],
    ["Campaign generation and gate", "offline batch", "minutes per round, no latency budget"],
    ["Detector fitting and refits", "offline batch", "55 s per fit measured on the external corpus"],
    ["Feature assembly", "streaming or online store", "not measured in this run"],
    ["Model scoring", "inline, ONNX", "0.0255 ms p50, 0.0939 ms p99 measured"],
    ["Threshold and ladder", "inline", "four arithmetic operations"],
    ["Graph channel", "offline batch", "30 s to 5 min lag in a production shape"],
  ], ["l","l","l"]),
  caption("tab", "Workload separation. The expensive adversarial machinery is entirely offline; only scoring and banding are on the inline path."),
  rich([["The measured scoring latency is 0.0255 ms at p50 and 0.0939 ms at p99 over 10,000 iterations with 500 warmup, for the compiled model plus Platt calibration. That figure is honest about what it excludes: it does not include feature assembly, and it does not include the feature-store lookup, which could not be measured in this run because the Redis instance was unreachable. The 50 ms inline budget and the 5 ms feature-lookup target are therefore ", {}],
        ["design constraints, not measured results", { b: true }],
        [". A complete inline latency claim requires the feature path to be measured, and this document does not make one.", {}]]),
  h2("8.1 Where this would sit"),
  p("Scotoma is not a replacement for a mature fraud decisioning system and is not positioned as one. It is a continuous adversarial testing layer that would sit beside such a system and consume its model artefacts."),
  bullet("Model validation. Generate campaigns against a candidate model before promotion, and report per-vector recall rather than a single aggregate."),
  bullet("Blind-spot discovery. The per-vector table in Section 6.2 is the deliverable: it names which attack classes a current model cannot see."),
  bullet("Regression testing. Campaigns that once evaded become fixed test cases, so a model change that reopens a closed blind spot is caught before promotion."),
  bullet("New payment paradigms. Agentic vectors can be tested before enough live fraud exists to train on, which is the case where historical validation has nothing to offer."),
  bullet("Data-sharing arguments. The party-scope matrix quantifies what a single institution cannot see, which turns a qualitative argument for consortium data into a measured one."),
  h2("8.2 Operational requirements this does not yet meet"),
  p("A production deployment would need several things the prototype does not have. Model rollback and artefact versioning exist only as file outputs. Drift monitoring is not implemented; the loop measures degradation against its own campaigns, not against live traffic. Feature availability at scoring time is assumed rather than verified, and the Redis feature path is unmeasured. Reason codes are produced through TreeSHAP and are readable, but they have not been reviewed by an operations team for actionability, which is a different standard from being technically correct."),
);

/* ------------------------------------------------------- 9 limitations */
add(
  h1("9. Limitations"),
  p("The following are stated because a reviewer will find them, and because the boundary between what was measured and what was assumed is the most useful part of this document."),
  bullet("The loop trains and evaluates on traffic Scotoma generates. External corpora anchor and cross-check it, but they do not replace it, and the agentic vectors have no external anchor at all because no public corpus contains a payment mandate, an attestation or a cart hash."),
  bullet("Coverage is 12 of 32 vectors. The other twenty are documented registry entries with no generator behind them and are not claimed as tested."),
  bullet("The external-reference gate run rejected all three rounds, and the population density gap described in Section 4.1 means that result cannot yet be read as a fidelity verdict in either direction."),
  bullet("Inline latency is measured for model scoring only. The feature-store path is unmeasured, so no end-to-end authorisation latency is claimed."),
  bullet("The blind holdout is one attack family and one entity cohort, built with divergent population parameters. It is not an independently generated holdout, and the strength of the circularity defence is bounded by that."),
  bullet("Round-over-round PR-AUC is not evidence of improvement on its own, because campaign difficulty rises with each round. A fixed benchmark evaluated at every round would be required to separate the two effects, and it is not built."),
  bullet("Three rounds were run in the reported configuration; the default is six. The 30-day label embargo, the cost constants and the ladder bands are all configuration and have not been tuned against an institution's actual loss experience."),
  p("What would be required for production validation is a shadow deployment against live traffic with a measured feature path, a fixed external benchmark scored every round, and a density-normalised fidelity reference. None of those are present here."),

  h1("10. Summary"),
  p("Scotoma generates attacks across six payment rails, refuses to score them unless they survive a six-layer realism gate that provably rejects a weaker generator, detects them with a calibrated three-channel model, and reports where it fails at the granularity of individual attack vectors. It catches high-velocity attacks well, at 0.9114 to 0.9729 recall on four vectors, and it fails on distributed low-velocity attacks, at 0.0099 to 0.2009 on four others, for a reason the architecture explains. It measures its own graph channel and switches it off. It quantifies what a single institution cannot see."),
  p("The contribution is the loop, not a leaderboard position. The most valuable output is not the aggregate score, it is the list of attacks the detector cannot see and the evidence for why."),

  h1("References"),
  p("[1] Elkan, C. The Foundations of Cost-Sensitive Learning. IJCAI, 2001.", { align: AlignmentType.LEFT, after: 60 }),
  p("[2] Altman, E. et al. Realistic Synthetic Financial Transactions for Anti-Money Laundering Models. NeurIPS Datasets and Benchmarks, 2023.", { align: AlignmentType.LEFT, after: 60 }),
  p("[3] Dal Pozzolo, A. et al. Calibrating Probability with Undersampling for Unbalanced Classification. IEEE SSCI, 2015.", { align: AlignmentType.LEFT, after: 60 }),
  p("[4] Harris, B. Sparkov Data Generation. Kaggle dataset kartik2112/fraud-detection, simulated credit card transactions.", { align: AlignmentType.LEFT, after: 60 }),
  p("[5] Lundberg, S. and Lee, S. A Unified Approach to Interpreting Model Predictions. NeurIPS, 2017.", { align: AlignmentType.LEFT, after: 60 }),
  p("[6] Tang, J. et al. GADBench: Revisiting and Benchmarking Supervised Graph Anomaly Detection. NeurIPS, 2023.", { align: AlignmentType.LEFT, after: 60 }),
);

/* ---------------------------------------------------------- assemble */
const doc = new Document({
  styles: {
    default: {
      document: { run: { font: FONT, size: BODY, color: INK },
                  paragraph: { spacing: { line: LINE } } },
    },
  },
  numbering: {
    config: [{
      reference: "bul", levels: [{
        level: 0, format: "bullet", text: "•", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 460, hanging: 260 } } },
      }],
    }],
  },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 120 },
          children: [new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: SMALL, color: "6E6862" })],
        })],
      }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then(buf => {
  const out = path.join(ROOT, "SCOTOMA_Solution_Walkthrough.docx");
  fs.writeFileSync(out, buf);
  console.log("wrote", out, buf.length, "bytes");
});
