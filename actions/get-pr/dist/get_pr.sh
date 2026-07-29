#!/bin/bash

target_branch="${TARGET_BRANCH}"
COMMIT_SHA="${COMMIT_SHA:-}"
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

# commit 与 target_branch 冲突检测
if [[ -n "${COMMIT_SHA}" ]]; then
  # 校验 commit 是否存在于本地仓库
  if ! git rev-parse "${COMMIT_SHA}" >/dev/null 2>&1; then
    echo "WARNING: commit ${COMMIT_SHA} 不存在于本地仓库，跳过冲突检测"
  else
    target_ref="origin/${target_branch}"
    short_commit=$(git rev-parse --short "${COMMIT_SHA}")
    target_short=$(git rev-parse --short "${target_ref}")

    if git merge-base --is-ancestor "${COMMIT_SHA}" "${target_ref}" 2>/dev/null; then
      # commit 已合入 target_branch
      conflict_reason="commit \`${short_commit}\` 已合入目标分支 \`${target_branch}\`（${target_short}），diff 结果为空或反向"
      has_conflict=1
    elif ! git merge-base --is-ancestor "${target_ref}" "${COMMIT_SHA}" 2>/dev/null; then
      # 两者已分叉，target_branch 不是 commit 的祖先
      conflict_reason="commit \`${short_commit}\` 与目标分支 \`${target_branch}\`（${target_short}）已分叉，diff 结果包含无关变更"
      has_conflict=1
    else
      echo "✅ commit ${short_commit} 是目标分支 ${target_branch} 的后代，无冲突"
      has_conflict=0
    fi

    if [[ "${has_conflict}" == "1" ]]; then
      echo "⚠️ 检测到冲突：${conflict_reason}"
      if [[ -n "${ATOMGIT_STEP_SUMMARY}" ]]; then
        {
          echo "## ⚠️ Commit 与 Target Branch 冲突"
          echo ""
          echo "| 参数 | 值 |"
          echo "|------|------|"
          echo "| commit | \`${short_commit}\` |"
          echo "| target_branch | \`${target_branch}\`（${target_short}） |"
          echo ""
          echo "**冲突原因：** ${conflict_reason}"
          echo ""
        } >> "${ATOMGIT_STEP_SUMMARY}"
      fi
    fi
  fi
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