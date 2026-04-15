# CANN Issue 标签规则规范

> 本文档定义了 CANN 社区 Issue 的标签体系与规则，支持正则匹配和特定场景标签，用于机器人自动化管理和人工分类。

## 一、标签体系架构

### 1.1 标签分类概览

```
标签体系
├── 类型标签 (kind/*)          - Issue 类型分类
├── 优先级标签 (priority/*)     - 处理优先级
├── 状态标签                    - Issue 生命周期状态
├── 模块标签 (module/*)         - CANN 功能模块
├── SIG 标签 (sig/*)           - 兴趣小组归属
├── CI 标签 (ci-*)             - 持续集成状态
├── 环境标签 (env/*)           - 硬件/软件环境
└── 特殊标签                    - 特定场景专用
```

---

## 二、类型标签 (kind/*)

### 2.1 标签定义

| 标签 | 中文名称 | 正则匹配规则 | 描述 |
|------|----------|--------------|------|
| `kind/bug` | 缺陷 | `(?i)(bug|缺陷|错误|异常|报错|崩溃|crash|error|fail)` | 代码缺陷或功能异常 |
| `kind/feature` | 新功能 | `(?i)(feature|新功能|新特性|需求|enhancement|新增)` | 新功能开发需求 |
| `kind/documentation` | 文档 | `(?i)(doc|文档|readme|guide|指南|教程|文档)` | 文档问题或改进 |
| `kind/question` | 咨询 | `(?i)(question|咨询|疑问|如何|how to|help|求助)` | 使用咨询问题 |
| `kind/performance` | 性能 | `(?i)(performance|性能|优化|慢|卡顿|吞吐|延迟)` | 性能相关问题 |
| `kind/security` | 安全 | `(?i)(security|安全|漏洞|cve|vulnerability)` | 安全漏洞问题 |
| `kind/refactor` | 重构 | `(?i)(refactor|重构|代码优化|code clean)` | 代码重构需求 |
| `kind/test` | 测试 | `(?i)(test|测试|ut|st|冒烟|用例|coverage)` | 测试相关问题 |
| `kind/ci` | CI/CD | `(?i)(ci|流水线|门禁|编译|build|pipeline|jenkins)` | 持续集成问题 |
| `kind/duplicate` | 重复 | `(?i)(duplicate|重复|已存在)` | 与已有 Issue 重复 |
| `kind/invalid` | 无效 | `(?i)(invalid|无效|无法复现|wontfix)` | 无效或不予处理 |

### 2.2 自动打标规则

```yaml
kind-label-rules:
  - label: "kind/bug"
    match:
      title_regex: "(?i)(\\[bug\\]|bug report|缺陷反馈|报错|异常|错误)"
      body_keywords: ["报错信息", "错误日志", "异常行为", "期望结果", "实际结果"]
    templates:
      - "bug-report.yml"
      - "Bug-Report|缺陷反馈"
      
  - label: "kind/feature"
    match:
      title_regex: "(?i)(\\[feature\\]|\\[新功能\\]|feature request|需求建议|新特性)"
      body_keywords: ["新功能", "需求描述", "应用场景", "价值评估"]
    templates:
      - "feature-request.yml"
      - "Feature-Request|功能需求"
      
  - label: "kind/documentation"
    match:
      title_regex: "(?i)(\\[doc\\]|文档反馈|documentation)"
      body_keywords: ["文档链接", "问题片段", "改进建议"]
    templates:
      - "documentation.yml"
      - "Documentation|文档反馈"
      
  - label: "kind/question"
    match:
      title_regex: "(?i)(\\[question\\]|问题咨询|question)"
      body_keywords: ["问题描述", "如何", "请问"]
    templates:
      - "question.yml"
      - "Question|问题咨询"
```

---

## 三、优先级标签 (priority/*)

### 3.1 标签定义

