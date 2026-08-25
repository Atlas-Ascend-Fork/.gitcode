#!/bin/bash
set -e

WORKSPACE="${WORKSPACE}"
UT_TYPE="${UT_TYPE}"
TARGET_BRANCH="${TARGET_BRANCH}"
COVERAGE_NUM="${COVERAGE_NUM}"

pip install diff-cover 2>/dev/null || true

coveragePath=$(find "${WORKSPACE}" -name ".coverage" | head -n1)
if [ -z "${coveragePath}" ]; then
    echo "No coverage file found"
    exit 0
fi
coverageDir=$(dirname "${coveragePath}")
cd "${coverageDir}" || exit
echo "coverage is exist"
python3 -m coverage html -i -d cov_report
if [ -d cov_report ]; then
    tar -zcf ut_cov_python_${UT_TYPE}.tar.gz *
    if [ "$(cd "${coverageDir}" && pwd)" != "$(cd "${WORKSPACE}" && pwd)" ]; then
        cp -rf ut_cov_python_${UT_TYPE}.tar.gz "${WORKSPACE}"
    fi
fi
cd "${coverageDir}" || exit
python3 -m coverage xml -i
coverage_file="${coverageDir}/coverage.xml"
python3 -m diff_cover.diff_cover_tool --compare-branch=origin/${TARGET_BRANCH} "${coverage_file}" --fail-under=${COVERAGE_NUM}
if [ $? -ne 0 ];then
    echo "Coverage less than fail-under=${COVERAGE_NUM}"
    exit 1
fi
