# Pipeline Agent — 门禁流水线智能定界与定位需求方案

---

## 1. 背景与问题

### 1.1 现状

CANN 门禁流水线（GitCode Action）覆盖编译、UT、ST、静态检查、PreSmoke 等阶段，单次 PR 触发 **20-50 个 Job**。失败后开发者需要：

1. 打开 GitCode Action 页面，逐个查看失败 Job
2. 下载或浏览日志（单 Job 日志可达 **数万行**，如 ops-transformer UT 日志 10664 行）
3. 人工定位错误行、判断根因
4. 决定是改代码、改 CI 配置、还是重试

**平均定位耗时 15-30 分钟**，且高度依赖经验。

### 1.2 痛点总结

| 痛点 | 影响 |
|------|------|
| 日志量大，人工搜索慢 | 单 Job 日志可达 1 万+ 行，定位 1 行错误 |
| 失败模式重复但无积累 | 同类问题每次从头分析，无知识沉淀 |
| 失败分类粗糙 | 只知道 FAILED，不知是代码/环境/CI配置/网络 |
| 失败归因困难 | 看到 error 不等于找到根因，真正的触发点可能在 error 之前 |
| 重试盲目 | 不知道上次失败是否已修复，不知道本次新增了什么问题 |
| 无复现路径 | 知道哪个用例失败了，但不知道如何在本地快速复现 |

---

## 2. 目标

| # | 目标 | 衡量标准 |
|---|------|---------|
| G1 | **自动定界**：流水线失败后 1 分钟内输出根因定位 | 覆盖 80%+ 常见失败模式 |
| G2 | **自动分类**：区分代码问题/环境问题/CI配置问题 | 分类准确率 90%+ |
| G3 | **自动反馈**：结果推送到 GitCode PR 评论 + 标签 | 无需人工打开 Action 页面 |
| G4 | **因果关联**：定位到 PR 变更的具体代码行 | 回答"改了什么导致失败" |
| G5 | **增量对比**：同 PR 多次执行时只报告新增/已修复的变化 | 减少重复噪音 |
| G6 | **经验复用**：历史失败模式形成知识库，推荐已验证方案 | 命中率随时间递增 |

---

## 3. 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                     GitCode Action 流水线                        │
│                                                                 │
│  stage1: PreBuild → stage2: Compile → stage3: UT → stage4: ...  │
│                                                                 │
│  [Job A] [Job B] [Job C]  ...  [Job X] ❌ FAILED               │
│                                                                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                    post: if: failure()
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Pipeline Agent (ai-triage)                    │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ 1. 日志   │→│ 2. 规则   │→│ 3. LLM    │→│ 4. 知识库 │       │
│  │    获取   │  │    引擎   │  │    分析   │  │    匹配   │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
│       │              │              │              │            │
│       ▼              ▼              ▼              ▼            │
│  download-logs   正则匹配      截取上下文     语义匹配           │
│  GitCode API     30+ 模式      调 LLM API    历史case           │
│                                                                 │
│  ┌──────────────────────────────────────────────────────┐       │
│  │              5. 智能定界（5 大能力）                   │       │
│  │  ├─ 5.1 变更-失败因果关联（PR diff × 失败用例）        │       │
│  │  ├─ 5.2 增量定界（同 PR 多次 Run 对比）               │       │
│  │  ├─ 5.3 错误链回溯（error → warning 反向追溯）        │       │
│  │  ├─ 5.4 最小重现路径提取（生成可复现命令）             │       │
│  │  └─ 5.5 相似故障推荐（知识库经验复用）                 │       │
│  └──────────────────────────────────────────────────────┘       │
│                           │                                     │
│                           ▼                                     │
│  ┌──────────────────────────────────────────────────────┐       │
│  │              6. 反馈到 GitCode                        │       │
│  │  ├─ PR 评论（定界报告 + 因果分析 + 复现命令）          │       │
│  │  ├─ Label 打标（ci-fail-code/env/ci-config/timeout）  │       │
│  │  └─ @ 相关人员（代码问题@提交者，CI问题@维护者）        │       │
│  └──────────────────────────────────────────────────────┘       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. 基础能力设计

### 4.1 触发机制

在流水线 `post` 阶段自动触发，无需人工干预：

