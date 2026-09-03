#!/usr/bin/env bash
# One-time setup: pushes ClickHouse creds from .env into Secret Manager.
# Run from the repo root: ! bash scripts/create_secrets.sh
set -euo pipefail
cd "$(dirname "$0")/.."

source <(grep -E '^(CLICKHOUSE_HOST|CLICKHOUSE_PORT|CLICKHOUSE_USER|CLICKHOUSE_PASSWORD)=' .env)

PROJECT=agenticcinema-507506

create_or_update() {
  local name="$1" value="$2"
  if gcloud secrets describe "$name" --project="$PROJECT" >/dev/null 2>&1; then
    printf '%s' "$value" | gcloud secrets versions add "$name" --data-file=- --project="$PROJECT"
  else
    printf '%s' "$value" | gcloud secrets create "$name" --data-file=- --project="$PROJECT"
  fi
}

create_or_update clickhouse-host "$CLICKHOUSE_HOST"
create_or_update clickhouse-port "$CLICKHOUSE_PORT"
create_or_update clickhouse-user "$CLICKHOUSE_USER"
create_or_update clickhouse-password "$CLICKHOUSE_PASSWORD"

echo "Secrets created/updated. Granting cinesignal-dev SA access..."
for s in clickhouse-host clickhouse-port clickhouse-user clickhouse-password; do
  gcloud secrets add-iam-policy-binding "$s" \
    --member="serviceAccount:cinesignal-dev@${PROJECT}.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor" \
    --project="$PROJECT" >/dev/null
done
echo "Done."
