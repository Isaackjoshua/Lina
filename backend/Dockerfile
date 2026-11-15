FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.9 /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Dependencies first, so code changes do not reinstall them.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY alembic.ini ./
COPY alembic ./alembic
COPY lina ./lina

RUN useradd --system --uid 1001 lina
USER lina

EXPOSE 8000
CMD ["uvicorn", "lina.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
