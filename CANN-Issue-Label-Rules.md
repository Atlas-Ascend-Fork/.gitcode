# CANN Issue 标签规则规范

> Issue 标签体系与自动化规则，用于机器人管理 Issue 生命周期。

---

## 一、标签分类

| 分类 | 前缀 | 用途 |
|------|------|------|
| 类型 | `kind/*` | Issue 类型分类 |
| 状态 | 无前缀 | 生命周期状态 |
| 模块 | `module/*` | CANN 功能模块 |
| 特殊 | 无前缀 | 特定场景专用 |

---

## 二、类型标签 (kind/*)

| 标签 | 匹配关键词 | 说明 |
|------|-----------|------|
| `kind/bug` | bug, 缺陷, 错误, crash, error | 代码缺陷 |
| `kind/feature` | feature, 新功能 | 新功能需求 |
| `kind/documentation` | doc, 文档, readme | 文档问题 |
| `kind/question` | question, 咨询, 如何 | 使用咨询 |
| `kind/performance` | performance, 性能, 慢 | 性能问题 |
| `kind/security` | security, 安全, 漏洞, cve | 安全漏洞 |
| `kind/refactor` | refactor, 重构 | 代码重构 |
| `kind/test` | test, 测试, ut, st | 测试相关 |
| `kind/ci` | ci, 流水线, 编译, build | CI 问题 |
| `kind/duplicate` | duplicate, 重复 | 重复 Issue |
| `kind/invalid` | invalid, 无效, wontfix | 无效 Issue |

---

## 三、状态标签

| 标签 | 含义 | 自动触发条件 |
|------|------|-------------|
| `triage` | 待分类 | 新 Issue 默认 |
| `confirmed` | 已确认 | 维护者确认 |
| `in-progress` | 处理中 | 指派负责人 |
| `resolved` | 已解决 | PR 合入 |
| `stale` | 闲置 | resolved 7天无更新 |
| `wait-feedback` | 等待反馈 | 需要更多信息 |

### 状态转换规则

```
新建 → triage → confirmed → in-progress → resolved → stale → closed
                          ↓
                    wait-feedback (14天无回复自动关闭)
```

---

## 四、模块标签 (module/*)

| 标签 | 模块 | 匹配关键词 | 联系人 |
|------|------|-----------|--------|
| `module/ops` | 算子 | 算子, operator, ops- | @songkai111 |
| `module/hccl` | 通信 | hccl, hcomm, allreduce | @jiyuanhao |
| `module/ge` | 图编译 | graph, fusion, atc | @jikai-tyler |
| `module/runtime` | 运行时 | runtime, acl | @duanpengliang |
| `module/driver` | 驱动 | driver, npu | @ad_cx |
| `module/ascendc` | AscendC | ascendc, asc-devkit | @DragonBornHD84 |
| `module/pto` | PTO | pto, pypto, tile | @y30038433 |
| `module/tool` | 工具 | tool, amct, oam | @RQL7 |
| `module/model` | 模型 | model, recipe | @rous_zhang |
| `module/extension` | 扩展 | extension, boost | @overfitting_zh |

---

## 五、特殊标签

| 标签 | 用途 |
|------|------|
| `help-wanted` | 适合社区认领 |
| `good-first-issue` | 新手友好任务 |
| `no-stale` | 禁止标记 stale |
| `pinned` | 置顶，不自动关闭 |
| `workaround-available` | 有临时方案 |

---

## 六、配置示例

```yaml
bot-issue-manage:
  label_resolve: "resolved"
  label_stale: "stale"
  label_wait_feedback: "wait-feedback"
  
  resolve_to_stale_days: 7
  stale_to_close_days: 14
  wait_feedback_to_warn_days: 7
  wait_feedback_to_close_days: 14

label-auto-match:
  kind_labels:
    - pattern: "(?i)(bug|缺陷|错误)"
      label: "kind/bug"
    - pattern: "(?i)(feature|新功能)"
      label: "kind/feature"
    - pattern: "(?i)(doc|文档)"
      label: "kind/documentation"
      
  module_labels:
    - pattern: "(?i)(算子|operator)"
      label: "module/operator"
    - pattern: "(?i)(hccl|通信)"
      label: "module/communication"

template-label-mapping:
  "bug-report.yml": ["kind/bug", "triage"]
  "feature-request.yml": ["kind/feature", "triage"]
  "question.yml": ["kind/question", "triage"]
  "security-issue.yml": ["kind/security", "triage"]
```

---

## 七、最佳实践

### Issue 创建

1. **标题规范**: `[类型] 描述`，如 `[Bug] AllReduce 执行失败`
2. **必填信息**: 硬件型号、CANN 版本、错误日志、复现步骤
3. **选择模板**: 根据类型选择对应模板

### 标签使用

1. 至少一个 `kind/*` 标签
2. 指明模块归属 `module/*`

---

**文档版本**: v2.1  
**最后更新**: 2026-04-15  
**维护者**: Infrastructure SIG