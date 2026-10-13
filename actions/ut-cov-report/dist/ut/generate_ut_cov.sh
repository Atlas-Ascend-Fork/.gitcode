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
if [ "${INC_COV}X" == "TrueX" ]
then
    echo "FULL_COVERAGE_CONFIG is ${FULL_COVERAGE_CONFIG}"
    echo "BRANCH is ${BRANCH}"
    echo "OUTDIR is ${OUTDIR}"
    echo "TARGETS is ${TARGETS}"
    echo "BLACKLIST is ${BLACKLIST}"
    echo "INC_COV is ${INC_COV}"
    echo "THRESHOLD is ${THRESHOLD}"
    # 增量 diff 基线：浅克隆只拉了 PR merge sha，需要带 token 把基分支 ref 拉下来，
    # 否则 get_ai_inc_cov.py 里 `git diff origin/${BRANCH} HEAD` 会报 bad revision
    if [ -d "${TARGETS}/.git" ] && [ -n "${BRANCH}" ] && [ -n "${GIT_TOKEN:-}" ]; then
        ORIGIN_URL=$(git -C "${TARGETS}" remote get-url origin 2>/dev/null)
        if git -C "${TARGETS}" fetch --no-tags "https://${GIT_TOKEN}@${ORIGIN_URL#https://}" "+refs/heads/${BRANCH}:refs/remotes/origin/${BRANCH}" >/dev/null 2>&1 \
           || git -C "${TARGETS}" fetch --no-tags "https://oauth2:${GIT_TOKEN}@${ORIGIN_URL#https://}" "+refs/heads/${BRANCH}:refs/remotes/origin/${BRANCH}" >/dev/null 2>&1; then
            echo "[INFO] base branch origin/${BRANCH} fetched (authenticated)"
        else
            echo "[WARN] fetch origin/${BRANCH} failed, incremental diff baseline may be unavailable"
        fi
    else
        echo "[WARN] GIT_TOKEN 缺失，跳过基分支 fetch"
    fi
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