```yaml
post:
  jobs:
    job_post:
      name: Pipeline-Agent
      steps:
        - name: ai-triage
          if: ${{ failure() }}
          uses: cann/.gitcode/actions/ai-triage@master
          with:
            run_id: ${{ atomgit.event.action.run_id }}
            repo_name: ${{ env.repo_name }}
            pr_id: ${{ env.MERGE_ID }}
            token: ${{ secrets.GIT_TOKEN }}
      runs-on: ["self-hosted", "arch=x64", "spec=small"]
```

### 4.2 日志获取

复用已有的 `download-logs` 能力，仅下载失败 Job 日志：

```
1. 调 GitCode API: GET /repos/:owner/:repo/actions/runs/:run_id/jobs
2. 筛选 status=FAILED 的 Job
3. 对每个失败 Job: GET .../jobs/:job_id/download_log
4. 解压日志，提取文本
```

**优化**：跳过 `workflow_call` 类型 Job（无实际日志），只下载 `normal` 类型。

### 4.3 失败分类规则引擎

基于真实案例提炼的 **7 大类 30+ 模式**：

| 类别 | 标签 | 模式（正则/关键词） | 典型案例 |
|------|------|-------------------|---------|
| **代码逻辑** | `ci-fail-code` | `FAILED.*Test`、`assert.*expected`、`tilingRet`、`Segmentation fault`、`core dump` | ops-transformer tiling 失败 |
| **CI配置** | `ci-fail-config` | `ModuleNotFoundError`、`permission.*invalid`、`No such file`、`command not found`、`PACKAGE_URL` | pypto 包路径错误、权限校验 |
| **环境超时** | `ci-fail-timeout` | `SIGTERM`、`signal.*TERM`、`timed out`、`TimeoutExpired` | cannbot-knowledge check-pr 被杀 |
| **网络问题** | `ci-fail-network` | `getaddrinfo.*failed`、`Connection refused`、`download.*failed`、`404.*Not Found` | hcomm mockcpp 下载失败 |
| **设备/NPU** | `ci-fail-device` | `rtSetDevice.*invalid`、`devId.*invalid`、`AICore.*error`、`device.*not found` | pypto device id 越界 |
| **依赖缺失** | `ci-fail-dependency` | `No module named`、`library not found`、`undefined reference`、`cannot find -l` | 编译依赖缺失 |
| **其他** | `ci-fail-unknown` | 未命中以上模式 | 转 LLM 分析 |

**规则引擎伪代码**：

```python
PATTERNS = [
    # (category, regex_pattern, extract_group, suggestion_template)
    ("code",     r"\[FAILED\].*Test",              None,   "测试用例失败，请检查代码逻辑"),
    ("code",     r"tilingRet.*Which is: (\d+)",     1,     "tiling 返回值 {0}，期望 0，检查 tiling 边界条件"),
    ("config",   r"ModuleNotFoundError: '(\w+)'",   1,     "Python 模块 {0} 未安装，检查 pre_smoke.sh 或 build_ci.py"),
    ("config",   r"permission is invalid",          None,   "目录权限校验失败，检查安装路径属主"),
    ("timeout",  r"signal.*SIGTERM",                None,   "进程被超时杀死，建议增加 step timeout-minutes"),
    ("timeout",  r"signal.*SIGKILL",                None,   "进程被 OOM Killer 杀死，检查内存或增加 runner 规格"),
    ("network",  r"getaddrinfo.*failed.*for (\S+)", 1,     "DNS 解析失败: {0}，检查网络/DNS 配置"),
    ("network",  r"download.*failed.*'(\S+)'",      1,     "下载失败: {0}，检查 URL 或预缓存依赖"),
    ("device",   r"devId is invalid.*Expected.*\[0, (\d+)\)", 1, "device id 越界，有效范围 [0, {0})"),
    ("dependency", r"No module named '(\w+)'",      1,     "缺少 Python 模块 {0}"),
    ("dependency", r"cannot find -l(\S+)",          1,     "缺少链接库 {0}"),
]
```

### 4.4 LLM 智能分析（兜底）

规则引擎未命中时，截取日志中 error 上下文（±50 行），调用 LLM 分析：

