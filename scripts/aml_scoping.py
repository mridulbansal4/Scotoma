"""Scope Channel B against IBM AML HI-Small. Measure, do not train a GNN.

    python scripts/aml_scoping.py [--rows N]

Writes weights/aml_scoping.json.
"""

import argparse
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.realdata import aml  # noqa: E402
from backend.runtime.config import load_config  # noqa: E402

AML_CSV = REPO_ROOT / "data" / "real" / "aml" / "HI-Small_Trans.csv"
OUT = REPO_ROOT / "weights" / "aml_scoping.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=0, help="0 reads the whole file")
    args = parser.parse_args()

    if not AML_CSV.exists():
        print(f"missing {AML_CSV}", file=sys.stderr)
        return 2

    config = load_config()
    frame = aml.read_aml(AML_CSV, rows=args.rows or None)
    census = aml.motif_census(frame)
    scoping = aml.scope_channel_b(frame, min_lift=config.gnn_min_lift_prauc)

    payload = {"motif_census": census, "channel_b_scoping": scoping}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"accounts {census['accounts']:,}  edges {census['edges']:,}")
    for label in ("laundering", "legitimate"):
        c = census[label]
        print(
            f"{label:12s} edges={c['edges']:>9,} "
            f"mean_src_out={c['mean_src_out_degree']:>8.2f} "
            f"mean_dst_in={c['mean_dst_in_degree']:>8.2f} "
            f"reciprocated={c['reciprocated_share']:.4f} "
            f"self_loop={c['self_loop_share']:.4f}"
        )
    s = scoping
    print()
    print(f"graph-only PR-AUC   {s['graph_only_pr_auc']}  (base rate {s['test_base_rate']})")
    print(f"lift over base rate {s['lift_over_base_rate']}  bar {s['lift_bar']}")
    print(f"clears the bar      {s['clears_lift_bar']}")
    print("top features        " + ", ".join(list(s["feature_importance"])[:5]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
