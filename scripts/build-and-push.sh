#!/usr/bin/env bash
# Build and push service images to Artifact Registry.
#
# Usage:
#   ./scripts/build-and-push.sh                # builds user-service and task-service
#   ./scripts/build-and-push.sh user-service   # one service only
#   TAG=v1.2.3 ./scripts/build-and-push.sh     # custom tag (defaults: short git sha + latest)
#
# Env overrides:
#   PROJECT_ID   GCP project (default: still-function-494322-d7)
#   REGION       Artifact Registry region (default: europe-west3)
#   REPO         Repository name (default: taskmanager)
#   TAG          Image tag (default: git short sha; also pushed as :latest)
#   PLATFORM     Build platform (default: linux/amd64 — Cloud Run is x86_64)

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-still-function-494322-d7}"
REGION="${REGION:-europe-west3}"
REPO="${REPO:-taskmanager}"
PLATFORM="${PLATFORM:-linux/amd64}"

if [[ -z "${TAG:-}" ]]; then
  TAG="$(git -C "$(dirname "$0")/.." rev-parse --short HEAD 2>/dev/null || echo latest)"
fi

REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Default to both services; allow positional overrides.
if [[ $# -eq 0 ]]; then
  SERVICES=(user-service task-service)
else
  SERVICES=("$@")
fi

gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

for svc in "${SERVICES[@]}"; do
  if [[ ! -f "${REPO_ROOT}/services/${svc}/Dockerfile" ]]; then
    echo "unknown service: ${svc}" >&2
    exit 1
  fi

  image="${REGISTRY}/${svc}"
  echo "==> building ${image}:${TAG}"
  docker build \
    --platform="${PLATFORM}" \
    -f "services/${svc}/Dockerfile" \
    -t "${image}:${TAG}" \
    -t "${image}:latest" \
    "${REPO_ROOT}"

  echo "==> pushing ${image}:${TAG}"
  docker push "${image}:${TAG}"
  docker push "${image}:latest"
done

echo
echo "done. Pushed tag: ${TAG}"