| 标签 | 优先级 | SLA | 正则匹配规则 | 触发条件 |
|------|--------|-----|--------------|----------|
| `priority/critical` | 紧急 | 4h 响应 | `(?i)(critical|紧急|严重|阻塞|blocker|p0)` | 主流程阻塞、安全漏洞、数据丢失 |
| `priority/high` | 高 | 24h 响应 | `(?i)(high|高优先级|重要|p1)` | 核心功能异常、性能严重下降 |
| `priority/medium` | 中 | 3天 响应 | `(?i)(medium|中|一般|p2)` | 功能部分受影响、需优化 |
| `priority/low` | 低 | 7天 响应 | `(?i)(low|低|次要|p3|minor)` | 小问题、建议类 |

### 3.2 优先级判定规则

```yaml
priority-rules:
  - label: "priority/critical"
    conditions:
      - title_contains: ["紧急", "critical", "阻塞", "blocker", "P0"]
      - body_contains: ["主流程阻塞", "数据丢失", "安全漏洞", "服务不可用"]
      - module_labels: ["security", "data-loss"]
      - env_labels: ["production-down"]
    auto_assign: true
    notify_maintainers: true
    
  - label: "priority/high"
    conditions:
      - title_contains: ["高", "high", "重要", "P1"]
      - body_contains: ["核心功能", "性能下降", "无法正常使用"]
      - module_labels: ["operator", "communication", "runtime"]
      
  - label: "priority/medium"
    conditions:
      - title_contains: ["中", "medium", "P2"]
      - default_for: "kind/feature"
      
  - label: "priority/low"
    conditions:
      - title_contains: ["低", "low", "次要", "P3"]
      - default_for: ["kind/documentation", "kind/refactor"]
```

---

## 四、状态标签

### 4.1 生命周期状态标签

| 标签 | 含义 | 正则匹配 | 自动化规则 |
|------|------|----------|------------|
| `resolved` | 已解决 | - | PR 合入后自动添加 |
| `stale` | 闲置 | - | resolved 7天后无更新自动添加 |
| `wait-feedback` | 等待反馈 | - | 责任人需要更多信息时添加 |
| `confirmed` | 已确认 | - | 维护者确认问题存在 |
| `triage` | 待分类 | - | 新 Issue 默认状态 |
| `in-progress` | 处理中 | `(?i)(处理中|进行中|开发中|in progress)` | 指派负责人后自动添加 |

### 4.2 状态转换规则

```yaml
state-transitions:
  resolved-management:
    label_resolve: "resolved"
    label_stale: "stale"
    label_wait_feedback: "wait-feedback"
    
    resolve_to_stale_days: 7
    stale_to_close_days: 14
    wait_feedback_to_warn_days: 7
    wait_feedback_to_close_days: 14
    
    auto_actions:
      - trigger: "pr_merged"
        action: "add_label"
        label: "resolved"
        
      - trigger: "resolved_7d_no_update"
        action: "add_label_and_comment"
        label: "stale"
        comment_template: "stale_comment"
        
      - trigger: "user_comment_on_stale"
        action: "remove_labels"
        labels: ["stale", "resolved"]
        
      - trigger: "stale_14d_no_update"
        action: "close_issue"
        comment_template: "stale_close_comment"

  feedback-management:
    - trigger: "maintainer_need_info"
      action: "add_label"
      label: "wait-feedback"
      
    - trigger: "author_comment_on_wait_feedback"
      action: "remove_label"
      label: "wait-feedback"
      
    - trigger: "wait_feedback_7d_no_response"
      action: "add_warning_comment"
      comment_template: "wait_feedback_warn_comment"
      
    - trigger: "wait_feedback_14d_no_response"
      action: "close_issue"
      comment_template: "wait_feedback_close_comment"
```

---

## 五、模块标签 (module/*)

### 5.1 CANN 功能模块标签

