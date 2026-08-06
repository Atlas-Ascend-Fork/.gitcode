# query-pipeline

通过 GitCode OpenAPI 查询流水线运行详情和各 Job 执行结果，以格式化表格输出。支持根据任务执行结果给 PR 打标签。

## 功能

- 查询流水线整体状态（workflow 名称、分支、PR、触发者、运行时间）
- 列出所有 Job 的执行结果（名称、状态、耗时）
- 列出失败的 Job 供进一步排查
- 根据 PR 编号和任务执行结果自动打标签（无失败任务打 `ci-pipeline-passed`，有失败任务打 `ci-pipeline-failed`）

## 输入参数

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `token` | 是 | - | GitCode 个人访问令牌 |
| `owner` | 否* | - | 仓库所属组织/用户 |
| `repo` | 否* | - | 仓库名称 |
| `run_id` | 否* | - | 流水线运行 ID |
| `url` | 否* | - | 流水线页面 URL（与 owner/repo/run_id 二选一） |
| `json` | 否 | `false` | 输出原始 JSON |
| `pr_number` | 否 | - | PR 编号，需配合 `apply_label` 使用 |
| `apply_label` | 否 | `false` | 是否根据任务执行结果打标签，为 `true` 时需同时传入 `pr_number` |

> \* `url` 与 `owner` + `repo` + `run_id` 两种方式二选一。

## 涉及的 API

| 接口 | 方法 | 路径 |
| --- | --- | --- |
| 获取流水线运行详情 | GET | `/api/v8/repos/{owner}/{repo}/actions/runs/{run_id}` |
| 获取 Job 列表 | GET | `/api/v8/repos/{owner}/{repo}/actions/runs/{run_id}/jobs` |
| 获取 PR 标签列表 | GET | `/api/v5/repos/{owner}/{repo}/pulls/{pr_number}/labels` |
| 添加 PR 标签 | POST | `/api/v5/repos/{owner}/{repo}/pulls/{pr_number}/labels` |
| 移除 PR 标签 | DELETE | `/api/v5/repos/{owner}/{repo}/pulls/{pr_number}/labels/{label}` |

## 打标签逻辑

当 `apply_label` 为 `true` 且传入 `pr_number` 时，脚本在查询各任务执行结果后自动执行：

1. 统计所有任务的执行状态
2. 先移除 `ci-pipeline-passed` 和 `ci-pipeline-failed` 标签
3. 若存在失败任务（状态为 FAILED/FAILURE）→ 打 `ci-pipeline-failed`
4. 若不存在失败任务 → 打 `ci-pipeline-passed`

## 使用示例

```yaml
- name: query-pipeline
  uses: cann/.gitcode/actions/query-pipeline@master
  with:
    owner: ${{ env.org_name }}
    repo: ${{ env.repo_name }}
    run_id: ${{atomgit.workflow_run_id}}
    token: ${{ secrets.GIT_TOKEN }}
    pr_number: ${{ env.MERGE_ID }}
    apply_label: 'true'
```
