# Single-service prototype image for Render: builds both web apps, serves them from the API.
FROM node:22.12-alpine AS web
WORKDIR /repo
RUN npm install -g pnpm@10.34.9  # not corepack: old Node images ship stale npm signing keys
COPY . .
RUN pnpm install --frozen-lockfile \
 && pnpm --filter @oglos/web-admin build \
 && VITE_BASE=/staff/ pnpm --filter @oglos/staff-pwa build

FROM python:3.12.8-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /bin/uv
WORKDIR /app
COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY apps/api/ .
COPY --from=web /repo/apps/web-admin/dist /app/web/admin
COPY --from=web /repo/apps/staff-pwa/dist /app/web/staff
RUN useradd --system --uid 10001 oglos && chown -R oglos /app
USER oglos
ENV PATH="/app/.venv/bin:$PATH" WEB_DIST_DIR=/app/web STORAGE_BACKEND=db APP_ENV=demo PORT=10000
# Free services have no pre-deploy step: bootstrap + migrate + (idempotent) demo seed, then serve.
CMD ["sh", "-c", "python -m app.db.bootstrap && alembic upgrade head && python -m app.seed.sunrise; exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips '*'"]
