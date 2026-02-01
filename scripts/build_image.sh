#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <model> <tag> [--push]"
  exit 1
fi

MODEL="$1"
TAG="$2"
PUSH="${3:-}"

REPO="brineylab"  # TODO: update to your registry namespace
IMAGE="${REPO}/${MODEL}:${TAG}"
DOCKERFILE="containers/${MODEL}/Dockerfile"

if [[ ! -f "${DOCKERFILE}" ]]; then
  echo "Dockerfile not found: ${DOCKERFILE}"
  exit 1
fi

# Build with repo root as context so shared assets can be copied.
docker build -f "${DOCKERFILE}" -t "${IMAGE}" .

echo "Built ${IMAGE}"

if [[ "${PUSH}" == "--push" ]]; then
  docker push "${IMAGE}"
  echo "Pushed ${IMAGE}"
fi