| 标签 | 模块名称 | 正则匹配规则 | 负责仓库 | CIE 联系人 |
|------|----------|--------------|----------|------------|
| `module/operator` | 算子 | `(?i)(算子|operator|op_|ops-)` | cann/opbase, cann/ops-* | @songkai111 |
| `module/communication` | 通信 | `(?i)(通信|hccl|hcomm|collective|allreduce|allgather)` | cann/hccl, cann/hcomm | @jiyuanhao |
| `module/graph` | 图编译 | `(?i)(图|graph|fusion|算子融合|atc)` | cann/graph-autofusion | @jikai-tyler |
| `module/runtime` | 运行时 | `(?i)(运行时|runtime|acl|执行)` | cann/runtime | @duanpengliang |
| `module/driver` | 驱动 | `(?i)(驱动|driver|npu|设备)` | cann/driver | @ad_cx |
| `module/ascendc` | AscendC | `(?i)(ascendc|asc-devkit|asc-tools|算子开发)` | cann/asc-devkit | @DragonBornHD84 |
| `module/pto` | PTO | `(?i)(pto|pypto|tile|性能优化)` | cann/pto-*, cann/pypto | @y30038433 |
| `module/tool` | 工具 | `(?i)(工具|tool|amct|oam|转换|量化)` | cann/amct, cann/oam-tools | @RQL7 |
| `module/model` | 模型 | `(?i)(模型|model|recipe|推理|训练)` | cann/cann-recipes-* | @rous_zhang |
| `module/extension` | 扩展 | `(?i)(扩展|extension|boost|shmem|catlass)` | cann/ascend-boost-* | @overfitting_zh |

### 5.2 模块自动匹配规则

```yaml
module-label-rules:
  - label: "module/operator"
    match:
      title_regex: "(?i)(算子|operator|op_|ops-)"
      body_keywords: ["算子名称", "算子类型", "op实现", "kernel"]
      file_patterns: ["**/ops-*", "**/operator/**", "**/*_op.*"]
      
  - label: "module/communication"
    match:
      title_regex: "(?i)(通信|hccl|hcomm|collective|allreduce|allgather|broadcast)"
      body_keywords: ["HCCL", "HCOMM", "集合通信", "通信域", "AllReduce", "AllGather"]
      file_patterns: ["**/hccl/**", "**/hcomm/**", "**/communication/**"]
      
  - label: "module/graph"
    match:
      title_regex: "(?i)(图|graph|fusion|算子融合|atc|om)"
      body_keywords: ["图编译", "算子融合", "ATC", "OM模型", "离线模型"]
      file_patterns: ["**/graph/**", "**/fusion/**", "**/atc/**"]
      
  - label: "module/runtime"
    match:
      title_regex: "(?i)(运行时|runtime|acl|执行|推理)"
      body_keywords: ["ACL", "运行时", "推理执行", "内存管理"]
      file_patterns: ["**/runtime/**", "**/acl/**"]
```

---

## 六、SIG 标签 (sig/*)

### 6.1 兴趣小组标签

| 标签 | SIG 名称 | 职责范围 | 联系方式 |
|------|----------|----------|----------|
| `sig/infrastructure` | 基础设施 | CI/CD、机器人、社区服务 | infrastructure@opencode.ai |
| `sig/operator` | 算子开发 | 算子库开发与维护 | operator-sig@opencode.ai |
| `sig/performance` | 性能优化 | 性能分析与调优 | performance-sig@opencode.ai |
| `sig/security` | 安全 | 安全漏洞修复与防护 | security@opencode.ai |
| `sig/documentation` | 文档 | 文档编写与翻译 | docs-sig@opencode.ai |

### 6.2 SIG 标签规则

```yaml
sig-label-rules:
  - label: "sig/infrastructure"
    match:
      title_regex: "(?i)(ci|流水线|门禁|机器人|robot|cla|邮件列表)"
      templates: ["ci_issue_template.yml"]
      
  - label: "sig/operator"
    match:
      module_labels: ["module/operator", "module/ascendc"]
      
  - label: "sig/performance"
    match:
      kind_labels: ["kind/performance"]
      module_labels: ["module/pto"]
```

---

## 七、CI 标签 (ci-*)

### 7.1 持续集成状态标签

