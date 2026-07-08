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

# 打印当前脚本的路径
echo "当前脚本路径： $SCRIPT_PATH, $WORK_CODE_DIR"

target_branch="${TARGET_BRANCH}"
cd "${WORKSPACE}"

git branch
git branch -r

git diff origin/${target_branch} HEAD --stat
git -c core.quotePath=false diff origin/${target_branch} HEAD --name-status > pr_filelist_mod.txt
git -c core.quotePath=false diff origin/${target_branch} HEAD --name-only > pr_filelist.txt
git -c core.quotePath=false diff origin/${target_branch}...HEAD --name-only --diff-filter=AM > pr_filelist_precommit.txt
git -c core.quotePath=false diff -U0 -w --no-renames origin/${target_branch}...HEAD > update_file_detail.txt

cat pr_filelist_mod.txt
cat pr_filelist.txt
cat pr_filelist_precommit.txt

# touch gitdiff.txt
# while IFS= read -r line;do
#   if [[ -f "$line" && "$line" == *.md ]];then
#     echo "------${line}" >> gitdiff.txt
#     git diff origin/${target_branch} "$line" >> gitdiff.txt
#   fi
# done < pr_filelist.txt


# 打印传入的参数
echo "传入的参数: $sc_tool"

case "$sc_tool" in
    markdown)
        sc_scan_cmd="$SCRIPT_DIR/staticcheck/markdownlint/markdownlint.sh $WORK_CODE_DIR $REPOSITORY_NAME $GIT_TARGET_BRANCH $COMMIT_ID"
        ;;
    *)
        sc_scan_cmd="$SCRIPT_DIR/staticcheck/docs-ci/docs-ci.sh $WORK_CODE_DIR $REPOSITORY_NAME $GIT_TARGET_BRANCH $COMMIT_ID $sc_tool"
        ;;
esac

echo $sc_scan_cmd

bash $sc_scan_cmd
echo "run status $?"
exit $?

