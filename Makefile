UV ?= uv
export UV_CACHE_DIR := $(CURDIR)/.cache/uv
export npm_config_cache := $(CURDIR)/.cache/npm
export PLAYWRIGHT_BROWSERS_PATH := $(CURDIR)/.cache/ms-playwright
export NEXT_TELEMETRY_DISABLED := 1
VERIFY = docker compose -p aegisops-verify -f docker-compose.yml -f docker-compose.verify.yml --profile verify

.PHONY: install check test browser build up integration migrate spike stop
install:
	$(UV) sync --frozen --all-groups
	npm ci
	npx playwright install chromium

check:
	$(UV) run --frozen --all-groups ruff check apps agents scripts
	$(UV) run --frozen --all-groups ruff format --check apps agents scripts
	$(UV) run --frozen --all-groups mypy apps/api/app agents/incident_investigator/spike.py agents/incident_investigator/free_tier.py agents/incident_investigator/groq_adapter.py scripts/verify_phase1_e2e.py
	npm run lint
	npm run format:check
	npm run typecheck

test:
	$(UV) run --frozen --all-groups pytest -q -m 'not integration'
	npm test

browser:
	npm run test:web

test-rules:
	docker compose -f docker-compose.yml -f docker-compose.observability.yml --profile observability exec prometheus promtool test rules /etc/prometheus/rules/test_api_alerts.yml

build:
	docker compose build api
	docker compose build web
	docker compose build shop-api

up:
	docker compose --profile core --profile lab up -d --wait

obs-up:
	docker compose -f docker-compose.yml -f docker-compose.observability.yml --profile core --profile lab --profile observability up -d --wait

verify-e2e:
	$(UV) run --frozen --all-groups python scripts/verify_phase1_e2e.py

migrate:
	docker compose run --rm api alembic upgrade head

integration:
	$(VERIFY) run --rm verify
	$(VERIFY) down

spike:
	$(UV) run --frozen --all-groups python -m agents.incident_investigator.spike --output artifacts/spike-supported.json
	$(UV) run --frozen --all-groups python -m agents.incident_investigator.spike --scenario conflicting --output artifacts/spike-conflicting.json

obs-down:
	docker compose -f docker-compose.yml -f docker-compose.observability.yml --profile core --profile lab --profile observability down

stop:
	docker compose --profile core --profile lab down
