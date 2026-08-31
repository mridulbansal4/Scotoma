"""Prepare Sparkov partitions and fit Channel A on them.

    python scripts/sparkov_pipeline.py prepare --raw data/real/raw
    python scripts/sparkov_pipeline.py train
    python scripts/sparkov_pipeline.py tstr

prepare reads fraudTrain.csv / fraudTest.csv and writes calib/floor/blind parquet.
train fits Channel A on calib and exports the weights bundle.
tstr scores the calib-trained model on blind, which is the transfer number.
"""

import argparse
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.realdata import sparkov, train as trainer  # noqa: E402
from backend.runtime.config import load_config  # noqa: E402

REAL_DIR = REPO_ROOT / "data" / "real"
WEIGHTS_DIR = REPO_ROOT / "weights"
SHAP_BACKGROUND_ROWS = 2000


def cmd_prepare(args: argparse.Namespace) -> int:
    raw = Path(args.raw)
    train_csv, test_csv = raw / "fraudTrain.csv", raw / "fraudTest.csv"
    for path in (train_csv, test_csv):
        if not path.exists():
            print(f"missing {path}", file=sys.stderr)
            return 2

    report = sparkov.partition(train_csv, test_csv, REAL_DIR, calib_fraction=args.calib_fraction)
    (REAL_DIR / "partition_report.json").write_text(
        json.dumps(report.as_payload(), indent=2), encoding="utf-8"
    )
    for name in sparkov.PARTITIONS:
        print(
            f"{name:6s} rows={report.rows[name]:>9,} "
            f"frauds={report.frauds[name]:>7,} "
            f"prevalence={report.prevalence(name):.5f} "
            f"span={report.boundaries[name][0]} .. {report.boundaries[name][1]}"
        )
    print("partition-overlap assertion passed")
    return 0


def cmd_train(args: argparse.Namespace) -> int:
    config = load_config()
    calib = sparkov.load_partition(REAL_DIR, sparkov.CALIB)
    if args.limit:
        calib = calib.head(args.limit)

    result, fit = trainer.train(calib, config, negative_ratio=args.negative_ratio)
    background = trainer.build_features(calib.head(SHAP_BACKGROUND_ROWS), include_absent=False)
    written = trainer.export_weights(result, fit, WEIGHTS_DIR, background=background)

    for key in (
        "rows_total",
        "rows_fit",
        "prevalence_source",
        "prevalence_fit",
        "prevalence_calibration",
        "pr_auc",
        "roc_auc",
        "brier_calibrated",
        "brier_uncalibrated",
    ):
        print(f"{key:24s} {fit.metrics[key]}")
    print("wrote " + ", ".join(written))
    return 0


def cmd_tstr(args: argparse.Namespace) -> int:
    config = load_config()
    calib = sparkov.load_partition(REAL_DIR, sparkov.CALIB)
    blind = sparkov.load_partition(REAL_DIR, sparkov.BLIND)
    if args.limit:
        calib, blind = calib.head(args.limit), blind.head(args.limit)

    result, fit = trainer.train(calib, config, negative_ratio=args.negative_ratio)
    scores = trainer.evaluate(result.model, blind)
    print(f"real-trained baseline on blind: pr_auc={scores['pr_auc']} rows={scores['rows']:,}")
    (WEIGHTS_DIR / "tstr_baseline.json").write_text(
        json.dumps({"baseline_real_to_real": scores, "calib_fit": fit.metrics}, indent=2),
        encoding="utf-8",
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser("prepare", help="temporal split into calib/floor/blind")
    prepare.add_argument("--raw", default=str(REAL_DIR / "raw"))
    prepare.add_argument("--calib-fraction", type=float, default=0.60, dest="calib_fraction")
    prepare.set_defaults(func=cmd_prepare)

    train_cmd = sub.add_parser("train", help="fit Channel A on calib and export weights")
    train_cmd.add_argument("--limit", type=int, default=0)
    train_cmd.add_argument("--negative-ratio", type=float, default=10.0, dest="negative_ratio")
    train_cmd.set_defaults(func=cmd_train)

    tstr = sub.add_parser("tstr", help="score the calib-trained model on blind")
    tstr.add_argument("--limit", type=int, default=0)
    tstr.add_argument("--negative-ratio", type=float, default=10.0, dest="negative_ratio")
    tstr.set_defaults(func=cmd_tstr)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
