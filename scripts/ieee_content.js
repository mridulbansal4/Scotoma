const K = require("./build_ieee.js");
const {
  body, mixed, H1, H2, bullet, figCap, tabCap, img, tbl,
  Document, Packer, Paragraph, TextRun, AlignmentType, SectionType, Footer, PageNumber,
  F, BODY, SMALL, CAP, INK, LINE, fs, path, ROOT,
} = K;

const A4 = { width: 11906, height: 16838 };
const MARGIN = { top: 1080, right: 893, bottom: 1440, left: 893, header: 720, footer: 720 };
const TWO = { type: SectionType.CONTINUOUS, page: { size: A4, margin: MARGIN }, column: { count: 2, space: 360 } };
const ONE = { type: SectionType.CONTINUOUS, page: { size: A4, margin: MARGIN }, column: { count: 1 } };

const sections = [];
const two = (children) => sections.push({ properties: TWO, children });
const one = (children) => sections.push({ properties: ONE, children });

/* ------------------------------------------------------------------ title */
sections.push({
  properties: { page: { size: A4, margin: MARGIN }, column: { count: 1 } },
  footers: { default: new Footer({ children: [new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ children: [PageNumber.CURRENT], font: F, size: SMALL, color: INK })] })] }) },
  children: [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 },
      children: [new TextRun({ text: "Scotoma: A Closed Adversarial Loop for Measuring Fraud-Detection Blind Spots", font: F, size: 48, color: INK })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 200, after: 40 },
      children: [new TextRun({ text: "Scotoma Project Team", font: F, size: 22, color: INK })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 240 },
      children: [new TextRun({ text: "Prototype submission, technical solution walkthrough", font: F, size: 18, italics: true, color: INK })] }),
  ],
});

/* ------------------------------------------------------- abstract onwards */
two([
  new Paragraph({
    alignment: AlignmentType.JUSTIFIED, spacing: { after: 120, line: LINE },
    children: [
      new TextRun({ text: "Abstract", font: F, size: 18, bold: true, italics: true, color: INK }),
      new TextRun({ text: ": Fraud models are validated against fraud that has already been seen, which leaves them structurally blind to attack classes no historical label covers. Scotoma is an offline adversarial testing layer that generates attacks across six payment rails, refuses to score them unless they survive a six-layer realism gate, detects them with a calibrated three-channel model, and returns whatever evaded into the next round. On a committed run the detector reaches 0.8650 precision at K and 0.7554 recall at 95 percent precision, while per-vector recall separates cleanly into attacks it sees (0.9114 to 0.9729 on four vectors) and attacks it does not (0.0099 to 0.2009 on four others), a split the architecture explains. The realism gate rejects a GaussianCopula ablation of the project's own data on five of six layers. The graph channel disabled itself on measured lift. Blind-holdout evasion is reported beside active evasion and does not fall. The contribution is the loop and the blind-spot map it produces, not a leaderboard position.",
        font: F, size: 18, bold: true, color: INK }),
    ],
  }),
  new Paragraph({
    alignment: AlignmentType.JUSTIFIED, spacing: { after: 160, line: LINE },
    children: [
      new TextRun({ text: "Keywords", font: F, size: 18, bold: true, italics: true, color: INK }),
      new TextRun({ text: ": payment fraud, adversarial simulation, synthetic data fidelity, cost-sensitive detection, agentic commerce, model validation", font: F, size: 18, bold: true, italics: true, color: INK }),
    ],
  }),

  H1("I", "Introduction"),
  body("A fraud model is validated against the fraud that has already been seen. That is a sound way to measure yesterday and a poor way to anticipate tomorrow. A detector can hold excellent aggregate metrics while being structurally blind to an attack class that no historical label covers, and the blind spot is usually discovered only when it is exploited at volume.", { noIndent: true }),
  body("Two conditions sharpen this. Attack surface is expanding across rails that share entities but not visibility, so a campaign distributed across card, instant-payment and agentic channels can appear unremarkable to any single participant. And agent-initiated commerce has introduced payment mandates, attestations and cart hashes, for which no historical corpus exists at all."),
  mixed([["The economics also argue against blunt defences. Global card fraud losses reached 33.41 billion dollars in 2024 on 51.92 trillion dollars of volume, while false declines cost merchants 50.7 billion dollars across four markets in 2022. The larger number sits with customers refused wrongly, which is why this system reports cost per 100,000 events rather than a catch rate, and why nothing below the top decision band blocks autonomously.", {}]]),
  mixed([["The claim defended here is deliberately narrow. ", {}],
         ["Scotoma measures and shrinks a detector's blind spots. It does not claim to make anyone monotonically safer.", { i: true }],
         [" Every figure below is reported against that sentence, and where a quantity was not measured the text says so.", {}]]),

  H1("II", "System Architecture"),
  mixed([["Four stages run in sequence, all offline, closed by a loop controller. The organising rule is that ", {}],
         ["all heavy cognition is offline and the live rail is arithmetic", { i: true }],
         [". Language-model reasoning, parameter search, graph simulation, fidelity testing and retraining are batch work. The inline path holds a compiled model, a probabilistic-structure lookup and a hash comparison.", {}]], { noIndent: true }),
  body("The ordering carries the argument. If generated traffic went straight to the detector, the loop would converge on attacks that are easy to generate rather than attacks that are realistic, and every downstream metric would describe an artefact. Placing the gate before the detector means a batch must first look like plausible payment traffic and only then gets to be difficult."),
]);

