#!/usr/bin/env bash
# End-to-end generation used by `make demo`. Every stage writes into runs/$RUN_ID.
set -euo pipefail

RUN_ID="${RUN_ID:-2026-08-31-final}"
PYTHON="${PYTHON:-.venv/Scripts/python.exe}"
if [ ! -x "$PYTHON" ]; then
  PYTHON=".venv/bin/python"
fi

echo "PayLoop seed_demo: run_id=$RUN_ID"
"$PYTHON" -c "from runtime.warehouse import initialise_schema, open_warehouse; initialise_schema(open_warehouse())"
"$PYTHON" -c "from loop.controller import run; print(run())"
make web-data RUN_ID="$RUN_ID"
echo "PayLoop seed_demo complete. Artefacts in runs/$RUN_ID and web/data/run."