```
输入（Prompt 模板）：
你是 CANN 流水线失败分析专家。以下是流水线 Job 的失败日志片段，请分析：
Job 名称：{job_name}  仓库：{repo_name}  分支：{branch}
日志片段（error 上下文）：
{error_context}
请输出 JSON：{ category, root_cause, evidence, suggestion, confidence }
```

**成本控制**：仅对规则未命中的 case 调 LLM（预计 20-30%），截取 error 上下文限制 token < 4K。

### 4.5 知识库匹配

历史失败分析结果存入知识库，新失败先做语义匹配：

```json
{
  "cases": [
    {
      "id": "case_001",
      "pattern": "ModuleNotFoundError: No module named 'pypto'",
      "category": "config",
      "root_cause": "包未安装，下载 URL 路径错误",
      "suggestion": "检查 pre_smoke.sh 中的包下载路径",
      "solution_pr": "https://gitcode.com/cann/pypto/pulls/5496",
      "resolved_by": "tanghaoran7",
      "occurrences": 3
    }
  ]
}
```

---

## 5. 智能定界核心能力（5 大创新点）

### 5.1 变更-失败因果关联

> 回答"**你改了什么导致这个失败**"

#### 问题

当前定界只能告诉"tiling_13 失败了"，开发者还要自己去找"我改了哪行代码导致 tiling_13 失败"。

#### 方案

```
PR 变更文件（pr_filelist.txt + git diff）
  │
  ├─ 文件名/用例名关联:
  │   失败用例: "SparseFlashAttentionTiling.SparseFlashAttention_910b_tiling_13"
  │   变更文件: "op_host/arch35/sparse_flash_attention_tiling.cpp"
  │   → 关键词 "sparse_flash_attention" + "tiling" 匹配度 0.95
  │
  ├─ git diff 行级关联:
  │   变更: sparse_flash_attention_tiling.cpp 第 87 行新增 LSE 分支
  │   失败: tiling_13 的输入走到 LSE 分支后返回 -1
  │   → 定位到具体代码行
  │
  └─ 历史基线对比:
      master 分支 tiling_13 通过 → PR 引入变更后失败 → 确认是 PR 导致
```

#### 输出示例

```
🔍 因果关联分析:
  失败用例 SparseFlashAttention_910b_tiling_13
  与你修改的 sparse_flash_attention_tiling.cpp 强相关（匹配度 0.95）

  变更位置: 第 87 行，新增 LSE 分支处理
  失败原因: tiling_13 的输入参数走到 LSE 分支后 tilingRet 返回 -1

  建议: 检查 LSE 分支的 boundary_input_idx 范围判断，
        tiling_13 的输入可能不在 LSE 分支预期的处理范围内
```

#### 实现关键

- 解析 `pr_filelist.txt` 获取变更文件列表
- 调 `git diff` 获取变更的具体行号和内容
- 用例名与文件路径做关键词提取 + 匹配（TF-IDF 或简单关键词重叠）
- 对比 master 分支同一用例的执行结果

### 5.2 增量定界（同 PR 多次 Run 对比）

> 回答"**这次新引入了什么问题**"

#### 问题

同一 PR 多次触发（重试），每次都全量分析所有失败，但开发者实际只关心"这次比上次多了/少了什么"。

#### 方案

```
当前 Run 失败 Job: [UT_tiling_13, PreSmoke_A3]
上次 Run 失败 Job: [UT_tiling_13]
  │
  ├─ UT_tiling_13: 上次也失败 → "⏳ 未解决，仍是同一问题"
  ├─ PreSmoke_A3:  上次成功 → "❌ 新增失败！代码回归"
  │
  └─ 对比上次成功的 Run（如果有）:
      Compile: 上次失败 → 本次通过 → "✅ 已修复"
```

#### 输出示例

```
📊 增量对比（相比上次 Run #2928）:
  ❌ 新增失败: PreSmoke_A3（上次通过，本次失败 → 可能是代码回归）
  ⏳ 未解决:   UT_tiling_13（上次也失败，同一问题，case_001）
  ✅ 已修复:   Compile_arm（上次失败，本次通过）
```

#### 实现关键

