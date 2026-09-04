#!/bin/bash
set -e

WORKSPACE="${WORKSPACE}"
UT_TYPE="${UT_TYPE}"
TARGET_BRANCH="${TARGET_BRANCH}"
COVERAGE_NUM="${COVERAGE_NUM}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

pip install diff-cover 2>/dev/null || true

coverageJson=$(find "${WORKSPACE}" -name "coverage-final.json" -path "*/coverage/*" | head -n1)
if [ -z "${coverageJson}" ]; then
    echo "No coverage-final.json found"
    exit 0
fi
coverageDir=$(dirname "${coverageJson}")
echo "coverage-final.json found: ${coverageJson}"

node "${SCRIPT_DIR}/convert_json_to_lcov.mjs" "${coverageJson}" "${WORKSPACE}/cov/coverage.info"

cd "${WORKSPACE}/cov"
tar -zcf "ut_cov_${UT_TYPE}.tar.gz" *
cp -f "ut_cov_${UT_TYPE}.tar.gz" "${WORKSPACE}"

cd "${WORKSPACE}"
if [ -f "cov/coverage.info" ]; then
    python3 -m diff_cover.diff_cover_tool "cov/coverage.info" --compare-branch=origin/${TARGET_BRANCH} --fail-under=${COVERAGE_NUM} || true
fi
