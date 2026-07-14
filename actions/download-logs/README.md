# download-logs

通过 GitCode OpenAPI 下载指定流水线运行的所有 Job 日志，打包为两个 zip 文件：

- `all_logs.zip` — 全部 Job 日志
- `failed_logs.zip` — 仅失败 Job 日志

每个日志文件包含 Job 头部信息（名称、状态、耗时、步骤明细）和完整日志内容。自动过滤 `workflow_call` 父 Job 和 post 阶段 Job。

## 输入参数

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `token` | 是 | - | GitCode 个人访问令牌 |
| `owner` | 否* | - | 仓库所属组织/用户 |
| `repo` | 否* | - | 仓库名称 |
| `run_id` | 否* | - | 流水线运行 ID |
| `url` | 否* | - | 流水线页面 URL（与 owner/repo/run_id 二选一） |
| `output_dir` | 否 | `logs` | 输出目录 |

> \* `url` 与 `owner` + `repo` + `run_id` 两种方式二选一。

## 输出参数

| 参数 | 说明 |
| --- | --- |
| `logs_path` | 日志保存目录的绝对路径（包含 `all_logs.zip` 和 `failed_logs.zip`） |

## 涉及的 API

| 接口 | 方法 | 路径 |
| --- | --- | --- |
| 获取流水线运行详情 | GET | `/api/v8/repos/{owner}/{repo}/actions/runs/{run_id}` |
| 获取 Job 列表 | GET | `/api/v8/repos/{owner}/{repo}/actions/runs/{run_id}/jobs` |
| 下载 Job 日志 | GET | `/api/v8/repos/{owner}/{repo}/actions/runs/{run_id}/jobs/{job_id}/download_log` |

## 使用示例

```yaml
- name: download-logs
  uses: cann/.gitcode/actions/download-logs@master
  with:
    owner: ${{ env.org_name }}
    repo: ${{ env.repo_name }}
    run_id: ${{atomgit.workflow_run_id}}
    token: ${{ secrets.GIT_TOKEN }}
    output_dir: logs
```

或通过 URL 指定：

```yaml
- name: download-logs
  uses: cann/.gitcode/actions/download-logs@master
  with:
    url: https://gitcode.com/cann/runtime/actions/runs/f833dac756e64ce3ab3d963fac641967
    token: ${{ secrets.GIT_TOKEN }}
```
