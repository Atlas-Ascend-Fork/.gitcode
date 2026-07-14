# query_pipeline

通过 GitCode OpenAPI 查询流水线运行详情和各 Job 执行结果，以格式化表格输出。

## 功能

- 查询流水线整体状态（workflow 名称、分支、PR、触发者、运行时间）
- 列出所有 Job 的执行结果（名称、状态、耗时）
- 支持查看单个 Job 的步骤明细
- 列出失败的 Job 供进一步排查

## 输入参数

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `token` | 是 | - | GitCode 个人访问令牌 |
| `owner` | 否* | - | 仓库所属组织/用户 |
| `repo` | 否* | - | 仓库名称 |
| `run_id` | 否* | - | 流水线运行 ID |
| `url` | 否* | - | 流水线页面 URL（与 owner/repo/run_id 二选一） |
| `job_id` | 否 | - | 查看指定 Job 的步骤详情 |
| `json` | 否 | `false` | 输出原始 JSON |

> \* `url` 与 `owner` + `repo` + `run_id` 两种方式二选一。

## 涉及的 API

| 接口 | 方法 | 路径 |
| --- | --- | --- |
| 获取流水线运行详情 | GET | `/api/v8/repos/{owner}/{repo}/actions/runs/{run_id}` |
| 获取 Job 列表 | GET | `/api/v8/repos/{owner}/{repo}/actions/runs/{run_id}/jobs` |
| 获取 Job 详情 | GET | `/api/v8/repos/{owner}/{repo}/actions/runs/{run_id}/jobs/{job_id}` |

## 使用示例

```yaml
- name: query_pipeline
  uses: cann/.gitcode/actions/query_pipeline@master
  with:
    owner: ${{ env.org_name }}
    repo: ${{ env.repo_name }}
    run_id: ${{atomgit.workflow_run_id}}
    token: ${{ secrets.GIT_TOKEN }}
```

查看指定 Job 步骤明细：

```yaml
- name: query_job_detail
  uses: cann/.gitcode/actions/query_pipeline@master
  with:
    owner: ${{ env.org_name }}
    repo: ${{ env.repo_name }}
    run_id: ${{atomgit.workflow_run_id}}
    job_id: '<job_id>'
    token: ${{ secrets.GIT_TOKEN }}
```
