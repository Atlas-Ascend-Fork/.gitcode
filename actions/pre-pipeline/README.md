# pre-pipeline

流水线开始前给 PR 打上 `ci-pipeline-running` 标签，并移除 `ci-pipeline-passed` 和 `ci-pipeline-failed` 标签；传入 `run_url` 时在 PR 评论区发布流水线链接评论；传入 `actor` 时检查触发者是否具备**目标分支仓库**的权限（`target_repo` 可指定, 默认取 `owner/repo`），失败则发布「CI 流水线启动失败」评论并以退出码 1 终止。

## 输入参数

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `owner` | 是 | - | 仓库所属组织/用户 |
| `repo` | 是 | - | 仓库名称 |
| `pr_number` | 是 | - | PR 编号 |
| `token` | 是 | - | GitCode 个人访问令牌 |
| `apply_label` | 否 | `false` | 是否执行打标签逻辑 |
| `run_url` | 否 | `''` | 当前流水线运行链接, 传入则在 PR 评论区发布流水线链接评论 |
| `actor` | 否 | `''` | 流水线触发者用户名, 用于目标仓库权限检查(失败在评论中说明) |
| `target_repo` | 否 | `owner/repo` | 目标分支仓库全名(owner/repo), 权限检查的对象仓库 |
| `pr_author` | 否 | `''` | PR 作者用户名(接 `atomgit.event.pull_request.user.login`), 作者本人触发直接通过 |

## 权限检查逻辑

传入 `actor` 时, 通过 `GET /api/v5/repos/{target_repo}/collaborators/{actor}/permission` 查询触发者对**目标分支仓库**的权限:

```
触发者 == PR 作者本人 → ✅ 通过
      │
查询触发者对目标仓库的权限
      │
      ├─ permission ∈ {push, admin} 或 access_level ≥ 30 → ✅ 通过
      ├─ HTTP 404(非仓库成员) → ❌ 失败
      └─ 未识别触发者(actor 为空) → 跳过检查
```

**失败行为**: 发布「❌ CI 流水线启动失败」PR 评论(含权限说明与处理建议), 并以退出码 1 终止步骤。

**成功行为**: 仅打日志, 不写步骤摘要。

## 涉及的 API

| 接口 | 方法 | 路径 |
| --- | --- | --- |
| 添加 PR 标签 | POST | `/api/v5/repos/{owner}/{repo}/pulls/{pr_number}/labels` |
| 删除 PR 标签 | DELETE | `/api/v5/repos/{owner}/{repo}/pulls/{pr_number}/labels/{label}` |
| 发布 PR 评论 | POST | `/api/v5/repos/{owner}/{repo}/pulls/{pr_number}/comments` |
| 查询用户仓库权限 | GET | `/api/v5/repos/{owner}/{repo}/collaborators/{username}/permission` |

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
    run_url: https://gitcode.com/${{ env.org_name }}/${{ env.repo_name }}/actions/runs/${{ atomgit.workflow_run_id }}
    actor: ${{ atomgit.actor }}
    pr_author: ${{ atomgit.event.pull_request.user.login }}
    target_repo: ${{ atomgit.event.pull_request.base.repo.full_name }}
```
