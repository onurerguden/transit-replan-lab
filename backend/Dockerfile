FROM ghcr.io/astral-sh/uv:0.11.7@sha256:240fb85ab0f263ef12f492d8476aa3a2e4e1e333f7d67fbdd923d00a506a516a AS uv
FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df

COPY --from=uv /uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    TRL_DATA=/app/data \
    TRL_DB=/var/lib/trl/runs.sqlite \
    PATH="/app/backend/.venv/bin:$PATH"

WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock /app/backend/
RUN uv sync --locked --no-dev --no-install-project --project backend
COPY backend/src /app/backend/src
RUN uv sync --locked --no-dev --no-editable --project backend \
    && groupadd --system trl \
    && useradd --system --gid trl trl \
    && install -d -o trl -g trl /var/lib/trl
COPY data/gtfs /app/data/gtfs
COPY data/scenarios/demo.json /app/data/scenarios/demo.json
COPY data/fixtures /app/data/fixtures

USER trl
EXPOSE 8000
CMD ["uvicorn", "--factory", "trl.api.app:create_app", "--host", "0.0.0.0", "--port", "8000"]
