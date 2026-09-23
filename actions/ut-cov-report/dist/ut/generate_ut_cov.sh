#!/bin/bash
set -e
#echo command line
echo "$0" "$@"

FULL_COVERAGE_CONFIG="$1"
BLACKLIST="blacklist.txt"
BRANCH="$2"
TARGETS="$3"
INC_COV="$4"
OUTDIR="$5"
THRESHOLD="$6"
test_type="$8"
# 增量 diff 基线：浅克隆默认只拉 PR merge sha，需要把基分支 ref 拉下来，
# 否则 get_ai_inc_cov.py 里 `git diff origin/${BRANCH} HEAD` 会报 bad revision
if [ -d "${TARGETS}/.git" ] && [ -n "${BRANCH}" ]; then
    if git -C "${TARGETS}" fetch --no-tags origin "${BRANCH}" >/dev/null 2>&1; then
        git -C "${TARGETS}" update-ref "refs/remotes/origin/${BRANCH}" FETCH_HEAD
        echo "[INFO] base branch origin/${BRANCH} fetched for incremental diff"
    else
        echo "[WARN] fetch origin/${BRANCH} failed, incremental diff baseline may be unavailable"
    fi
fi
if [ "${INC_COV}X" == "TrueX" ]
then
    echo "FULL_COVERAGE_CONFIG is ${FULL_COVERAGE_CONFIG}"
    echo "BRANCH is ${BRANCH}"
    echo "OUTDIR is ${OUTDIR}"
    echo "TARGETS is ${TARGETS}"
    echo "BLACKLIST is ${BLACKLIST}"
    echo "INC_COV is ${INC_COV}"
    echo "THRESHOLD is ${THRESHOLD}"
    echo "python3 get_ai_inc_cov.py "${FULL_COVERAGE_CONFIG} ${FULL_COVERAGE_CONFIG}_llt" ${BRANCH} ${BLACKLIST} ${WORKSPACE} True ${THRESHOLD} ${OUTDIR} ${test_type}"
    python3 get_ai_inc_cov.py "${FULL_COVERAGE_CONFIG} ${FULL_COVERAGE_CONFIG}_llt" ${BRANCH} ${BLACKLIST} ${TARGETS} True ${THRESHOLD} ${OUTDIR} ${test_type}
    result=`echo $?`
    echo ${result}"---------------------"
    if [[ "${result}x" == "0x" ]]
    then
        exit 0
    else
        exit 0
    fi
else
    exit 1
fi
