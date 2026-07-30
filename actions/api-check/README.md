# api-check

依据 `mode` 参数执行不同流程：

- `mode: compile`：调用 `api_compile_upload.sh`，执行 API 文档生成、上报与可用性检查。
- `mode: check`：调用 `api_check.sh`，查询 PR 接口校验结果。

## 输入参数

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `org_name` | 是 | 组织名称 |
| `mode` | 是 | 执行模式：`compile`（API文档生成上报）或 `check`（PR接口校验） |
| `repo_name` | 否 | 仓库名称 |
| `merge_id` | 否 | PR/MERGE 编号 |
| `workspace` | 否 | 代码工作目录（compile 模式必填） |
| `source_branch` | 否 | PR 源分支（compile 模式必填） |
| `target_branch` | 否 | PR 目标分支（compile 模式必填） |

## 使用示例

compile 模式：

```yaml
- name: Checkout
  identifier: process_checkout
  uses: checkout
  with:
    ref: ${{ atomgit.event.pull_request.merge_commit_sha || atomgit.sha }}
    token: ${{ secrets.GIT_TOKEN }}
- name: api-check
  identifier: api-check
  uses: cann/.gitcode/actions/api-check@master
  with:
    org_name: ${{ env.org_name }}
    mode: compile
    repo_name: ${{ env.repo_name }}
    merge_id: ${{ env.MERGE_ID }}
    workspace: ${{ steps.process_checkout.outputs.path }}
    source_branch: ${{ env.SOURCE_BRANCH }}
    target_branch: ${{ env.TARGET_BRANCH }}
```

check 模式：

```yaml
- name: api-check
  uses: cann/.gitcode/actions/api-check@master
  with:
    org_name: ${{ env.org_name }}
    mode: check
    repo_name: ${{ env.repo_name }}
    merge_id: ${{ env.MERGE_ID }}
```
