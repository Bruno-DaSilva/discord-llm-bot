FROM docker.io/library/python:3.12-slim-bookworm AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /bin/
ENV UV_PYTHON_DOWNLOADS=0
ENV UV_LINK_MODE=copy
WORKDIR /app
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-editable

FROM docker.io/library/python:3.12-slim-bookworm
RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY --from=builder /app/.venv .venv
COPY src src
ENV PYTHONPATH="/app"
ENV PATH="/app/.venv/bin:$PATH"
USER app
CMD ["python", "-u", "-m", "src.bot"]
