# OGLOS developer commands. On Windows without make: `pwsh scripts/dev.ps1 <target>`.
COMPOSE = docker compose -f infra/docker-compose.yml --env-file .env
API = cd apps/api && uv run

.PHONY: dev dev-full down migrate migrate-new seed test test-api test-web lint lint-api lint-web e2e verify-audit

dev:            ## start postgres, redis, s3 (run the API/web apps on the host)
	$(COMPOSE) up -d postgres redis s3

dev-full:       ## start everything in containers
	$(COMPOSE) --profile full up -d --build

down:
	$(COMPOSE) --profile full down

migrate:
	$(API) alembic upgrade head

migrate-new:    ## make migrate-new name=add_x
	$(API) alembic revision -m "$(name)"

seed:
	$(API) python -m app.seed.sunrise

test: test-api test-web

test-api:
	$(API) pytest

test-web:
	pnpm -r test

lint: lint-api lint-web

lint-api:
	$(API) ruff check . && $(API) ruff format --check . && $(API) mypy app

lint-web:
	pnpm -r lint && pnpm -r typecheck && pnpm exec prettier --check .

e2e:
	pnpm --filter @oglos/e2e test

verify-audit:
	$(API) python -m app.audit.verify
