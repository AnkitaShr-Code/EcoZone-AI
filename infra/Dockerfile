# One image, one Cloud Run service (infra/RULES.md): the app build plus the Python packages.
# The area bundle is not in the image; the service reads it from ECOZONE_BUNDLE_URI at startup.

# ---- stage 1: build the React app ----
FROM node:24-slim AS app
WORKDIR /src/app
COPY app/package.json app/package-lock.json ./
RUN npm ci
COPY app/ ./
RUN npm run build

# ---- stage 2: Python service ----
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never PYTHONUNBUFFERED=1
WORKDIR /srv

# Dependencies first, for layer caching
COPY pyproject.toml uv.lock ./
COPY contract/pyproject.toml contract/
COPY engine/pyproject.toml engine/
COPY pipeline/pyproject.toml pipeline/
COPY agents/pyproject.toml agents/
COPY api/pyproject.toml api/
RUN mkdir -p contract/src/ecozone_contract engine/src/ecozone_engine pipeline/src/ecozone_pipeline \
      agents/src/ecozone_agents api/src/ecozone_api \
 && uv sync --frozen --no-dev --no-install-workspace --package ecozone-api

COPY contract/src contract/src
COPY engine/src engine/src
COPY agents/src agents/src
COPY api/src api/src
RUN uv sync --frozen --no-dev --package ecozone-api

COPY pipeline/config/unit_costs.yaml /srv/config/unit_costs.yaml
COPY --from=app /src/app/dist /srv/app/dist
ENV ECOZONE_APP_DIST=/srv/app/dist ECOZONE_UNIT_COSTS=/srv/config/unit_costs.yaml PORT=8080
RUN useradd --system --uid 10001 ecozone
USER ecozone
EXPOSE 8080
CMD ["sh", "-c", "exec /srv/.venv/bin/uvicorn ecozone_api.main:app --host 0.0.0.0 --port ${PORT}"]
