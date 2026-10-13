# pre-pipeline

流水线最前置检查插件: ① 传入 `pr_number` 时检测 **PR 冲突状态**(冲突 PR 的 `merge_commit_sha` 不存在, 后续 Checkout 必失败, 故必须在最早阶段拦截); ② 给 PR 打上 `ci-pipeline-running` 标签并移除 `ci-pipeline-passed`/`ci-pipeline-failed` 标签; ③ 传入 `run_url` 时在 PR 评论区发布流水线链接评论; ④ 传入 `actor` 时检查触发者权限(`target_repo` 可指定, 默认取 `owner/repo`), 失败则发布「CI 流水线启动失败」评论并以退出码 1 终止。

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
      ├─ permission ∈ {push, admin} → ✅ 通过
      ├─ role_name 含"维护者"(生态维护者/社区维护者等可信角色, 见 TRUSTED_ROLES) → ✅ 通过
      ├─ 其他 read 级角色(生态开发者等) → ❌ 失败
      ├─ HTTP 404(非仓库成员) → ❌ 失败
      └─ 未识别触发者(actor 为空) → 跳过检查
```

> 说明: GitCode 自定义角色(如生态维护者)在 API 中粗粒度映射为 `read`, 但平台实际允许其触发流水线, 故按角色白名单放通(2026-09 起)。

**失败行为**: 发布「❌ CI 流水线启动失败」PR 评论(含权限说明与处理建议), 并以退出码 1 终止步骤。

**成功行为**: 仅打日志, 不写步骤摘要。

## 冲突检测逻辑

`pr_number` 存在时, 在**权限检查通过后、打标签之前**调用 `GET /api/v5/repos/{owner}/{repo}/pulls/{pr_number}`, 读取 `mergeable_state.conflict_passed`(权限是准入门槛, 先拦未授权触发者, 避免其通过反复触发向 PR 区塞评论):

| conflict_passed | 判定 | 行为 |
| --- | --- | --- |
| `false` | 冲突 | 发布「❌ CI 流水线启动失败」评论(含冲突说明与处理建议), 退出码 1 终止 |
| `true` | 无冲突 | 打日志继续 |
| 字段缺失/解析失败 | 未知 | WARNING 不阻断 |

> 背景: 冲突检测原在 `get-pr` 插件中, 但冲突 PR 的 `merge_commit_sha` 不存在导致 pre_action 的 Checkout(拉 `merge_commit_sha`)先行失败, 检测从未生效, 故移入 pre-pipeline 在流水线最早阶段执行(2026-09)。

## 涉及的 API

| 接口 | 方法 | 路径 |
| --- | --- | --- |
| 添加 PR 标签 | POST | `/api/v5/repos/{owner}/{repo}/pulls/{pr_number}/labels` |
| 删除 PR 标签 | DELETE | `/api/v5/repos/{owner}/{repo}/pulls/{pr_number}/labels/{label}` |
| 发布 PR 评论 | POST | `/api/v5/repos/{owner}/{repo}/pulls/{pr_number}/comments` |
| 查询用户仓库权限 | GET | `/api/v5/repos/{owner}/{repo}/collaborators/{username}/permission` |
| 查询 PR 信息(冲突检测) | GET | `/api/v5/repos/{owner}/{repo}/pulls/{pr_number}` |

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
