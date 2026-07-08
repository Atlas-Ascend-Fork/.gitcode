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
GIT_TOKEN="${GIT_TOKEN:-}"
cd "${WORKSPACE}"

# 先拿到原始远程地址
ORIG_URL=$(git remote get-url origin)
echo ${ORIG_URL}

# 配置远端分支映射规则
git config --local remote.origin.fetch "+refs/heads/*:refs/remotes/origin/*"

if [[ -n "${GIT_TOKEN}" ]]; then
  AUTH_URL=$(echo "$ORIG_URL" | sed "s|https://|https://cann-robot:${GIT_TOKEN}@|")
  git fetch "${AUTH_URL}" "${target_branch}:refs/remotes/origin/${target_branch}" --unshallow
else
  echo "公开仓库，无Token直接拉取"
  git fetch origin "${target_branch}" --unshallow
fi

# 校验分支是否拉取成功
if ! git rev-parse "origin/${target_branch}" >/dev/null 2>&1; then
  echo "ERROR: 远端分支 origin/${target_branch} 不存在"
  exit 1
fi

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

