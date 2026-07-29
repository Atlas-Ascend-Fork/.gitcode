#!/bin/bash

target_branch="${TARGET_BRANCH}"
OWNER="${OWNER:-}"
REPO="${REPO:-}"
PR_NUMBER="${PR_NUMBER:-}"
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

# 通过 API 检测 PR 冲突状态
if [[ -n "${OWNER}" && -n "${REPO}" && -n "${PR_NUMBER}" ]]; then
  PR_API_URL="https://api.gitcode.com/api/v5/repos/${OWNER}/${REPO}/pulls/${PR_NUMBER}"
  if [[ -n "${GIT_TOKEN}" ]]; then
    PR_INFO=$(curl -sf -H "Authorization: Bearer ${GIT_TOKEN}" "${PR_API_URL}" 2>/dev/null)
  else
    PR_INFO=$(curl -sf "${PR_API_URL}" 2>/dev/null)
  fi
  if [[ $? -ne 0 || -z "${PR_INFO}" ]]; then
    echo "WARNING: 获取 PR 信息失败，跳过冲突检测"
  else
    conflict_passed=$(echo "${PR_INFO}" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('mergeable_state', {}).get('conflict_passed', ''))
except Exception:
    print('')
" 2>/dev/null)

    if [[ "${conflict_passed}" == "False" ]]; then
      echo "⚠️ PR #${PR_NUMBER} 存在冲突（conflict_passed=False）"
      if [[ -n "${ATOMGIT_STEP_SUMMARY}" ]]; then
        {
          echo "## ⚠️ PR 冲突检测"
          echo ""
          echo "| 参数 | 值 |"
          echo "|------|------|"
          echo "| PR | #${PR_NUMBER} |"
          echo "| owner/repo | ${OWNER}/${REPO} |"
          echo "| target_branch | \`${target_branch}\` |"
          echo "| conflict_passed | ❌ False |"
          echo ""
          echo "**冲突原因：** PR 与目标分支存在冲突，无法自动合并，请先解决冲突再重新触发流水线。"
          echo ""
        } >> "${ATOMGIT_STEP_SUMMARY}"
      fi
    elif [[ "${conflict_passed}" == "True" ]]; then
      echo "✅ PR #${PR_NUMBER} 无冲突（conflict_passed=True）"
    else
      echo "WARNING: 无法解析 conflict_passed 字段，跳过冲突检测"
    fi
  fi
else
  echo "未提供 owner/repo/pr_number/git_token，跳过冲突检测"
fi

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