| 标签 | 含义 | 触发条件 | 自动化命令 |
|------|------|----------|------------|
| `ci-pipeline-passed` | 流水线通过 | `/compile` 执行成功 | 自动添加 |
| `ci-pipeline-failed` | 流水线失败 | `/compile` 执行失败 | 自动添加 |
| `st-success` | 冒烟通过 | `/system-test` 执行成功 | 自动添加 |
| `st-fail` | 冒烟失败 | `/system-test` 执行失败 | 自动添加 |
| `ascend-cla/yes` | CLA 已签署 | CLA 检查通过 | 自动添加 |
| `ascend-cla/no` | CLA 未签署 | CLA 检查未通过 | 自动添加 |
| `api_check_failed` | API 检查失败 | API 兼容性检查异常 | 自动添加 |
| `lgtm` | 评审通过 | `/lgtm` | 人工触发 |
| `approved` | 同意合入 | `/approve` | 人工触发 |
| `keeper_approved` | 守护者审核通过 | `/merge` | 人工触发 |

### 7.2 CI 标签规则

```yaml
ci-label-rules:
  pipeline:
    trigger_command: "/compile"
    success_label: "ci-pipeline-passed"
    failure_label: "ci-pipeline-failed"
    related_commands:
      - "/retry"
      - "/stop"
      - "/get-log"
      
  smoke_test:
    trigger_command: "/system-test"
    success_label: "st-success"
    failure_label: "st-fail"
    applicable_repos: ["MindIE-SD"]
    
  cla:
    trigger_command: "/check-cla"
    success_label: "ascend-cla/yes"
    failure_label: "ascend-cla/no"
    cancel_command: "/cla cancel"
    
  review:
    lgtm:
      add_command: "/lgtm"
      cancel_command: "/lgtm cancel"
    approve:
      add_command: "/approve"
      cancel_command: "/approve cancel"
    merge_check:
      trigger_command: "/check-pr"
      required_labels: ["lgtm", "approved", "ascend-cla/yes"]
```

---

## 八、环境标签 (env/*)

### 8.1 硬件环境标签

| 标签 | 硬件型号 | 正则匹配 |
|------|----------|----------|
| `env/ascend910b` | Ascend 910B | `(?i)(910b|ascend910b|910-b)` |
| `env/ascend910` | Ascend 910 | `(?i)(910[^b]|ascend910[^b])` |
| `env/ascend310p` | Ascend 310P | `(?i)(310p|ascend310p|310-p)` |
| `env/ascend310` | Ascend 310 | `(?i)(310[^p]|ascend310[^p])` |

### 8.2 软件环境标签

| 标签 | 环境 | 正则匹配 |
|------|------|----------|
| `env/cann-8.5` | CANN 8.5.x | `(?i)(cann.?8\\.5|8\\.5\\.\\d+)` |
| `env/cann-8.0` | CANN 8.0.x | `(?i)(cann.?8\\.0|8\\.0\\.\\d+)` |
| `env/ubuntu` | Ubuntu 系统 | `(?i)(ubuntu)` |
| `env/centos` | CentOS 系统 | `(?i)(centos|rhel)` |
| `env/pytorch` | PyTorch 框架 | `(?i)(pytorch|torch)` |
| `env/tensorflow` | TensorFlow 框架 | `(?i)(tensorflow|tf)` |

### 8.3 环境标签规则

```yaml
env-label-rules:
  hardware:
    - label: "env/ascend910b"
      match:
        body_regex: "(?i)(910b|ascend.?910b|910-b)"
        
    - label: "env/ascend310p"
      match:
        body_regex: "(?i)(310p|ascend.?310p|310-p)"
        
  software:
    - label: "env/cann-8.5"
      match:
        body_regex: "(?i)(cann.?8\\.5|版本:?\\s*8\\.5)"
        
    - label: "env/pytorch"
      match:
        body_regex: "(?i)(pytorch|torch|pt)"
```

---

## 九、特殊场景标签

### 9.1 任务认领标签

| 标签 | 场景 | 描述 |
|------|------|------|
| `help wanted` | 任务认领 | 适合社区开发者认领的任务 |
| `good first issue` | 新手任务 | 适合新手贡献者的简单任务 |
| `contribution welcome` | 欢迎贡献 | 欢迎社区贡献的功能点 |

