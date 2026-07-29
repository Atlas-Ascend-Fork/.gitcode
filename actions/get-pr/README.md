# get-pr

拉取目标分支并生成 PR 变更文件清单，供后续检查步骤消费。

## 输入参数

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `workspace` | 是 | 代码工作目录（已检出的仓库根目录） |
| `target_branch` | 是 | 对比基准分支 |
| `commit` | 否 | 指定 commit SHA，传入时与 target_branch 做冲突检测，冲突信息写入步骤摘要 |
| `git_token` | 否 | 私有仓库访问 token，公开仓库无需传入 |

## 产物

| 文件 | 说明 |
| --- | --- |
| `pr_filelist.txt` | 变更文件名清单 |
| `pr_filelist_mod.txt` | 变更文件名 + 状态（A/M/D）清单 |
| `pr_filelist_precommit.txt` | 新增/修改（A/M）文件清单，供 `precommit` 使用 |
| `update_file_detail.txt` | 变更明细 diff（`-U0 -w --no-renames`） |
| `gitdiff.txt` | 所有 `.md` 变更文件的完整 diff |

## 冲突检测

当传入 `commit` 参数时，会检测该 commit 与 `target_branch` 的关系：

| 场景 | 判定 | 说明 |
| --- | --- | --- |
| target_branch 是 commit 的祖先 | 无冲突 | commit 基于目标分支，diff 正常 |
| commit 已合入 target_branch | 冲突 | diff 结果为空或反向 |
| 两者已分叉 | 冲突 | diff 结果包含无关变更 |

冲突信息通过 `$ATOMGIT_STEP_SUMMARY` 写入步骤摘要，以 Markdown 表格形式展示。

## 使用示例

```yaml
- name: Checkout
  identifier: process_checkout
  uses: checkout
  with:
    ref: ${{ atomgit.event.pull_request.merge_commit_sha || atomgit.sha }}
    token: ${{ secrets.GIT_TOKEN }}
- name: get_pr
  identifier: get_pr
  uses: cann/.gitcode/actions/get-pr@master
  with:
    workspace: ${{ steps.process_checkout.outputs.path }}
    target_branch: ${{ env.TARGET_BRANCH }}
    commit: ${{ atomgit.sha }}
    git_token: ${{ secrets.GIT_TOKEN }}
```