one([ img("fig1_architecture.png", 640, 325), figCap("The closed loop. The gate sits between generation and scoring, so unrealistic traffic never reaches the detector.") ]);

one([
  ...tabCap("Implemented Components"),
  tbl([3400, 4100, 2560], [
    ["Component", "Implementation", "Status"],
    ["Attack registry", "32 machine-readable vectors, 6 rails", "built"],
    ["Simulator", "8 injector modules, 12 injector classes", "built"],
    ["Fidelity gate", "6 layers, 1 rotated into shadow per round", "built"],
    ["Channel A", "gradient boosting, 151 features", "built"],
    ["Channel B", "neighbour aggregation over the entity graph", "built, auto-disabled"],
    ["Channel C", "isolation forest on legitimate traffic", "built"],
    ["Loop controller", "6-round default, hardest-campaign retention", "built"],
    ["Party-scope projection", "issuer, acquirer and network masks", "built"],
    ["Red agent", "LLM proposals, offline evolutionary fallback", "built, offline in this run"],
  ], ["l", "l", "l"]),
]);

two([
  H1("III", "Attack Coverage"),
  body("The registry holds 32 vectors across six rails: card-not-present (19), UPI (12), ACH (9), SEPA Instant (8), card-present (6) and agentic (5). Vectors appear on more than one rail where the attack genuinely crosses rails.", { noIndent: true }),
  mixed([["Twelve of the 32 have live simulators, which is ", {}], ["37.5 percent coverage", { b: true }],
         [". The remaining twenty are registry entries with schemas and no generator behind them. That distinction is enforced in the product rather than described in prose: the coverage screen greys the undelivered rows and prints the ratio.", {}]]),
]);