- 调 GitCode API 获取同 PR（`pull_request_id`）的历史 Run 列表
- 取上一次 Run 的 Job 状态做对比
- 区分"新增失败"、"未解决"、"已修复"三种状态

### 5.3 错误链回溯

> 回答"**真正的根因在 error 之前**"

#### 问题

日志中可能有多个 error，开发者习惯看第一个 error，但真正的根因可能在更早的 warning 或某步中间输出。

#### 典型场景

```
日志顺序:
  line 500:  [WARNING] deprecated function GetOldApi() called        ← 真正的根因
  line 800:  [INFO] start tiling calculation
  line 900:  [ERROR] tiling returned -1                               ← 开发者看到的第一个 error
  line 950:  [ERROR] test case failed
```

#### 方案

```
1. 找到所有 error 行
2. 对每个 error，向前回溯搜索相关的 warning/notice/info
   - 匹配规则: 同一模块/同一函数/同一文件的连续日志
   - 回溯范围: error 行前 200 行内
3. 构建错误链:
   WARNING(deprecated API, line 500)
     → INFO(start tiling, line 800)
     → ERROR(tiling -1, line 900)
     → ERROR(test fail, line 950)
4. 输出: "根因可能在 line 500 的 deprecated API 调用"
```

#### 输出示例

```
🔗 错误链回溯:
  根因（疑似）: line 500 [WARNING] deprecated function GetOldApi() called
    ↓
  line 800 [INFO] start tiling calculation
    ↓
  line 900 [ERROR] tiling returned -1  ← 你可能看到的第一行 error
    ↓
  line 950 [ERROR] test case failed

  建议: line 500 的 deprecated API 返回了空值，导致后续 tiling 计算异常。
        请将 GetOldApi() 替换为 GetNewApi()。
```

#### 实现关键

- 从 error 行向前回溯，匹配 `WARNING`、`NOTICE`、`CAUTION` 等关键字
- 按文件名/模块名/函数名做上下文关联（同一上下文的日志才算同一错误链）
- 回溯深度可配置（默认 200 行）

### 5.4 最小重现路径提取

> 回答"**给我一条能本地复现的命令**"

#### 问题

当前定界输出"tiling_13 失败，tilingRet=-1"，但开发者要在本地复现还需自己找：用例输入是什么？怎么执行？

#### 方案

```
失败日志中提取:
  │
  ├─ 用例名: SparseFlashAttentionTiling.SparseFlashAttention_910b_tiling_13
  │   → 从测试数据文件中找到对应的 input shape/params
  │
  ├─ 执行命令:
  │   从日志中提取实际执行的 build_ci.py 命令行
  │   "python3 build_ci.py --frontend=cpp --utest ... --utest_module=codegen:operator"
  │
  ├─ 关键环境变量:
  │   ASCEND_HOME_PATH, CANN_3RD_LIB_PATH, etc.
  │
  └─ 生成复现命令:
      bash build.sh -u --case "SparseFlashAttention*tiling_13" -j1
      或:
      python3 -m pytest tests/ut/.../test_sparse_flash_attention.py -k "tiling_13" -v
```

#### 输出示例

```
🛠️ 本地复现命令:
  # 编译并执行单个失败用例
  source /usr/local/Ascend/cann/bin/setenv.bash
  cd <repo_root>
  python3 build_ci.py --frontend=cpp --build_type=Debug \
    --utest --utest_module=codegen:operator \
    --case_filter="*SparseFlashAttention*tiling_13*" -j1 --verbose

  # 或直接运行测试二进制
  ./build_out/tests/transformer_op_host_ut \
    --gtest_filter="*SparseFlashAttention_910b_tiling_13*"
```

#### 实现关键

- 从日志中正则提取 `build_ci.py`、`pytest`、`gtest_filter` 等执行命令
- 从测试数据文件（CSV/JSON）中匹配用例名对应的输入参数
- 按仓库类型（pypto/hccl/ops-transformer）生成不同的复现命令模板

### 5.5 相似故障推荐

> 回答"**以前怎么解决的**"

#### 问题

不同仓库/不同 PR 经常遇到同类失败，但每次都从头分析。

#### 方案

