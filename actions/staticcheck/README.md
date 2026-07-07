# staticcheck

按 `check_type` 分发到对应静态检查工具：

- `markdown`：调用 `markdownlint/markdownlint.sh` 检查 Markdown 规范。
- 其他：调用 `docs-ci/docs-ci.sh` 进行文档规范检查（支持多种子工具）。

## 输入参数

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `workspace` | 是 | - | 代码工作目录 |
| `check_type` | 是 | - | 检查类型，如 `markdown` |
| `repo_name` | 是 | - | 仓库名称 |
| `target_branch` | 是 | - | 对比基准分支 |
| `merge_id` | 是 | - | PR/MERGE 编号 |
| `commit_id` | 否 | `0` | 当前提交 commit hash |

## 使用示例

```yaml
- name: Checkout
  identifier: process_checkout
  uses: checkout
  with:
    ref: ${{ atomgit.event.pull_request.merge_commit_sha || atomgit.sha }}
    token: ${{ secrets.GIT_TOKEN }}
- name: staticcheck
  identifier: staticcheck
  uses: cann/.gitcode/actions/staticcheck@master
  with:
    check_type: ${{ inputs.check_type }}
    target_branch: ${{ env.TARGET_BRANCH }}
    repo_name: ${{ env.repo_name }}
    merge_id: ${{ env.MERGE_ID }}
    commit_id: ${{ env.COMMIT_ID }}
    workspace: ${{ steps.process_checkout.outputs.path }}
```
