#!/bin/bash
set -euo pipefail

REGISTRY="${REGISTRY:-}"
DOCKER_CONFIG="${DOCKER_CONFIG:-}"

if [[ -n "${DOCKER_CONFIG}" && -d "${DOCKER_CONFIG}" ]]; then
  export DOCKER_CONFIG
fi

docker logout ${REGISTRY} 2>/dev/null || true