### 9.2 特殊处理标签

| 标签 | 场景 | 自动化行为 |
|------|------|------------|
| `no-stale` | 禁止闲置 | 不会自动标记为 stale |
| `pinned` | 置顶 | 不会被自动关闭 |
| `workaround-available` | 有临时方案 | 已有临时规避方法 |

### 9.3 特殊场景规则

```yaml
special-label-rules:
  help_wanted:
    trigger_template: "help-wanted.yml"
    auto_labels:
      - "help wanted"
    difficulty_levels:
      - label: "good first issue"
        conditions: ["difficulty: 新手友好"]
      - label: "contribution welcome"
        conditions: ["difficulty: 中等难度", "difficulty: 高级挑战"]
        
  no_stale:
    conditions:
      - has_label: ["no-stale", "pinned", "priority/critical"]
    actions:
      skip_stale_check: true
      skip_auto_close: true
```

---

## 十、机器人命令速查

### 10.1 标签管理命令

| 命令 | 功能 | 示例 |
|------|------|------|
| `/label add <label>` | 添加标签 | `/label add kind/bug` |
| `/label remove <label>` | 移除标签 | `/label remove kind/question` |
| `/kind <type>` | 设置类型 | `/kind bug` |
| `/priority <level>` | 设置优先级 | `/priority high` |
| `/sig <name>` | 设置 SIG | `/sig infrastructure` |
| `/module <name>` | 设置模块 | `/module operator` |

### 10.2 CI 相关命令

| 命令 | 功能 | 场景 |
|------|------|------|
| `/compile` | 触发编译流水线 | PR 提交后 |
| `/system-test` | 触发冒烟测试 | 编译通过后 |
| `/get-log` | 获取构建日志 | 排查问题时 |
| `/retry` | 重试失败流水线 | 偶发失败时 |
| `/stop` | 停止流水线 | 需要中断时 |
| `/check-cla` | 检查 CLA 状态 | CLA 签署验证 |

### 10.3 评审与合并命令

| 命令 | 功能 | 结果标签 |
|------|------|----------|
| `/lgtm` | 标记评审通过 | `lgtm` |
| `/lgtm cancel` | 取消评审通过 | 移除 `lgtm` |
| `/approve` | 同意合入 | `approved` |
| `/approve cancel` | 取消合入同意 | 移除 `approved` |
| `/merge` | 守护者审核 | `keeper_approved` |
| `/check-pr` | 检查并合并 | 自动合并 |
| `/assign` | 指派负责人 | - |
| `/unassign` | 取消指派 | - |

---

## 十一、配置文件示例

### 11.1 bot-issue-manage.yaml 完整配置

