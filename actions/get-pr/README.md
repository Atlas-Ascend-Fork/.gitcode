# get-pr

拉取目标分支并生成 PR 变更文件清单，供后续检查步骤消费。

## 输入参数

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `workspace` | 是 | 代码工作目录（已检出的仓库根目录） |
| `target_branch` | 是 | 对比基准分支 |
| `owner` | 否 | 仓库所属组织/用户，传入时启用冲突检测 |
| `repo` | 否 | 仓库名称，传入时启用冲突检测 |
| `pr_number` | 否 | PR 编号，传入时调用 API 检测冲突状态 |
| `git_token` | 否 | 私有仓库访问 token，冲突检测时必传 |

## 产物

| 文件 | 说明 |
| --- | --- |
| `pr_filelist.txt` | 变更文件名清单 |
| `pr_filelist_mod.txt` | 变更文件名 + 状态（A/M/D）清单 |
| `pr_filelist_precommit.txt` | 新增/修改（A/M）文件清单，供 `precommit` 使用 |
| `update_file_detail.txt` | 变更明细 diff（`-U0 -w --no-renames`） |
| `gitdiff.txt` | 所有 `.md` 变更文件的完整 diff |

## 冲突检测

当同时传入 `owner`、`repo`、`pr_number`、`git_token` 时，通过 GitCode API（`GET /api/v5/repos/{owner}/{repo}/pulls/{number}`）获取 PR 信息，读取 `mergeable_state.conflict_passed` 字段判断冲突状态：

| conflict_passed | 判定 | 说明 |
| --- | --- | --- |
| `true` | 无冲突 | PR 可正常合并 |
| `false` | 冲突 | PR 与目标分支存在冲突，无法自动合并 |

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
    owner: ${{ env.org_name }}
    repo: ${{ env.repo_name }}
    pr_number: ${{ atomgit.event.pull_request.number }}
    git_token: ${{ secrets.GIT_TOKEN }}
```
