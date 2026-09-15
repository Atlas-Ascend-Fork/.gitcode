#!/bin/bash
########
# Init #
########

# 获取当前脚本的路径
SCRIPT_PATH=$(realpath "$0")
SCRIPT_DIR=$(dirname "$SCRIPT_PATH")
WORK_CODE_DIR=${WORKSPACE}
sc_tool=$1
REPOSITORY_NAME=$2
GIT_TARGET_BRANCH=$3
GIT_PR_NUMBER=$4
COMMIT_ID=$5
ORG_NAME=$6

# 打印当前脚本的路径
echo "当前脚本路径： $SCRIPT_PATH, $WORK_CODE_DIR"


# 打印传入的参数
echo "传入的参数: $sc_tool"

# case "$sc_tool" in
#     markdown)
#         sc_scan_cmd="$SCRIPT_DIR/staticcheck/markdownlint/markdownlint.sh $WORK_CODE_DIR $REPOSITORY_NAME $GIT_TARGET_BRANCH $COMMIT_ID"
#         ;;
#     *)
#         sc_scan_cmd="$SCRIPT_DIR/staticcheck/docs-ci/docs-ci.sh $WORK_CODE_DIR $REPOSITORY_NAME $GIT_TARGET_BRANCH $COMMIT_ID $sc_tool"
#         ;;
# esac
sc_scan_cmd="$SCRIPT_DIR/staticcheck/docs-ci/docs-ci.sh $WORK_CODE_DIR $REPOSITORY_NAME $GIT_TARGET_BRANCH $COMMIT_ID $sc_tool $ORG_NAME $GIT_PR_NUMBER"
echo $sc_scan_cmd
bash $sc_scan_cmd
return_value=$?
echo "run sc_scan_cmd status ${return_value}"
exit ${return_value}
