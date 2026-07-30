# pre-pipeline

流水线开始前给 PR 打上 `ci-pipeline-running` 标签，并移除 `ci-pipeline-passed` 和 `ci-pipeline-failed` 标签。

## 输入参数

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `owner` | 是 | - | 仓库所属组织/用户 |
| `repo` | 是 | - | 仓库名称 |
| `pr_number` | 是 | - | PR 编号 |
| `token` | 是 | - | GitCode 个人访问令牌 |
| `apply_label` | 否 | `true` | 是否执行打标签逻辑 |

## 涉及的 API

| 接口 | 方法 | 路径 |
| --- | --- | --- |
| 添加 PR 标签 | POST | `/api/v5/repos/{owner}/{repo}/pulls/{pr_number}/labels` |
| 删除 PR 标签 | DELETE | `/api/v5/repos/{owner}/{repo}/pulls/{pr_number}/labels/{label}` |

## 使用示例

```yaml
- name: pre_pipeline
  uses: cann/.gitcode/actions/pre-pipeline@master
  with:
    owner: ${{ env.org_name }}
    repo: ${{ env.repo_name }}
    pr_number: ${{ atomgit.event.pull_request.number }}
    token: ${{ secrets.GIT_TOKEN }}
    apply_label: 'true'
```
