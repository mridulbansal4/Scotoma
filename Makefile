# Resolved lazily: `make setup` creates the interpreter this variable points at, so it
# cannot be pinned when the file is parsed.
PY = $(shell if [ -x .venv/Scripts/python.exe ]; then echo .venv/Scripts/python.exe; else echo .venv/bin/python; fi)
RUN_ID ?= 2026-08-31-final
WEB_DATA := frontend/data/run
SHELL := /bin/bash

.PHONY: setup generate inject fidelity defend scopes bench loop web-data web test report demo clean

setup:
	python -m venv .venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r requirements.txt
	$(PY) -c "from backend.runtime.warehouse import initialise_schema, open_warehouse; initialise_schema(open_warehouse())"

generate:
	$(PY) -c "from backend.loop.controller import stage; print(stage('generate'))"

inject:
	$(PY) -c "from backend.generate.injectors import INJECTORS; from backend.loop.controller import simulate_batch; print(simulate_batch({'vectors': list(INJECTORS), 'days': 180, 'intensity': 1.0}))"

fidelity:
	$(PY) -c "from backend.loop.controller import stage; print(stage('fidelity'))"

defend:
	$(PY) -c "from backend.loop.controller import stage; print(stage('defend'))"

scopes:
	$(PY) -c "from backend.loop.controller import stage; print(stage('scopes'))"

bench:
	$(PY) -c "from backend.loop.controller import stage; print(stage('bench'))"

loop:
	$(PY) -c "from backend.loop.controller import run; print(run())"

web-data:
	mkdir -p $(WEB_DATA)
	cp runs/$(RUN_ID)/* $(WEB_DATA)/
	$(PY) -c "import json, yaml, pathlib; p = pathlib.Path('$(WEB_DATA)/vectors.json'); p.write_text(json.dumps(yaml.safe_load(open('backend/registry/vectors.yaml', encoding='utf-8')), indent=2, sort_keys=True), encoding='utf-8')"
	$(PY) -c "import json, yaml, pathlib; p = pathlib.Path('$(WEB_DATA)/claims.json'); p.write_text(json.dumps(yaml.safe_load(open('backend/registry/claims.yaml', encoding='utf-8')), indent=2, sort_keys=True), encoding='utf-8')"

web:
	cd frontend && npm install && npm run build && npm start

test:
	$(PY) -m pytest -q

report:
	$(PY) -c "from backend.loop.controller import stage; print(stage('report'))"

demo: setup loop web-data web

clean:
	rm -rf data/entities.parquet data/events_legit.parquet data/events_blind.parquet data/edges.parquet data/campaigns data/payloop.db $(WEB_DATA)
