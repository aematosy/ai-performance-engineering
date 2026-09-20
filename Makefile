SHELL := /bin/bash
.DEFAULT_GOAL := help

PYTHON := poetry run python
SCENARIO ?= create-post-demo
PLAN ?= tests/plans/$(SCENARIO)/test-plan.yaml
JMX ?= tests/generated/$(SCENARIO).jmx
RUN_MANIFEST ?= work/pre-execution/make-run-demo.json
PROFILE ?= config/execution-profiles/baseline.yaml
APPROVED_BY ?=
AUTHORIZED_BY ?=

LATEST_REPORT_DIR := $(shell find reports -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null | xargs -0 ls -td 2>/dev/null | head -1)

.PHONY: help validate smoke review-plan validate-plan approve-plan generate-jmx validate-jmx \
	authorize-demo preflight-demo run-demo status observability-up observability-down \
	clean-runtime reporte_ia reporte_pdf reporte_jmeter reporte_intelligence \
	reporte_grafana reporte_prometheus reportes reportes_completos

help:
	@echo "AI-Assisted Performance Engineering"
	@echo ""
	@echo "Validation / Design"
	@echo "  make validate"
	@echo "  make smoke"
	@echo "  make review-plan"
	@echo "  make validate-plan"
	@echo '  make approve-plan APPROVED_BY="Nombre Apellido"'
	@echo "  make generate-jmx"
	@echo "  make validate-jmx"
	@echo ""
	@echo "Execution"
	@echo '  make authorize-demo AUTHORIZED_BY="Nombre Apellido"'
	@echo "  make preflight-demo"
	@echo "  make run-demo"
	@echo ""
	@echo "Reports"
	@echo "  make reporte_ia            # Reporte HTML profesional"
	@echo "  make reporte_pdf           # Reporte PDF profesional"
	@echo "  make reporte_jmeter        # Dashboard JMeter"
	@echo "  make reporte_intelligence  # Reporte Intelligence"
	@echo "  make reportes              # HTML + JMeter + Intelligence"
	@echo "  make reportes_completos    # HTML + PDF + JMeter + Intelligence"
	@echo ""
	@echo "Observability"
	@echo "  make reporte_grafana"
	@echo "  make reporte_prometheus"
	@echo ""
	@echo "Operations"
	@echo "  make status"
	@echo "  make observability-up"
	@echo "  make observability-down"
	@echo "  make clean-runtime"

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
	@if [ -z "$(APPROVED_BY)" ]; then \
		echo 'ERROR: use make approve-plan APPROVED_BY="Nombre Apellido"'; \
		exit 2; \
	fi
	$(PYTHON) scripts/approve_test_plan.py \
		--plan "$(PLAN)" \
		--approved-by "$(APPROVED_BY)"

generate-jmx:
	$(PYTHON) scripts/generate_jmx_from_plan.py \
		--plan "$(PLAN)" \
		--output "$(JMX)"

validate-jmx:
	$(PYTHON) scripts/validate_jmx_artifact.py \
		--plan "$(PLAN)" \
		--jmx "$(JMX)"

authorize-demo:
	@if [ -z "$(AUTHORIZED_BY)" ]; then \
		echo 'ERROR: use make authorize-demo AUTHORIZED_BY="Nombre Apellido"'; \
		exit 2; \
	fi
	$(PYTHON) scripts/authorize_execution.py \
		--plan "$(PLAN)" \
		--authorized-by "$(AUTHORIZED_BY)" \
		--notes "Authorized through controlled Makefile workflow."
	@echo ""
	@echo "Authorization changes the plan hash."
	@echo "Run: make generate-jmx SCENARIO=$(SCENARIO)"

preflight-demo: validate-jmx
	$(PYTHON) scripts/run_approved_plan.py \
		--plan "$(PLAN)" \
		--profile "$(PROFILE)" \
		--jmx "$(JMX)" \
		--manifest "$(RUN_MANIFEST)" \
		--preflight

