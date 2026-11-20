# One image for api, worker and beat (different commands in docker-compose).
FROM python:3.12.8-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY . .
RUN useradd --system --uid 10001 oglos && chown -R oglos /app
USER oglos
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
ENV PORT=8000
# --proxy-headers: rate limits must see the real client IP behind Render / Caddy.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips '*'"]
