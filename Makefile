# Every target runs from the repository root. `make all` does not call Jev.
PY ?= python3

.PHONY: help install data rules jev tune-rules tune-jev cost eval narrative test lint all

help:           ## list targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/ -/'

install:        ## install the package (editable) with dev tools
	$(PY) -m pip install -e ".[dev]"

data:           ## regenerate data/ (deterministic, no API)
	$(PY) -m triage.dataset.generate

rules:          ## rules-only baseline predictions
	$(PY) -m triage.rules

tune-rules:     ## grid-search rule thresholds on the tune set
	$(PY) -m triage.rules --tune

jev:            ## Jev predictions: 150 API calls (needs TYPESAFE_API_KEY in .env)
	$(PY) -m triage.jev

tune-jev:       ## grid-search Jev combination thresholds from recorded answers (no API)
	$(PY) -m triage.jev --tune

cost:           ## Sonnet 5 cost estimate (no LLM calls)
	$(PY) -m triage.llm_estimate

eval:           ## test-split evaluation -> results/summary.md
	$(PY) -m triage.evaluate

narrative:      ## plain-language write-up -> results/evaluation_summary.md
	$(PY) -m triage.narrative

test:
	$(PY) -m pytest -q

lint:
	ruff check src tests && ruff format --check src tests

all: data rules cost eval narrative   ## everything that does not spend API credits
