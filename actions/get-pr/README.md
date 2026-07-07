# get-pr

拉取目标分支并生成 PR 变更文件清单，供后续检查步骤消费。

## 输入参数

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `workspace` | 是 | 代码工作目录（已检出的仓库根目录） |
| `target_branch` | 是 | 对比基准分支 |
| `git_token` | 否 | 私有仓库访问 token，公开仓库无需传入 |

## 产物

| 文件 | 说明 |
| --- | --- |
| `pr_filelist.txt` | 变更文件名清单 |
| `pr_filelist_mod.txt` | 变更文件名 + 状态（A/M/D）清单 |
| `pr_filelist_precommit.txt` | 新增/修改（A/M）文件清单，供 `precommit` 使用 |
| `update_file_detail.txt` | 变更明细 diff（`-U0 -w --no-renames`） |
| `gitdiff.txt` | 所有 `.md` 变更文件的完整 diff |

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
    git_token: ${{ secrets.GIT_TOKEN }}
```