```
当前失败: "permission is invalid, /home/taskspace not root"
  │
  ├─ 知识库语义匹配:
     case_001: pypto PR#5496, "permission invalid"
               解决方案: "修改 smoke-conf securityContext runAsUser: 0"
               解决 PR: https://gitcode.com/cann/pypto/pulls/5496
               解决人: tanghaoran7
               相似度: 0.92
  │
  └─ 输出:
     "此失败与 pypto PR#5496 高度相似（0.92）
      解决方案: 在 smoke-A3-with-shm.yaml 中设置 runAsUser: 0
      参考 PR: https://gitcode.com/cann/pypto/pulls/5496
      解决人: @tanghaoran7（可咨询）"
```

#### 实现关键

- 知识库存储已解决的失败 case（pattern + solution + PR link + resolver）
- 新失败做文本相似度匹配（TF-IDF / embedding）
- 相似度 > 0.8 时直接推荐历史解决方案

---

## 6. 反馈到 GitCode

### 6.1 PR 评论格式

自动在 PR 下评论完整定界报告：

```markdown
## 🔍 Pipeline Agent — 失败定界报告

**流水线**: [PR-pipeline_pypto #1657](https://gitcode.com/cann/pypto/actions/runs/xxx)
**失败 Job**: PreSmoke_A3 (耗时 2m29s)
**分类**: 🟡 CI配置问题

### 根因
`/home/taskspace` 目录属主非 root，.run 包安装脚本的权限校验失败

### 证据（错误链回溯）
```
line 9578: [WARNING]: [taskspace] permission isn't right, it should belong to root.
line 9580: [ERROR]: the given dir, or its parents, permission is invalid.
line 9604: subprocess.CalledProcessError: ... returned non-zero exit status 1.
```

### 因果关联
本 PR 未修改 PreSmoke 相关代码（.gitcode/scripts/pre_smoke.sh），
失败由 CI 环境配置引起，非代码回归。

### 增量对比（相比上次 Run #1656）
- ❌ 新增失败: PreSmoke_A3（上次通过，本次失败 → 环境变化导致）
- ✅ 已修复: Compile_arm（上次失败，本次通过）

### 本地复现
```bash
# 本问题为环境配置问题，无法通过代码复现
# 建议检查 volcano pod 的 securityContext.runAsUser 设置
```

### 相似故障推荐
此失败与 pypto PR#5496 完全相同（相似度 0.92，已解决）
解决方案: 在 smoke-A3-with-shm.yaml 中设置 `runAsUser: 0`
参考: https://gitcode.com/cann/pypto/pulls/5496
解决人: @tanghaoran7

---
🤖 由 Pipeline Agent 自动生成 | [查看详情](https://gitcode.com/cann/pypto/actions/runs/xxx)
```

### 6.2 Label 打标

| 分类 | Label | 颜色 |
|------|-------|------|
| 代码问题 | `ci-fail-code` | 🔴 红 |
| CI配置 | `ci-fail-config` | 🟡 黄 |
| 环境超时 | `ci-fail-timeout` | 🟠 橙 |
| 网络问题 | `ci-fail-network` | 🔵 蓝 |
| 设备问题 | `ci-fail-device` | 🟣 紫 |
| 依赖缺失 | `ci-fail-dependency` | 🟤 棕 |
| 未知 | `ci-fail-unknown` | ⚪ 白 |

### 6.3 智能通知

| 分类 | 通知对象 |
|------|---------|
| 代码问题 | @PR 提交者 |
| CI配置 | @CI 维护者 |
| 环境问题 | @CI 维护者 + 建议重试 |

### 6.4 去重与抑制

- **同 PR 同 Job 同根因**：仅评论 1 次，后续追加"已报告 ×N"
- **同 PR 多 Job 同根因**：合并为 1 条评论
- **重试后成功**：自动追加"✅ 重试后已通过"

---

## 7. 实现方案

### 7.1 技术选型

