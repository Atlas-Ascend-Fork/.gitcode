#!/bin/bash

target_branch="${TARGET_BRANCH}"
OWNER="${OWNER:-}"
REPO="${REPO:-}"
PR_NUMBER="${PR_NUMBER:-}"
GIT_TOKEN="${GIT_TOKEN:-}"
cd "${WORKSPACE}" || exit 1

# 先拿到原始远程地址
ORIG_URL=$(git remote get-url origin) || exit 1
echo ${ORIG_URL}

# 配置远端分支映射规则
git config --local remote.origin.fetch "+refs/heads/*:refs/remotes/origin/*" || exit 1

fetch_args=()
is_shallow=$(git rev-parse --is-shallow-repository) || exit 1
if [[ "${is_shallow}" == "true" ]]; then
  fetch_args+=(--unshallow)
fi

if [[ -n "${GIT_TOKEN}" ]]; then
  AUTH_URL=$(echo "$ORIG_URL" | sed "s|https://|https://cann-robot:${GIT_TOKEN}@|")
  git fetch "${AUTH_URL}" "${target_branch}:refs/remotes/origin/${target_branch}" "${fetch_args[@]}" || exit 1
else
  echo "公开仓库，无Token直接拉取"
  git fetch origin "${target_branch}:refs/remotes/origin/${target_branch}" "${fetch_args[@]}" || exit 1
fi

# 校验分支是否拉取成功
if ! git rev-parse "origin/${target_branch}" >/dev/null 2>&1; then
  echo "ERROR: 远端分支 origin/${target_branch} 不存在"
  exit 1
fi

git branch
git branch -r

# The target may advance after the PR merge snapshot was created. Comparing
# its current tip directly with HEAD would include reversals of unrelated work.
diff_base=$(git merge-base "origin/${target_branch}" HEAD) || exit 1
if [[ -z "${diff_base}" ]]; then
  echo "ERROR: PR HEAD has no common ancestor with the target branch"
  exit 1
fi
echo "PR diff base: ${diff_base}"
git diff "${diff_base}" HEAD --stat || exit 1
git -c core.quotePath=false diff "${diff_base}" HEAD --name-status > pr_filelist_mod.txt || exit 1
git -c core.quotePath=false diff "${diff_base}" HEAD --name-only > pr_filelist.txt || exit 1
git -c core.quotePath=false diff "${diff_base}" HEAD --name-only --diff-filter=AM > pr_filelist_precommit.txt || exit 1
git -c core.quotePath=false diff -U0 -w --no-renames "${diff_base}" HEAD > update_file_detail.txt || exit 1

touch gitdiff.txt
while IFS= read -r line;do
  if [[ -f "$line" && "$line" == *.md ]];then
    echo "------${line}" >> gitdiff.txt
    git diff "${diff_base}" HEAD -- "$line" >> gitdiff.txt || exit 1
  fi
done < pr_filelist.txt
