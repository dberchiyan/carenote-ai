# Shared commands for CareNote AI. Run `make help` for a list.
.DEFAULT_GOAL := help
SHELL := /bin/bash

API := cd api &&
WEB := cd web &&

.PHONY: help
help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

.PHONY: install
install: ## Install backend and frontend dependencies
	$(API) uv sync --locked
	$(WEB) npm ci

# --- Docker Compose ---------------------------------------------------------

.PHONY: up
up: db-tunnel ## Build and start api, web, fhir (database is external); wait until healthy
	docker compose up -d --build
	@$(MAKE) --no-print-directory wait

.PHONY: down
down: ## Stop the stack
	docker compose down

.PHONY: reset
reset: ## Stop the stack and delete the audio volume (the database is external)
	docker compose down -v

.PHONY: wait
wait: ## Wait until api, web and fhir answer
	@./scripts/wait-for.sh http://localhost:$${API_PORT:-8000}/health/ready api 60
	@./scripts/wait-for.sh http://localhost:$${WEB_PORT:-3000}/healthz web 60
	@./scripts/wait-for.sh http://localhost:$${FHIR_PORT:-8090}/fhir/metadata fhir 180

# --- Quality ----------------------------------------------------------------

.PHONY: check
check: check-api check-web types-check ## Run all linters, type checkers and unit tests

# The database lives on osdb-prod and is reached through an SSH tunnel on 127.0.0.1:5433.
# Containers reach the tunnel as host.docker.internal:5433. CI uses its own Postgres service.
DB_SSH_HOST ?= osdb-prod
DB_PORT ?= 5433

.PHONY: db-tunnel
db-tunnel: ## Open the SSH tunnel to the external PostgreSQL (idempotent)
	@nc -z 127.0.0.1 $(DB_PORT) 2>/dev/null && echo "db tunnel already open on :$(DB_PORT)" || \
		(ssh -f -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -L $(DB_PORT):127.0.0.1:$(DB_PORT) $(DB_SSH_HOST) \
		&& echo "db tunnel opened on :$(DB_PORT)")

.PHONY: db-tunnel-close
db-tunnel-close: ## Close the SSH tunnel
	@pkill -f "ssh -f -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -L $(DB_PORT):127.0.0.1:$(DB_PORT)" && echo "db tunnel closed" || echo "no tunnel"

.PHONY: check-api
check-api: db-tunnel check-api-ci ## ruff, mypy (strict), pytest (opens the db tunnel first)

.PHONY: check-api-ci
check-api-ci: # backend checks without touching the tunnel (CI has a Postgres service)
	$(API) uv run ruff format --check .
	$(API) uv run ruff check .
	$(API) uv run mypy
	$(API) uv run pytest -n auto --cov=carenote --cov-report=term:skip-covered --cov-fail-under=85

.PHONY: check-web
check-web: ## ESLint, Prettier, tsc, Vitest, production build
	$(WEB) npm run lint
	$(WEB) npm run format:check
	$(WEB) npm run typecheck
	$(WEB) npm test
	$(WEB) npm run build

.PHONY: fmt
fmt: ## Auto-format and auto-fix both projects
	$(API) uv run ruff format . && uv run ruff check --fix .
	$(WEB) npm run format

.PHONY: types
types: ## Regenerate web TypeScript types from the FastAPI OpenAPI schema
	$(API) uv run python -m carenote.openapi > ../web/openapi.json
	$(WEB) npm run gen:api

.PHONY: types-check
types-check: ## Fail if generated API types are out of date
	@tmp=$$(mktemp -d); \
	(cd api && uv run python -m carenote.openapi) > $$tmp/openapi.json; \
	(cd web && npx openapi-typescript $$tmp/openapi.json -o $$tmp/schema.d.ts >/dev/null 2>&1); \
	if diff -q $$tmp/openapi.json web/openapi.json >/dev/null && diff -q $$tmp/schema.d.ts web/src/shared/api/schema.d.ts >/dev/null; \
	then echo "API types up to date"; \
	else echo "API types are stale: run 'make types'"; rm -rf $$tmp; exit 1; fi; \
	rm -rf $$tmp

.PHONY: test-integration
test-integration: ## Integration tests against the running stack (HAPI FHIR $validate)
	$(API) uv run pytest -m integration

.PHONY: e2e
e2e: up ## Run Playwright end-to-end tests against Docker Compose, then restore the demo history
	$(WEB) npx playwright test; status=$$?; $(MAKE) --no-print-directory seed-history; exit $$status

# --- Data and evals ---------------------------------------------------------

.PHONY: migrate
migrate: ## Apply database migrations (the api container does this at start too)
	docker compose exec api alembic upgrade head

.PHONY: seed
seed: ## Seed demo users and synthetic patients (idempotent)
	docker compose exec api python -m carenote.seed

.PHONY: seed-history
seed-history: ## Replace all notes with a week of synthetic ward history (dashboards, trends)
	docker compose exec api python -m carenote.seed --history

.PHONY: dataset
dataset: ## Regenerate the synthetic dictation dataset and the held-out set (deterministic)
	$(API) uv run python -m evals.generate
	$(API) uv run python -m evals.holdout

.PHONY: dataset-audio
dataset-audio: ## Regenerate the dataset with TTS audio (TTS=macos|openai)
	$(API) uv run python -m evals.generate --audio --tts $${TTS:-macos}

.PHONY: eval
eval: ## Run the eval suite (PROVIDER=, MODE=text|audio, COMPARE="fake anthropic", DATASET=cases|cases_holdout, EVAL_BUDGET_USD=)
	$(API) uv run python -m evals.run --mode $${MODE:-text} --dataset $${DATASET:-cases} \
		$$( [ -n "$$COMPARE" ] && echo "--compare $$COMPARE" || echo "--provider $${PROVIDER:-fake}" ) \
		$$( [ "$${MODE:-text}" = audio ] && echo "--transcriber $${TRANSCRIBER:-fake}" ) \
		$$( [ -n "$$EVAL_BUDGET_USD" ] && echo "--max-cost-usd $$EVAL_BUDGET_USD" )

.PHONY: eval-gate
eval-gate: ## Fail when REPORT regresses >2 p.p. against BASELINE (json reports), or costs more than BUDGET
	$(API) uv run python -m evals.gate --report $(REPORT) --baseline $(BASELINE) \
		--max-regression $${MAX_REGRESSION:-0.02} $$( [ -n "$(BUDGET)" ] && echo "--max-cost-usd $(BUDGET)" )

.PHONY: banner
banner: ## Re-render docs/banner.png from the running stack (three real screens)
	cd web && node scripts/banner.mjs ../docs/banner.png

.PHONY: paraphrase
paraphrase: ## Paraphrase the dataset with Claude (needs CARENOTE_ANTHROPIC_API_KEY)
	$(API) uv run python -m evals.paraphrase