| 组件 | 方案 | 理由 |
|------|------|------|
| 触发 | GitCode Action post 步骤 | 无需额外调度，随流水线自动执行 |
| 日志获取 | GitCode API v8（复用 download-logs） | 已有成熟工具 |
| 规则引擎 | Python 正则 + 关键词 | 零成本，秒级，覆盖 70%+ case |
| LLM | 调 LLM API（优先内部模型） | 仅用于规则未命中的 30% |
| 知识库 | OBS JSON + TF-IDF 相似度 | 复用现有 OBS，轻量 |
| 因果关联 | pr_filelist + git diff + 关键词匹配 | 无需 AI，纯规则匹配 |
| 增量对比 | GitCode API 历史 Run 查询 | 复用 query-pipeline 能力 |
| PR 评论 | GitCode API v5 | 复用 query-pipeline 的 API 能力 |
| Label | GitCode API v5 | 复用 query-pipeline 的 label 能力 |

### 7.2 Action 插件设计

```
ai-triage/
├── action.yml              # action 定义
├── dist/
│   ├── main.js             # ncc 打包入口（调度 + API 调用）
│   ├── ai_triage.py        # 核心分析脚本
│   ├── rules.json          # 规则模式库（30+ 模式）
│   ├── knowledge_base.json # 知识库（初始含 7 个 case）
│   └── templates/          # 报告模板
│       ├── report.md.tmpl  # PR 评论模板
│       └── reproduce.sh.tmpl # 复现命令模板
└── README.md
```

### 7.3 执行流程

```
ai-triage 执行（< 60s）
│
├─ 1. 获取失败 Job 列表 + 日志（GitCode API）
│
├─ 2. 规则引擎分类（< 1s/Job）
│     ├─ 命中 → 记录结果
│     └─ 未命中 → 标记待 LLM
│
├─ 3. LLM 分析（< 10s/Job，仅未命中的）
│
├─ 4. 智能定界（5 大能力）
│     ├─ 4a. 变更-失败因果关联（pr_filelist × 失败用例名）
│     ├─ 4b. 增量定界（查询同 PR 上次 Run 对比）
│     ├─ 4c. 错误链回溯（error → 前溯 warning）
│     ├─ 4d. 最小重现路径提取（日志中提取执行命令）
│     └─ 4e. 相似故障推荐（知识库匹配）
│
├─ 5. 生成定界报告
│
├─ 6. 反馈到 GitCode
│     ├─ POST PR 评论
│     ├─ POST Label
│     └─ 更新知识库到 OBS
│
└─ 完成
```

### 7.4 规则模式库初始内容

基于已分析的 7 个真实案例：

```json
{
  "rules": [
    {"id": "R001", "category": "config",
     "pattern": "permission is invalid|permission isn't right.*root",
     "suggestion": "目录权限校验失败，检查 runner 容器 securityContext.runAsUser"},
    {"id": "R002", "category": "config",
     "pattern": "ModuleNotFoundError: No module named '(\\S+)'",
     "extract": 1,
     "suggestion": "Python 模块 {0} 未安装，检查 pre_smoke.sh 中的包下载/安装步骤"},
    {"id": "R003", "category": "device",
     "pattern": "devId is invalid.*Expected.*\\[0, (\\d+)\\)",
     "extract": 1,
     "suggestion": "device id 越界，有效范围 [0, {0})，改为动态获取设备数"},
    {"id": "R004", "category": "network",
     "pattern": "getaddrinfo.*failed.*for (\\S+)",
     "extract": 1,
     "suggestion": "DNS 解析失败: {0}，检查网络/DNS 配置，或将依赖预缓存到 OBS"},
    {"id": "R005", "category": "timeout",
     "pattern": "signal.*SIGTERM|signal.*TERM",
     "suggestion": "进程被超时终止(SIGTERM)，增加 step timeout-minutes 或优化脚本效率"},
    {"id": "R006", "category": "code",
     "pattern": "\\[FAILED\\].*Test|tilingRet.*Which is: (\\d+)",
     "extract": 1,
     "suggestion": "测试用例失败{0}，检查相关算子的 tiling/infershape 逻辑"},
    {"id": "R007", "category": "dependency",
     "pattern": "Each download failed|CMake Error.*download",
     "suggestion": "CMake 第三方依赖下载失败，检查网络或将依赖预缓存"}
  ]
}
```

---

## 8. 落地计划

### Phase 1：MVP — 规则引擎 + 基础定界（2 周）

