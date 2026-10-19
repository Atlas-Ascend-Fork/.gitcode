# failure-analyze

流水线失败时触发 Agent 分析失败原因：查询本次 run 的失败 Job → 组装分析上下文 → 调用 agent-hub `POST /agenthubs/api/agents/sessions/{session_id}/trigger` 异步触发分析任务。

**建议置于 `Test_finish` job 的 `query_pipeline` 步骤之后**——整条流水线唯一收尾点，一次运行至多触发一次分析，且失败 Job 清单天然可得。

## 行为逻辑(零 GitCode API 查询)

```
query_pipeline 步骤输出 pipeline_failed 变量
      │
      ├─ "false" ──> 流水线成功, 跳过失败分析
      │                └─ 开启 enable_success_review 时向 PR 写入 "/ai review force" 评论
      ├─ "true"  ──> 存在失败 Job, 触发分析
      └─ 缺失    ──> query_pipeline 自身异常(如 API 限流), 兜底触发
                        │
                  POST agent-hub trigger
                  content = run 链接( Agent 侧技能自行拉取数据 )
                        │
              HTTP 2xx ──> ✅ 已触发(仅日志, 不写步骤摘要)
              非 2xx   ──> WARNING 不阻断(本步骤恒 exit 0)
```

- **不重复查询**： 流水线成败由 query_pipeline 传递，本 action 不调 GitCode API
- **兜底**： query_pipeline 失败(变量缺失)恰是最需要分析的时刻，兜底触发
- **异步**： trigger 后不等 Agent 结果，Test_finish 正常结束
- **幂等约定**： content 携带 run_id，Agent 侧据此去重

## 输入参数

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `owner` | 是 | 仓库所属组织/用户 |
| `repo` | 是 | 仓库名称 |
| `run_id` | 是 | 本次运行的 run_id |
| `pr_number` | 否 | PR 编号（组装分析上下文） |
| `enable` | 否 | 总开关，默认 `false`；设置为 `true` 后启用失败分析，建议接入 `vars.FAILURE_ANALYZE_ENABLE` |
| `pipeline_failed` | 否 | query_pipeline 步骤输出：`false`=成功跳过；`true`=失败触发；**缺失=其自身异常，兜底触发** |
| `session_id` | 是 | agent-hub 事件型 Session ID（预先创建，绑定失败分析 Agent） |
| `event_key` | 否 | 事件 Key，需与 Session `trigger_config.event_key` 匹配，默认 `pipeline_failed` |
| `enable_pr_comment` | 否 | **PR 评论回写开关**(默认 false)：true=要求 Agent 将分析结果回写到 PR 评论区；false=仅输出报告 |
| `enable_success_review` | 否 | **成功评论开关**(默认 false, v1.1.0)：true=流水线成功时向 PR 写入 `/ai review force` 评论(成功态 AI 审查入口)；建议接 `vars.SUCCESS_AI_REVIEW_ENABLE` |
| `git_token` | 否 | GitCode API 令牌(写 `/ai review force` 评论用, 需 PR 评论权限)；建议接 `secrets.GIT_TOKEN` |
| `agent_hub_token` | 是 | agent-hub 认证 token |
| `agent_hub_url` | 否 | agent-hub 地址，默认 `https://cannbot.hicann.cn/agent-hub` |

## 触发的 content 示例

```
分析流水线失败: cann/ops-nn (PR#10178) https://gitcode.com/cann/ops-nn/actions/runs/6b919e...
```

开启 `enable_pr_comment` 时追加一行:

```
分析结果回写到 PR#10178 评论区。
```

> 指令刻意精简——技能用法/分析流程/输出格式/回写规则均由 agent 定义(gate-analyst.md)约束, 不在 content 里重复。

> Agent 侧需具备 `gitcode-ci-api` / `gate-failure-analysis` 技能（pipeline-skill 仓库），拿到链接自行拉取数据完成分析。

## 构建与部署

```bash
npm install
npm run all          # tsc → lib/ ; ncc → dist/main.js
# 部署: 拷贝 dist/main.js + failure_analyze.py + action.yml + README.md
#       到 cann/.gitcode/actions/failure-analyze/(dist/ 下)
```

修改 `failure_analyze.py` 业务逻辑无需重新打包；修改 `index.ts` 参数处理后需 `npm run all`。

## 使用示例

```yaml
# Test_finish job 内, query_pipeline 之后
- name: Query Pipeline
  identifier: query_pipeline          # 必须有 identifier, 供 outputs 引用
  uses: cann/.gitcode/actions/query-pipeline@master
  with:
    owner: ${{ env.org_name }}
    repo: ${{ env.repo_name }}
    run_id: ${{ atomgit.workflow_run_id }}
    token: ${{ secrets.GIT_TOKEN }}
    pr_number: ${{ env.MERGE_ID }}
    apply_label: ${{ vars.APPLY_LABEL }}

- name: Failure Analyze
  identifier: failure_analyze
  uses: cann/.gitcode/actions/failure-analyze@master
  if: ${{ always() }}                # query_pipeline 失败也执行(变量缺失即兜底触发)
  with:
    owner: ${{ env.org_name }}
    repo: ${{ env.repo_name }}
    run_id: ${{ atomgit.workflow_run_id }}
    pr_number: ${{ env.MERGE_ID }}
    enable: ${{ vars.FAILURE_ANALYZE_ENABLE }}             # 总开关(未配置=不启用, 灰度仓库配 true)
    pipeline_failed: ${{ steps.query_pipeline.outputs.pipeline_failed }}
    enable_pr_comment: ${{ vars.PR_COMMENT_ENABLE }}   # 系统变量控制(未配置时默认 false)
    enable_success_review: ${{ vars.SUCCESS_AI_REVIEW_ENABLE }}  # 成功时写 /ai review force 评论(未配置=关)
    git_token: ${{ secrets.GIT_TOKEN }}                # 成功评论用 GitCode 令牌
    session_id: ${{ vars.AGENT_SESSION_ID }}            # 系统变量控制
    event_key: ${{ vars.AGENT_EVENT_KEY }}
    agent_hub_token: ${{ secrets.AGENT_HUB_TOKEN }}
```

