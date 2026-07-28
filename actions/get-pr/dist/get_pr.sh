#!/bin/bash

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

touch gitdiff.txt
while IFS= read -r line;do
  if [[ -f "$line" && "$line" == *.md ]];then
    echo "------${line}" >> gitdiff.txt
    git diff origin/${target_branch} "$line" >> gitdiff.txt
  fi
done < pr_filelist.txt

# 检测 PR 与目标分支是否存在冲突
conflict_files=""
merge_base=$(git merge-base origin/${target_branch} HEAD 2>/dev/null)
if [ -n "${merge_base}" ]; then
  # 使用 merge-tree 检测冲突（不实际 merge）
  merge_output=$(git merge-tree --write-tree --no-messages --merge-base "${merge_base}" origin/${target_branch} HEAD 2>/dev/null)
  merge_status=$?
  # merge-tree --write-tree 返回 0 表示无冲突，非 0 表示有冲突
  if [ ${merge_status} -ne 0 ]; then
    # 从 merge-tree 输出中提取冲突文件名
    conflict_files=$(echo "${merge_output}" | grep -E '^\+<<<<<<<' -B 5 | grep -oE 'diff --git a/[^ ]+ b/[^ ]+' | sed 's|diff --git a/[^ ]+ b/||' || true)
    # 如果上面的方式没提取到，尝试用另一种方式
    if [ -z "${conflict_files}" ]; then
      conflict_files=$(echo "${merge_output}" | grep -E '^CONFLICT' | awk '{print $NF}' || true)
    fi
  fi
fi

if [ -n "${conflict_files}" ]; then
  echo "CONFLICT_DETECTED=true" >> "${ATOMGIT_OUTPUT:-/dev/null}"
  echo "${conflict_files}" > conflict_files.txt
else
  echo "CONFLICT_DETECTED=false" >> "${ATOMGIT_OUTPUT:-/dev/null}"
  echo "" > conflict_files.txt
fi