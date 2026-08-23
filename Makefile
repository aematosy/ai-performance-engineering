SHELL := /bin/bash
.DEFAULT_GOAL := help

PYTHON := poetry run python
SCENARIO ?= create-post-demo
PLAN ?= tests/plans/$(SCENARIO)/test-plan.yaml
JMX ?= tests/generated/$(SCENARIO).jmx
APPROVED_BY ?=

.PHONY: help validate smoke review-plan validate-plan approve-plan generate-jmx validate-jmx run-demo status observability-up observability-down clean-runtime

help:
	@echo "AI-Assisted Performance Engineering"
	@echo ""
	@echo "make validate"
	@echo "make smoke"
	@echo "make review-plan"
	@echo "make validate-plan"
	@echo 'make approve-plan APPROVED_BY="Nombre Apellido"'
	@echo "make generate-jmx"
	@echo "make validate-jmx"
	@echo "make run-demo"
	@echo "make status"
	@echo "make observability-up"
	@echo "make observability-down"
	@echo "make clean-runtime"

validate:
	$(PYTHON) scripts/config_loader.py
	$(PYTHON) scripts/validate_environment.py

smoke:
	$(PYTHON) scripts/demo_smoke_test.py --plan "$(PLAN)" --jmx "$(JMX)"

review-plan:
	$(PYTHON) scripts/review_test_plan.py --plan "$(PLAN)" --strict

validate-plan:
	$(PYTHON) scripts/validate_test_plan.py --plan "$(PLAN)"

approve-plan:
	@if [ -z "$(APPROVED_BY)" ]; then echo 'ERROR: use make approve-plan APPROVED_BY="Nombre Apellido"'; exit 2; fi
	$(PYTHON) scripts/approve_test_plan.py --plan "$(PLAN)" --approved-by "$(APPROVED_BY)"

generate-jmx:
	$(PYTHON) scripts/generate_jmx_from_plan.py --plan "$(PLAN)" --output "$(JMX)"

validate-jmx:
	$(PYTHON) scripts/validate_jmx_artifact.py --plan "$(PLAN)" --jmx "$(JMX)"

run-demo: validate-jmx
	$(PYTHON) scripts/run_approved_plan.py --plan "$(PLAN)" --jmx "$(JMX)" --preflight
	@read -r -p "Type RUN to authorize exactly the preflight parameters: " answer; \
	if [ "$$answer" != "RUN" ]; then echo "Execution cancelled."; exit 2; fi
	$(PYTHON) scripts/validate_environment.py
	$(PYTHON) scripts/run_approved_plan.py --plan "$(PLAN)" --jmx "$(JMX)" --authorized

status:
	@echo "===== DOCKER ====="
	@docker compose ps || true
	@echo ""
	@echo "===== LATEST RESULT ====="
	@latest=$$(ls -dt results/*/ 2>/dev/null | head -1); if [ -n "$$latest" ]; then echo "$$latest"; else echo "No results"; fi
	@echo ""
	@echo "===== PLAN ====="
	@$(PYTHON) scripts/validate_test_plan.py --plan "$(PLAN)" || true
	@echo ""
	@echo "===== JMX PROVENANCE ====="
	@$(PYTHON) scripts/validate_jmx_artifact.py --plan "$(PLAN)" --jmx "$(JMX)" || true

observability-up:
	docker compose up -d
	@curl -fsS http://localhost:9090/-/ready
	@echo ""
	@curl -fsS http://localhost:3000/api/health
	@echo ""

observability-down:
	docker compose down

clean-runtime:
	@find . -name ".DS_Store" -delete
	@find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	@find . -type f -name "*.pyc" -delete
	@find . -type f \( -name "*.tmp" -o -name "*.bak" \) -delete
	@echo "Runtime caches and temporary files removed."
