# CANN Issue 标签规则规范

> Issue 标签体系与自动化规则，用于机器人管理 Issue 生命周期。

---

## 一、标签分类

| 分类 | 前缀 | 用途 |
|------|------|------|
| 类型 | `kind/*` | Issue 类型分类 |
| 状态 | 无前缀 | 生命周期状态 |
| 模块 | `module/*` | CANN 功能模块 |
| SIG | `sig/*` | 兴趣小组归属 |
| CI | `ci-*` | CI 状态标记 |
| 环境 | `env/*` | 硬件/软件环境 |
| 特殊 | 无前缀 | 特定场景专用 |

---

## 二、类型标签 (kind/*)

| 标签 | 匹配关键词 | 说明 |
|------|-----------|------|
| `kind/bug` | bug, 缺陷, 错误, crash, error | 代码缺陷 |
| `kind/feature` | feature, 新功能, 需求 | 新功能需求 |
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
| `module/operator` | 算子 | 算子, operator, ops- | @songkai111 |
| `module/communication` | 通信 | hccl, hcomm, allreduce | @jiyuanhao |
| `module/graph` | 图编译 | graph, fusion, atc | @jikai-tyler |
| `module/runtime` | 运行时 | runtime, acl | @duanpengliang |
| `module/driver` | 驱动 | driver, npu | @ad_cx |
| `module/ascendc` | AscendC | ascendc, asc-devkit | @DragonBornHD84 |
| `module/pto` | PTO | pto, pypto, tile | @y30038433 |
| `module/tool` | 工具 | tool, amct, oam | @RQL7 |
| `module/model` | 模型 | model, recipe | @rous_zhang |
| `module/extension` | 扩展 | extension, boost | @overfitting_zh |

---

## 五、SIG 标签 (sig/*)

| 标签 | SIG 名称 | 职责 |
|------|----------|------|
| `sig/infrastructure` | 基础设施 | CI/CD、机器人 |
| `sig/operator` | 算子开发 | 算子库维护 |
| `sig/performance` | 性能优化 | 性能调优 |
| `sig/security` | 安全 | 安全漏洞修复 |
| `sig/documentation` | 文档 | 文档编写翻译 |

---

## 六、CI 标签 (ci-*)

| 标签 | 含义 | 触发命令 |
|------|------|----------|
| `ci-pipeline-passed` | 编译通过 | `/compile` 成功 |
| `ci-pipeline-failed` | 编译失败 | `/compile` 失败 |
| `st-success` | 冒烟通过 | `/system-test` 成功 |
| `st-fail` | 冒烟失败 | `/system-test` 失败 |
| `ascend-cla/yes` | CLA 已签 | CLA 检查通过 |
| `ascend-cla/no` | CLA 未签 | CLA 检查失败 |
| `lgtm` | 评审通过 | `/lgtm` |
| `approved` | 同意合入 | `/approve` |

---

## 七、环境标签 (env/*)

### 硬件

| 标签 | 型号 |
|------|------|
| `env/ascend910b` | Ascend 910B |
| `env/ascend910` | Ascend 910 |
| `env/ascend310p` | Ascend 310P |
| `env/ascend310` | Ascend 310 |

### 软件

| 标签 | 环境 |
|------|------|
| `env/cann-8.5` | CANN 8.5.x |
| `env/cann-8.0` | CANN 8.0.x |
| `env/ubuntu` | Ubuntu |
| `env/centos` | CentOS |
| `env/pytorch` | PyTorch |
| `env/tensorflow` | TensorFlow |

---

## 八、特殊标签

| 标签 | 用途 |
|------|------|
| `help wanted` | 适合社区认领 |
| `good first issue` | 新手友好任务 |
| `no-stale` | 禁止标记 stale |
| `pinned` | 置顶，不自动关闭 |
| `workaround-available` | 有临时方案 |

---

## 九、机器人命令

### 标签管理

| 命令 | 功能 | 示例 |
|------|------|------|
| `/label add <label>` | 添加标签 | `/label add kind/bug` |
| `/label remove <label>` | 移除标签 | `/label remove kind/question` |
| `/kind <type>` | 设置类型 | `/kind bug` |
| `/module <name>` | 设置模块 | `/module operator` |
| `/sig <name>` | 设置 SIG | `/sig operator` |

### CI 触发

| 命令 | 功能 |
|------|------|
| `/compile` | 触发编译 |
| `/system-test` | 触发冒烟测试 |
| `/get-log` | 获取构建日志 |
| `/retry` | 重试失败流水线 |
| `/stop` | 停止流水线 |
| `/check-cla` | 检查 CLA |

### 评审合并

| 命令 | 功能 | 标签 |
|------|------|------|
| `/lgtm` | 评审通过 | `lgtm` |
| `/approve` | 同意合入 | `approved` |
| `/check-pr` | 检查并合并 | 自动合并 |
| `/assign` | 指派负责人 | - |

---

## 十、配置示例

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
    - pattern: "(?i)(feature|新功能|需求)"
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
  "security-issue.yml": ["kind/security", "sig/security"]
```

---

## 十一、最佳实践

### Issue 创建

1. **标题规范**: `[类型] 描述`，如 `[Bug] AllReduce 执行失败`
2. **必填信息**: 硬件型号、CANN 版本、错误日志、复现步骤
3. **选择模板**: 根据类型选择对应模板

### 标签使用

1. 至少一个 `kind/*` 标签
2. 指明模块归属 `module/*`
3. 特定环境标注 `env/*`

---

**文档版本**: v2.1  
**最后更新**: 2026-04-15  
**维护者**: Infrastructure SIG