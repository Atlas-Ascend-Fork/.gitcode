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