| 里程碑 | 交付物 | 验证标准 |
|--------|--------|---------|
| 规则引擎 | `ai_triage.py` + 30+ 规则模式 | 对 7 个历史 case 100% 命中 |
| Action 插件 | `ai-triage` 插件（action.yml + dist/main.js） | post 步骤自动触发 |
| PR 评论 | 定界报告自动评论 | 格式正确，信息完整 |
| Label 打标 | 7 种分类 label | 自动打标成功 |
| 错误链回溯 | error → warning 回溯 | 能识别非首行 error 的根因 |
| 增量定界 | 同 PR 多次 Run 对比 | 区分新增/未解决/已修复 |

### Phase 2：LLM 兜底 + 因果关联 + 知识库（3 周）

| 里程碑 | 交付物 | 验证标准 |
|--------|--------|---------|
| LLM 分析 | LLM API 调用 + Prompt 模板 | 规则未命中 case 可分析 |
| 因果关联 | PR diff × 失败用例名匹配 | 能定位到变更文件和行号 |
| 最小重现 | 日志中提取复现命令 | 生成的命令可直接执行 |
| 知识库 | OBS 存储 + 相似度匹配 | 重复失败命中历史方案 |
| 相似故障推荐 | 推荐已验证解决方案 | 推荐 PR 链接 + 解决人 |
| 去重抑制 | 同 PR 同根因去重 | 不重复评论 |

### Phase 3：持续优化（4 周+）

| 里程碑 | 交付物 | 验证标准 |
|--------|--------|---------|
| 规则库扩展 | 50+ 规则模式 | 覆盖 95% 常见失败 |
| LLM 精度提升 | few-shot 学习 + 反馈闭环 | LLM 分析准确率 > 85% |
| 多仓库适配 | 通用化部署 | 支持 5+ 仓库 |
| 趋势分析 | 失败率/失败模式/趋势看板 | 周报自动生成 |

---

## 9. 风险与对策

| 风险 | 影响 | 对策 |
|------|------|------|
| LLM 不可用 | 兜底分析缺失 | 降级为"未知"分类，仅输出日志摘要 |
| GitCode API 限流 | 日志下载失败 | 复用 download-logs 的重试机制 |
| 规则误判 | 错误分类误导开发者 | 置信度 < 0.8 时标注"待人工确认" |
| 因果关联误匹配 | 关联到错误的变更文件 | 仅当匹配度 > 0.8 时展示，否则标注"疑似" |
| 知识库膨胀 | 匹配变慢 | 定期清理 resolved case，保留 pattern |
| PR 评论噪音 | 开发者反感 | 去重 + 折叠 + 可配置开关 |

---

## 10. 评估指标

| 指标 | Phase 1 目标 | Phase 2 目标 | Phase 3 目标 |
|------|-------------|-------------|-------------|
| 失败定位覆盖率 | 80% | 90% | 95% |
| 规则引擎命中率 | 70% | 75% | 80% |
| 平均定位耗时 | < 60s | < 30s | < 10s |
| 分类准确率 | 90% | 95% | 98% |
| 因果关联命中率 | — | 70% | 85% |
| 知识库命中率 | — | 50% | 70% |
| 复现命令可用率 | — | 80% | 95% |
| 开发者满意度 | 3.5/5 | 4.0/5 | 4.5/5 |

---

## 11. 开放问题（待讨论）

| # | 问题 | 选项 |
|---|------|------|
| Q1 | LLM 选型？ | A. 内部模型 B. 外部 API C. 本地小模型 D. Phase 1 不用 LLM |
| Q2 | 知识库存储？ | A. OBS JSON B. Redis C. 向量数据库 D. Phase 1 不做 |
| Q3 | 评论语言？ | A. 中文 B. 英文 C. 跟随仓库语言 |
| Q4 | 因果关联的匹配算法？ | A. 关键词重叠 B. TF-IDF C. Embedding |
| Q5 | 是否支持多个仓库？ | A. 通用（任何 .gitcode/workflows 仓库） B. 逐个适配 |
| Q6 | 是否自动重试环境类失败？ | A. Phase 1 不做 B. 自动重试 1 次 C. 人工确认后重试 |
| Q7 | 增量定界的对比范围？ | A. 仅上一次 Run B. 上一次成功的 Run C. 最近 3 次 Run |

---

*本方案用于串讲评估，欢迎反馈意见。*
