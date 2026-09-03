# CineSignal — single container: FastAPI serves the built SPA + /api/*,
# with mcp-clickhouse installed in the same Python environment and spawned
# as a subprocess at runtime (agent/mcp_client.py). Deploys to Cloud Run.

FROM node:20-slim AS web-build
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm install
COPY web/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY agent/ ./agent/
COPY api/ ./api/
COPY playbooks/ ./playbooks/
COPY ingest/ddl.sql ./ingest/ddl.sql
COPY --from=web-build /web/dist ./web/dist

ENV PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
