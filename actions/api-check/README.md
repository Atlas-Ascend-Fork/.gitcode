# api-check

依据 `task_name` 内容执行不同流程：

- 含 `compile`：调用 `api_compile_upload.sh`。该脚本内部进一步判断 `task_name` 是否同时含 `ubuntu24`，**仅当同时包含 `compile` 与 `ubuntu24` 时**才执行 API 文档生成、上报与可用性检查；否则直接退出（"no need to api check"）。
- 不含 `compile`：调用 `api_check.sh`，查询 PR 接口校验结果。

## 输入参数

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `org_name` | 是 | 组织名称 |
| `task_name` | 是 | 任务标识；含 `compile` 执行编译上报，含 `ubuntu24` 执行 PR 接口校验 |
| `repo_name` | 否 | 仓库名称 |
| `merge_id` | 否 | PR/MERGE 编号 |
| `workspace` | 否 | 代码工作目录（compile 流程必填） |
| `source_branch` | 否 | PR 源分支（compile 流程必填） |
| `target_branch` | 否 | PR 目标分支（compile 流程必填） |

## 使用示例

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
    task_name: compile
    repo_name: ${{ env.repo_name }}
    merge_id: ${{ env.MERGE_ID }}
    workspace: ${{ steps.process_checkout.outputs.path }}
    source_branch: ${{ env.SOURCE_BRANCH }}
    target_branch: ${{ env.TARGET_BRANCH }}
```
