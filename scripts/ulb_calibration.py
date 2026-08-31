"""Settle Platt versus isotonic on observed transactions.

    python scripts/ulb_calibration.py

Writes weights/ulb_calibration.json. ULB is the only corpus in this project that is
genuinely observed rather than generated, and its 0.172% prevalence is the regime the
calibration ruling is about.
"""

import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.realdata import ulb  # noqa: E402
from backend.runtime.config import load_config  # noqa: E402

ULB_CSV = REPO_ROOT / "data" / "real" / "ulb" / "creditcard.csv"
OUT = REPO_ROOT / "weights" / "ulb_calibration.json"


def main() -> int:
    if not ULB_CSV.exists():
        print(f"missing {ULB_CSV}", file=sys.stderr)
        return 2

    frame = ulb.read_ulb(ULB_CSV)
    payload = ulb.compare_calibrators(frame, load_config())

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"rows {payload['rows']:,}  prevalence {payload['prevalence']:.5f}")
    print(
        f"validation positives {payload['validation_positives']}  "
        f"test positives {payload['test_positives']}"
    )
    header = f"{'method':14s} {'pr_auc':>8s} {'brier':>10s} {'ECE':>10s} {'worst_bin':>10s} {'saturated':>10s}"
    print(header)
    for name in ("uncalibrated", "sigmoid", "isotonic"):
        r = payload["results"][name]
        print(
            f"{name:14s} {r['pr_auc']:>8.4f} {r['brier']:>10.6f} "
            f"{r['expected_calibration_error']:>10.6f} {r['worst_populated_bin']:>10.4f} "
            f"{r['saturated_fraction']:>10.4f}"
        )
    print(f"platt preserves ranking        : {payload['platt_preserves_ranking']}")
    print(f"pr_auc cost of isotonic        : {payload['pr_auc_cost_of_isotonic']}")
    print(f"platt better on populated bins : {payload['platt_better_on_populated_bins']}")
    print(f"isotonic scores pinned at 0 or 1: {payload['isotonic_saturated_fraction']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