one([
  ...tabCap("The Twelve Vectors With Live Simulators"),
  tbl([1100, 4400, 2900, 1660], [
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
]);

two([
  body("Four of the twelve are agentic. That concentration is deliberate and it carries the heaviest honesty burden: no public transaction corpus contains a payment mandate, an attestation or a cart hash, because the standards defining them are still arriving. Those vectors are generated from protocol structure rather than fitted to observed data.", { noIndent: true }),

  H1("IV", "Simulation Fidelity"),
  mixed([["Generated attack traffic is worthless as a test if it does not resemble payment traffic, and the usual failure is subtle: marginal distributions match while sequence structure inside an entity is destroyed. This is a measured property of a class of generators. A 2026 benchmark shows ", {}],
         ["row-independent generators degrade behavioural fraud signal 24 to 100 times while train-synthetic-test-real AUROC stays near baseline", { i: true }],
         [", so the standard quality check passes while the property a fraud model needs has been destroyed. The gate therefore checks six properties, and a batch passes only if every active layer passes.", {}]], { noIndent: true }),
  body("One of the marginal, joint and adversarial layers is rotated into shadow each round. A shadow layer is evaluated and reported but not enforced, so a generator cannot be tuned against a fixed set of six checks."),
]);

one([
  ...tabCap("The Six-Layer Gate Against a GaussianCopula Ablation"),
  tbl([2100, 3100, 1600, 1620, 1640], [
    ["Layer", "Statistic", "Threshold", "Scotoma", "Ablation"],
    ["Marginal", "worst KS", "0.10", "0.0117", "0.1970"],
    ["Joint", "pairwise corr. difference", "0.15", "0.0200", "0.0442"],
    ["Joint", "max Cramer V delta", "reported", "0.0028", "0.5444"],
    ["Behavioural", "composite ratio", "10.0", "1.0389", "20.0"],
    ["Behavioural", "lag-1 IET autocorrelation", "positive", "0.0843", "-0.1192"],
    ["Adversarial", "discriminator AUC", "0.65", "0.5176", "0.9599"],
    ["Privacy", "membership inference AUC", "0.55", "0.5009", "reported"],
    ["Utility", "TSTR ratio", "0.90", "0.9998", "reported"],
  ], ["l", "l", "r", "r", "r"]),
]);

two([
  mixed([["The ablation is the load-bearing evidence, because it is a test the gate could have failed and did not. A GaussianCopula synthesiser trained on the same population ", {}],
         ["fails five of the six layers", { b: true }],
         [". Its discriminator AUC of 0.9599 means a classifier separates its output from real traffic almost perfectly, and its lag-1 inter-event-time autocorrelation is negative at -0.1192 against 0.0847 for the reference. Row-independent generation does not merely weaken within-entity timing structure, it inverts it. The gate rejects that batch.", {}]], { noIndent: true }),

  H2("A", "Checking the gate against an external corpus"),
  mixed([["A gate whose reference is the system's own output is marking its own homework. The reference was therefore replaced with a partition of the Sparkov corpus, which this project did not generate, and three rounds were run. Every round was rejected, at composite 13.20 to 13.33 against a threshold of 10.0. That result is reported here rather than buried, and so is the reason it is ", {}],
         ["not yet a fidelity verdict", { b: true }],
         [". The Sparkov partition carries 939 cards at 2.6985 events per card per day; the Scotoma frame carries 34,152 cards at 0.2966. Each external card is roughly nine times busier, so comparing inter-event-time spread across the two measures the density gap first and realism second. The scale-free autocorrelation ratio sits at 1.40, close to parity.", {}]], { noIndent: true }),

  H1("V", "Detection"),
  body("Three channels, of which two ship. Channel A is a gradient-boosted decision tree over 151 features. Channel C is an isolation forest fitted only on legitimate traffic, which is what makes an anomaly score mean anything: a model shown fraud during fitting learns that fraud is ordinary. Channel B aggregates neighbour features over the entity graph and is gated on measured lift.", { noIndent: true }),
  body("The feature set is dominated by point-in-time velocity: seven entity keys by five windows by four aggregations. Every window excludes the current row. That single decision is the difference between a velocity feature and a label leak, and it is asserted in the test suite rather than assumed. Training respects a 30-day label embargo, so the model sees only labels that would have been available at decision time."),

  H2("A", "Calibration and the operating point"),
  body("Scores become decisions through an Elkan cost-sensitive threshold derived from a 25.00 chargeback fee, a 0.22 merchant margin, a 0.32 attrition probability and an 1,800.00 customer lifetime value. A threshold derived from miscalibrated posteriors is wrong, and every cost figure derived from it is wrong with it.", { noIndent: true }),
]);

one([ img("fig4_calibration.png", 620, 264),
  figCap("Left: reliability on the simulated corpus, bins with at least 30 events, Brier improving from 0.003029 to 0.001320 under Platt scaling. Right: the calibrator choice measured on ULB, the one genuinely observed corpus used in this work.") ]);

two([
  mixed([["Platt scaling was chosen over isotonic regression, and the choice was tested. On ULB, at a real 0.173 percent base rate, isotonic costs ", {}],
         ["0.0251 PR-AUC", { b: true }],
         [" because it is not monotonic and does not preserve ranking, it is worse on mass-weighted calibration error (0.000181 against 0.000172), and it pins 2.56 percent of scores at exactly zero or one. A posterior of exactly one asserts certainty, and a cost-sensitive threshold cannot price certainty.", {}]], { noIndent: true }),
  body("Decisions fall into four bands: approve below 0.30, step up to 3-D Secure to 0.70, hold to 0.90, and decline with a SAR queue entry above 0.90. Nothing below 0.90 blocks autonomously, so the consequential action always has a human in the loop. Given the false-decline economics, autonomous blocking destroys more value than it saves."),
  body("Every alert carries reason codes. TreeSHAP runs on the production model rather than a surrogate, and the top contributing features map through a fixed dictionary to a fixed sentence. A surrogate would explain a different model from the one that made the decision, which is not an explanation."),

  H1("VI", "Evaluation"),
  body("What follows is measured on run 2026-08-31-final: 180 simulated days, three loop rounds, seed 42.", { noIndent: true }),
  mixed([["ROC-AUC is deliberately not the headline, and there is a published figure that shows why. On the ULB dataset the same model scores ", {}],
         ["0.957 ROC-AUC against 0.708 PR-AUC", { b: true }],
         [". At fraud prevalence the two metrics tell different stories, and only one moves when the alert queue becomes unusable.", {}]]),
]);

one([
  ...tabCap("Headline Detection Metrics"),
  tbl([4000, 2400, 3660], [
    ["Metric", "Value", "Reading"],
    ["Precision at K", "0.8650", "alert queue quality"],
    ["Recall at 95 percent precision", "0.7554", "recall at a usable operating point"],
    ["False positive to true positive", "0.0210", "review burden per catch"],
    ["False positive rate, legitimate", "0.000171", "round 0"],
    ["Brier, uncalibrated", "0.003029", "before Platt"],
    ["Brier, calibrated", "0.001320", "after Platt"],
    ["Model scoring p50", "0.0255 ms", "measured, ONNX plus Platt"],
    ["Model scoring p99", "0.0939 ms", "measured, ONNX plus Platt"],
  ], ["l", "r", "l"]),
]);

two([
  mixed([["Recall of 0.7554 at 95 percent precision is the number an operations team would care about most: roughly three quarters of fraud caught at a precision where the queue remains workable. The FP to TP ratio of 0.021 is favourable against a production benchmark of 13 false positives per true positive, with the caveat that it is measured against generated campaigns at this run's realised prevalence, not a live portfolio mix. The direction is meaningful; the absolute value is not transferable.", {}]], { noIndent: true }),
  H2("A", "Per-vector recall, including where it fails"),
  body("Aggregate metrics hide exactly the failure this system exists to find.", { noIndent: true }),
]);

one([ img("fig2_per_vector_recall.png", 560, 297),
  figCap("Recall by vector on the active campaign. V07 is the blind holdout vector and never enters any training pool.") ]);

two([
  body("The pattern is coherent rather than random. High-volume vectors with a sharp local signature are caught: enumeration at 0.9114, BIN attack at 0.8810, APP scam at 0.9722 and UPI mandate abuse at 0.9729. These attacks concentrate activity on one entity in a short window, which is what point-in-time velocity features are shaped to see.", { noIndent: true }),
  mixed([["Four vectors fail badly and they fail for one reason. ", {}],
         ["Mule-network orchestration at 0.0099", { b: true }],
         [", agent impersonation at 0.0561, adversarial evasion at 0.1841 and prompt injection at 0.2009 all distribute activity across many entities so that no single entity exceeds a velocity threshold. Transaction-local features are structurally insufficient against attacks whose signal lives in relationships between entities rather than within any one of them.", {}]]),
  mixed([["The blind holdout is the strictest test in the run. V07 never enters any training pool, and neither does the last ten percent of cardholders by index with every device, IP and account bound only to them. Recall on V07 is ", {}],
         ["0.2050", { b: true }],
         [". A detector that had memorised the generator would score near zero; one with no generalisation problem would score near the vectors it trains on. Neither is true.", {}]]),
  H2("B", "Round progression and the circularity check"),
]);

one([
  ...tabCap("Three Rounds, With Blind-Holdout Evasion Co-Reported"),
  tbl([1200, 1900, 1900, 1900, 1600, 1560], [
    ["Round", "PR-AUC active", "Evasion active", "Evasion blind", "FPR legit", "Cost per 100k"],
    ["0", "0.5036", "0.8644", "0.8447", "0.000171", "81,080"],
    ["1", "0.7972", "1.0000", "1.0000", "0.000000", "834,633"],
    ["2", "0.2754", "0.9264", "0.8012", "0.000230", "94,102"],
  ], ["l", "r", "r", "r", "r", "r"]),
]);

two([
  mixed([["The blind column answers the circularity objection, and it is reported because it is unflattering. Evasion on the blind holdout stays between ", {}],
         ["0.8012 and 1.0000", { b: true }],
         [" across all three rounds: the loop is not driving it down. A system reporting only the active campaign could show a curve bending the right way while the holdout never moved. The fidelity composite is co-reported at 1.0389, 1.0439 and 1.0341, so all three batches were realistic by the gate's own measure.", {}]], { noIndent: true }),
  body("Active PR-AUC moves from 0.5036 to 0.7972 and then falls to 0.2754. The loop is adversarial, so this is expected rather than unstable: the controller feeds the hardest surviving campaigns into the next training pool and conditions the next proposals on what evaded. Round 2 is a harder examination than round 0. It does mean a single round-over-round series is not by itself evidence of improvement, and this paper does not present it as such."),
  mixed([["Round 1 is the instructive failure. PR-AUC is high at 0.7972 while evasion is ", {}], ["1.0000", { b: true }],
         [" and the false positive rate is zero. The model ranked that round's campaigns well and still placed its threshold so that nothing was actioned, and cost per 100,000 events rose to 834,633 against 81,080 in round 0. Ranking quality and operating point are different properties, and a system reporting only PR-AUC would have called round 1 its best result.", {}]]),
  H2("C", "Visibility asymmetry"),
  body("The same detector was refitted under three visibility masks, each seeing only the fields one party would hold. This operationalises a known asymmetry rather than discovering it.", { noIndent: true }),
  img("fig3_party_scope.png", 300, 196),
  figCap("Per-vector recall under issuer, acquirer and network visibility. Blank cells are vectors the party cannot observe at all."),
  body("UPI mandate abuse reaches 0.7354 at network scope and is not observable at issuer or acquirer scope. BIN attack is visible to all three but weakly, at 0.1456 for the network and 0.0002 for the issuer. Several of these attacks are therefore not detectable by any single institution regardless of model quality, which is a statement about data access rather than modelling."),
  H2("D", "The graph channel and its measured negative result"),
  mixed([["Channel B is built and it disabled itself. The configured bar is a 0.03 PR-AUC lift; the measured lift was ", {}],
         ["-0.2092", { b: true }],
         [", so the channel switched off automatically. It was then scoped against IBM AML HI-Small, a corpus with labelled laundering motifs that this project did not generate: 515,080 accounts and 5,078,345 edges. Laundering sources carry 1.42 times the out-degree of legitimate ones, so aggregate structure genuinely differs, but a degree and reciprocity baseline separates individual edges at only ", {}],
         ["0.0074 PR-AUC lift", { b: true }],
         [" over the base rate, four times short of the same bar.", {}]], { noIndent: true }),
  body("This is consistent with the published finding that boosted trees on neighbour-aggregated features beat the best graph neural network by 2.0 points of AUROC and 12.9 percent of AUPRC on a graph anomaly benchmark, which is why the built channel aggregates neighbour features rather than training a deep graph model. Publishing the number is more useful than shipping a decorative graph model with an unmeasured lift."),
  H2("E", "External corpora"),
  body("Three public corpora were used and their provenance differs in a way that matters for how each result should be read.", { noIndent: true }),
]);

one([
  ...tabCap("External Corpora and Their Provenance"),
  tbl([3000, 2200, 2200, 2660], [
    ["Corpus", "Rows", "Provenance", "Role"],
    ["Sparkov", "1,852,394", "generated", "external detector fit, gate reference"],
    ["ULB creditcardfraud", "284,807", "observed", "calibrator selection"],
    ["IBM AML HI-Small", "5,078,345", "generated", "graph channel scoping"],
  ], ["l", "r", "l", "l"]),
]);

two([
  body("Only ULB is observed transaction data. Sparkov is described by its publisher as simulated transactions produced by the Sparkov generator, and IBM AML is a generated benchmark. On the Sparkov partitions a detector fitted on 778,005 rows reaches PR-AUC 0.2898 against a 0.60 percent base rate, roughly a 48-fold lift, and transfers to a strictly later holdout at PR-AUC 0.0653. That fall across a six to twelve month gap is genuine temporal drift, and it is the baseline any train-on-generated claim must be measured against.", { noIndent: true }),
  body("The value of an external corpus here is not that it is real. It is that this project did not produce it, which is what breaks the circularity in a fidelity comparison."),

  H1("VII", "Novelty and Deployment"),
  body("The individual components are established. The contribution is the arrangement: a realism gate that can reject the project's own output, positioned between generation and detection, with survivors driving the next round and a visibility mask on the measurement.", { noIndent: true }),
  mixed([["Two pieces are concrete rather than architectural. The cart-hash comparison turns prompt injection into a decidable question: an agent-initiated purchase carries a hash of the cart at intent and again at settlement, and ", {}],
         ["if the two differ, the cart changed between the user agreeing and the payment completing", { b: true }],
         [". That is a deterministic boolean costing a hash comparison inline. Party-scope projection is the second, quantifying which vectors an issuer simply cannot see.", {}]]),
  body("Scotoma is not a replacement for a mature fraud decisioning system such as Mastercard Decision Intelligence, and is not positioned as one. Those systems are trained on network-scale labelled history this project does not have. Scotoma is a continuous adversarial testing layer that would sit beside such a system, consume its model artefacts, and report where they are blind: model validation before promotion, blind-spot discovery, regression tests built from campaigns that once evaded, and testing of new payment paradigms before enough live fraud exists to train on."),
]);

one([
  ...tabCap("Workload Separation"),
  tbl([2900, 2600, 4560], [
    ["Workload", "Where it runs", "Constraint"],
    ["Campaign generation and gate", "offline batch", "minutes per round, no latency budget"],
    ["Detector fitting and refits", "offline batch", "55 s per fit measured on the external corpus"],
    ["Feature assembly", "streaming or online store", "not measured in this run"],
    ["Model scoring", "inline, ONNX", "0.0255 ms p50, 0.0939 ms p99 measured"],
    ["Threshold and ladder", "inline", "four arithmetic operations"],
    ["Graph channel", "offline batch", "30 s to 5 min lag in a production shape"],
  ], ["l", "l", "l"]),
]);

two([
  mixed([["Scoring latency was measured over 10,000 iterations with 500 warmup for the compiled model plus Platt calibration. The figure excludes feature assembly and the feature-store lookup, which could not be measured because the Redis instance was unreachable. The 50 ms inline budget and the 5 ms feature-lookup target are therefore ", {}],
         ["design constraints, not measured results", { b: true }],
         [". The measurement was taken on a single Intel laptop core running Python 3.11, which is not production hardware. A complete inline latency claim requires the feature path to be measured on representative infrastructure, and this paper does not make one.", {}]], { noIndent: true }),
  body("A production deployment would also need model rollback and artefact versioning beyond file outputs, drift monitoring against live traffic rather than against the loop's own campaigns, verified feature availability at scoring time, and an operations review of whether the reason codes are actionable, which is a different standard from being technically correct."),

  H1("VIII", "Limitations"),
  body("These are stated because a reviewer will find them, and because the boundary between what was measured and what was assumed is the most useful part of this paper.", { noIndent: true }),
  bullet("The loop trains and evaluates on traffic this project generates. External corpora anchor and cross-check it but do not replace it, and the agentic vectors have no external anchor at all."),
  bullet("Coverage is 12 of 32 vectors. The other twenty are documented registry entries with no generator behind them and are not claimed as tested."),
  bullet("The external-reference gate run rejected all three rounds, and the population density gap means that result cannot yet be read as a fidelity verdict in either direction."),
  bullet("Inline latency is measured for model scoring only. The feature-store path is unmeasured, so no end-to-end authorisation latency is claimed."),
  bullet("The blind holdout is one attack family and one entity cohort built with divergent population parameters. It is not an independently generated holdout, and the strength of the circularity defence is bounded by that."),
  bullet("Round-over-round PR-AUC is not evidence of improvement on its own, because campaign difficulty rises each round. A fixed benchmark scored every round would be required to separate the two effects, and it is not built."),
  bullet("Three rounds were run in the reported configuration; the default is six. The label embargo, cost constants and ladder bands are configuration and have not been tuned against an institution's loss experience."),
  body("Production validation would require a shadow deployment against live traffic with a measured feature path, a fixed external benchmark scored every round, and a density-normalised fidelity reference. None are present here."),

  H1("IX", "Conclusion"),
  body("Scotoma generates attacks across six payment rails, refuses to score them unless they survive a gate that provably rejects a weaker generator, detects them with a calibrated three-channel model, and reports where it fails per vector. It catches high-velocity attacks at 0.9114 to 0.9729 recall and fails on distributed low-velocity attacks at 0.0099 to 0.2009, for a reason the architecture explains. It measures its own graph channel and switches it off. It quantifies what a single institution cannot see.", { noIndent: true }),
  body("The most valuable output is not the aggregate score. It is the list of attacks the detector cannot see, and the evidence for why."),

  H1("", "References"),
  ...[
    "C. Elkan, \"The foundations of cost-sensitive learning,\" in Proc. IJCAI, 2001.",
    "E. Altman et al., \"Realistic synthetic financial transactions for anti-money laundering models,\" in Proc. NeurIPS Datasets and Benchmarks, 2023.",
    "A. Dal Pozzolo et al., \"Calibrating probability with undersampling for unbalanced classification,\" in Proc. IEEE SSCI, 2015.",
    "B. Harris, \"Sparkov data generation,\" Kaggle dataset kartik2112/fraud-detection, simulated credit card transactions.",
    "S. Lundberg and S. Lee, \"A unified approach to interpreting model predictions,\" in Proc. NeurIPS, 2017.",
    "J. Tang et al., \"GADBench: revisiting and benchmarking supervised graph anomaly detection,\" in Proc. NeurIPS, 2023.",
  ].map((t, i) => new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    spacing: { after: 40, line: 200 },
    indent: { left: 260, hanging: 260 },
    children: [new TextRun({ text: `[${i + 1}] ${t}`, font: F, size: SMALL, color: INK })],
  })),
]);

const doc = new Document({
  creator: "Scotoma Project Team",
  lastModifiedBy: "Scotoma Project Team",
  title: "Scotoma: A Closed Adversarial Loop for Measuring Fraud-Detection Blind Spots",
  description: "Prototype submission, technical solution walkthrough",
  styles: { default: { document: { run: { font: F, size: BODY, color: INK },
                                   paragraph: { spacing: { line: LINE } } } } },
  sections,
});

Packer.toBuffer(doc).then(buf => {
  const out = path.join(ROOT, "SCOTOMA_Solution_Walkthrough.docx");
  fs.writeFileSync(out, buf);
  console.log("wrote", out, buf.length, "bytes");
});