run-demo: validate-jmx
	$(PYTHON) scripts/run_approved_plan.py \
		--plan "$(PLAN)" \
		--profile "$(PROFILE)" \
		--jmx "$(JMX)" \
		--manifest "$(RUN_MANIFEST)" \
		--execute

status:
	@echo "===== DOCKER ====="
	@docker compose ps || true
	@echo ""
	@echo "===== LATEST RESULT ====="
	@latest=$$(ls -dt results/*/ 2>/dev/null | head -1); \
	if [ -n "$$latest" ]; then \
		echo "$$latest"; \
	else \
		echo "No results"; \
	fi
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

reporte_ia:
	@if [ -z "$(LATEST_REPORT_DIR)" ]; then \
		echo "ERROR: No se encontraron reportes en reports/"; \
		exit 1; \
	fi
	@if [ ! -f "$(LATEST_REPORT_DIR)/executive-report.html" ]; then \
		echo "ERROR: No existe $(LATEST_REPORT_DIR)/executive-report.html"; \
		exit 1; \
	fi
	@echo "Abriendo reporte HTML: $(LATEST_REPORT_DIR)/executive-report.html"
	@open -a "Google Chrome" "$(LATEST_REPORT_DIR)/executive-report.html"

reporte_pdf:
	@if [ -z "$(LATEST_REPORT_DIR)" ]; then \
		echo "ERROR: No se encontraron reportes en reports/"; \
		exit 1; \
	fi
	@if [ ! -f "$(LATEST_REPORT_DIR)/executive-report.pdf" ]; then \
		echo "ERROR: No existe $(LATEST_REPORT_DIR)/executive-report.pdf"; \
		exit 1; \
	fi
	@echo "Abriendo PDF: $(LATEST_REPORT_DIR)/executive-report.pdf"
	@open "$(LATEST_REPORT_DIR)/executive-report.pdf"

reporte_jmeter:
	@if [ -z "$(LATEST_REPORT_DIR)" ]; then \
		echo "ERROR: No se encontraron reportes en reports/"; \
		exit 1; \
	fi
	@if [ ! -f "$(LATEST_REPORT_DIR)/jmeter/index.html" ]; then \
		echo "ERROR: No existe $(LATEST_REPORT_DIR)/jmeter/index.html"; \
		exit 1; \
	fi
	@echo "Abriendo reporte JMeter: $(LATEST_REPORT_DIR)/jmeter/index.html"
	@open -a "Google Chrome" "$(LATEST_REPORT_DIR)/jmeter/index.html"

reporte_intelligence:
	@if [ -z "$(LATEST_REPORT_DIR)" ]; then \
		echo "ERROR: No se encontraron reportes en reports/"; \
		exit 1; \
	fi
	@if [ ! -f "$(LATEST_REPORT_DIR)/intelligence-report.md" ]; then \
		echo "ERROR: No existe $(LATEST_REPORT_DIR)/intelligence-report.md"; \
		exit 1; \
	fi
	@echo "Abriendo reporte Intelligence: $(LATEST_REPORT_DIR)/intelligence-report.md"
	@open "$(LATEST_REPORT_DIR)/intelligence-report.md"

reporte_grafana:
	@echo "Abriendo dashboard de performance en Grafana..."
	@open -a "Google Chrome" \
		"http://localhost:3000/d/ai-performance-jmeter/ai-performance-engineering-jmeter-live?orgId=1&from=now-1h&to=now&timezone=browser&refresh=5s"

reporte_prometheus:
	@echo "Abriendo Prometheus..."
	@open -a "Google Chrome" "http://localhost:9090"

reportes: reporte_ia reporte_jmeter reporte_intelligence

reportes_completos: reporte_ia reporte_pdf reporte_jmeter reporte_intelligence

# LOCUST_REPORTING
.PHONY: reporte_locust

reporte_locust:
	@PYTHONPATH=src poetry run python -m performance_engineering.reporting.locust_reporting --open
