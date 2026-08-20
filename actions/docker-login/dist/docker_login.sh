#!/bin/bash
set -euo pipefail

REGISTRY="${REGISTRY:-}"
USERNAME="${USERNAME:-}"
PASSWORD="${PASSWORD:-}"
DOCKER_CONFIG="${DOCKER_CONFIG:-}"

if [[ -z "${USERNAME}" || -z "${PASSWORD}" ]]; then
  echo "ERROR: Username and password required"
  exit 1
fi

if [[ -n "${DOCKER_CONFIG}" ]]; then
  mkdir -p "${DOCKER_CONFIG}"
  export DOCKER_CONFIG
fi

echo "${PASSWORD}" | docker login ${REGISTRY} --username "${USERNAME}" --password-stdin
