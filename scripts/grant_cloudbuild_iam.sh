#!/usr/bin/env bash
# One-time setup: lets Cloud Build push images, deploy to Cloud Run, and
# deploy the service running as the cinesignal-dev service account.
# Run from the repo root: ! bash scripts/grant_cloudbuild_iam.sh
set -euo pipefail

PROJECT=agenticcinema-507506
CB_SA="874157397399@cloudbuild.gserviceaccount.com"

gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:${CB_SA}" --role="roles/run.admin" --condition=None

gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:${CB_SA}" --role="roles/artifactregistry.writer" --condition=None

gcloud iam service-accounts add-iam-policy-binding \
  "cinesignal-dev@${PROJECT}.iam.gserviceaccount.com" \
  --member="serviceAccount:${CB_SA}" --role="roles/iam.serviceAccountUser"

echo "Done."