```yaml
bot-issue-manage:
  # 标签名称配置
  label_resolve: "resolved"
  label_stale: "stale"
  label_wait_feedback: "wait-feedback"
  
  # 时间配置（天）
  resolve_to_stale_days: 7
  stale_to_close_days: 14
  wait_feedback_to_warn_days: 7
  wait_feedback_to_close_days: 14

  # 评论内容
  stale_comment: |
    您好，当前 Issue 标记为 resolved 且有一段时间未进一步更新，因此我们将其标记为 'stale'（闲置）状态。
    若您认为这是误操作，可通过添加任意评论来去除 'stale' 标签。
    标记为 stale 的 Issue 在 14 天内无更新活动将自动关闭。
    
  wait_feedback_warn_comment: |
    您好，为了更准确地定位和解决问题，我们需要您提供上述提到的相关信息。
    如果 14 天内没有进一步更新，我们将暂时关闭此 Issue。
    感谢您的理解与配合。
    
  wait_feedback_close_comment: |
    您好，由于该 Issue 已有一段时间没有更新，我们先将其关闭。
    如果您后续有新的进展或诉求，欢迎随时重新开启此 Issue 或提交新的 Issue，我们会继续为您跟进。

# 标签自动匹配规则
label-auto-match:
  kind_labels:
    - pattern: "(?i)(\\[bug\\]|bug|缺陷|报错|异常|错误)"
      label: "kind/bug"
    - pattern: "(?i)(\\[feature\\]|feature|新功能|需求|enhancement)"
      label: "kind/feature"
    - pattern: "(?i)(\\[doc\\]|doc|文档|readme|guide)"
      label: "kind/documentation"
    - pattern: "(?i)(\\[question\\]|question|咨询|疑问|如何)"
      label: "kind/question"
    - pattern: "(?i)(performance|性能|优化|慢|卡顿)"
      label: "kind/performance"
      
  priority_labels:
    - pattern: "(?i)(critical|紧急|严重|阻塞|blocker|p0)"
      label: "priority/critical"
    - pattern: "(?i)(high|高优先级|重要|p1)"
      label: "priority/high"
    - pattern: "(?i)(medium|中|一般|p2)"
      label: "priority/medium"
    - pattern: "(?i)(low|低|次要|p3)"
      label: "priority/low"
      
  module_labels:
    - pattern: "(?i)(算子|operator|op_|ops-)"
      label: "module/operator"
    - pattern: "(?i)(通信|hccl|hcomm|collective|allreduce)"
      label: "module/communication"
    - pattern: "(?i)(图|graph|fusion|算子融合|atc)"
      label: "module/graph"
    - pattern: "(?i)(运行时|runtime|acl)"
      label: "module/runtime"
    - pattern: "(?i)(驱动|driver|npu)"
      label: "module/driver"
      
  env_labels:
    - pattern: "(?i)(910b|ascend910b|910-b)"
      label: "env/ascend910b"
    - pattern: "(?i)(310p|ascend310p|310-p)"
      label: "env/ascend310p"
    - pattern: "(?i)(cann.?8\\.5|版本:?\\s*8\\.5)"
      label: "env/cann-8.5"

# 模板到标签映射
template-label-mapping:
  "bug-report.yml":
    - "kind/bug"
    - "triage"
  "feature-request.yml":
    - "kind/feature"
    - "triage"
  "documentation.yml":
    - "kind/documentation"
    - "triage"
  "question.yml":
    - "kind/question"
    - "triage"
  "help-wanted.yml":
    - "help wanted"
    - "triage"
  "security-issue.yml":
    - "kind/security"
    - "priority/critical"
    - "sig/security"
```

---

## 十二、最佳实践

### 12.1 Issue 创建建议

1. **选择正确的模板**：根据 Issue 类型选择对应模板
2. **标题规范**：使用 `[标签] 描述` 格式，如 `[Bug] AllReduce 算子执行失败`
3. **提供完整信息**：
   - 昇腾硬件型号
   - CANN 版本
   - 操作系统
   - 框架版本
   - 完整错误日志
   - 最小复现步骤

### 12.2 标签使用建议

1. **至少一个类型标签**：每个 Issue 必须有 `kind/*` 标签
2. **优先级标签**：影响用户使用的问题应标注优先级
3. **模块标签**：明确问题的功能模块归属
4. **环境标签**：特定环境的问题标注环境标签

### 12.3 机器人交互建议

1. **及时响应反馈请求**：`wait-feedback` 状态的 Issue 应在 14 天内回复
2. **使用命令触发 CI**：使用 `/compile` 等命令而非手动触发
3. **评审流程**：遵循 `/lgtm` -> `/approve` -> `/check-pr` 的评审流程

---

## 十三、参考资源

- [CANN 官方文档](https://www.hiascend.com/cann/document)
- [Infrastructure 仓库](https://gitcode.com/cann/infrastructure)
- [Robot 能力列表](https://gitcode.com/cann/infrastructure/blob/main/docs/robot/robot能力列表.md)
- [CI 工程检查项概览](https://gitcode.com/cann/infrastructure/blob/main/docs/ci/ci_guide.md)
- [服务支撑矩阵](https://gitcode.com/cann/infrastructure/blob/main/docs/services.md)

---

**文档版本**: v1.0  
**最后更新**: 2026-04-11  
**维护者**: Infrastructure SIG
