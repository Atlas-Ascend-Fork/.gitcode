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

### 2.1 失败分类体系

Pipeline Agent 将流水线失败分为三大类，每类有不同的定界策略和反馈动作：

| 分类 | 定义 | 典型场景 | 定界重点 | 反馈动作 |
|------|------|---------|---------|---------|
| **代码问题** | PR 变更的代码逻辑导致失败 | UT/ST 用例失败、编译错误、tiling 返回异常 | 定位到具体代码行，提供复现命令 | @PR 提交者修复 |
| **工程问题** | CI 配置、脚本、依赖配置导致失败 | 包路径错误、权限校验、workflow YAML 错误、脚本 bug | 定位到具体配置文件和配置项 | @CI 维护者修复 |
| **环境问题** | 运行环境异常导致失败 | 网络不通、设备 ID 越界、超时被杀、DNS 失败 | 识别环境异常特征，区分是否可重试 | 建议重试或联系平台 |

### 2.2 目标

| # | 目标 | 适用分类 | 衡量标准 |
|---|------|---------|---------|
| G1 | **自动定界**：流水线失败后 1 分钟内输出根因定位 | 全部 | 覆盖 80%+ 常见失败模式 |
| G2 | **自动分类**：准确区分代码/工程/环境三类问题 | 全部 | 分类准确率 90%+ |
| G3 | **自动反馈**：结果推送到 GitCode PR 评论 + 标签 | 全部 | 无需人工打开 Action 页面 |
| G4 | **代码定位**：代码问题定位到 PR 变更的具体代码行，提供复现命令 | 代码问题 | 回答"改了什么导致失败"+"如何本地复现" |
| G5 | **配置定位**：工程问题定位到具体配置文件和配置项，推荐修复方案 | 工程问题 | 回答"哪个配置错了"+"怎么改" |
| G6 | **环境识别**：环境问题识别异常类型，区分可重试/不可重试 | 环境问题 | 回答"是环境问题还是代码问题"+"能否重试" |
| G7 | **增量对比**：同 PR 多次执行时只报告新增/已修复的变化 | 全部 | 减少重复噪音 |
| G8 | **经验复用**：历史失败模式形成知识库，推荐已验证方案 | 全部 | 命中率随时间递增 |
| G9 | **健康度评估**：持续评估流水线整体稳定性，量化各仓库 CI 质量 | 全局 | 周报自动生成，预警及时触达 |

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
│  │              5. 智能定界（按分类差异化）               │       │
│  │  ├─ 5.1 代码问题：变更-失败因果关联 + 复现命令         │       │
│  │  ├─ 5.2 工程问题：配置项定位 + 修复推荐               │       │
│  │  ├─ 5.3 环境问题：异常识别 + 重试决策                 │       │
│  │  ├─ 5.4 增量定界（同 PR 多次 Run 对比）               │       │
│  │  ├─ 5.5 错误链回溯（error → warning 反向追溯）        │       │
│  │  └─ 5.6 相似故障推荐（知识库经验复用）                 │       │
│  └──────────────────────────────────────────────────────┘       │
│                           │                                     │
│                           ▼                                     │
│  ┌──────────────────────────────────────────────────────┐       │
│  │              6. 反馈到 GitCode                        │       │
│  │  ├─ PR 评论（定界报告 + 因果分析 + 复现命令）          │       │
│  │  ├─ Label 打标（ci-fail-code/env/ci-config/timeout）  │       │
│  │  └─ @ 相关人员（代码问题@提交者，CI问题@维护者）        │       │
│  └──────────────────────────────────────────────────────┘       │
│                           │                                     │
│                           ▼                                     │
│  ┌──────────────────────────────────────────────────────┐       │
│  │              7. 流水线整体评估                         │       │
│  │  ├─ 仓库健康度评分（成功率/首次率/重试/Flaky/耗时）    │       │
│  │  ├─ 失败模式分布（30天统计，识别系统性问题）            │       │
│  │  ├─ 趋势预警（连续失败/成功率下降/Flaky增多）          │       │
│  │  └─ 周报/月报（自动生成，推送 Issue）                  │       │
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

## 5. 智能定界核心能力

按失败分类（代码/工程/环境）分别设计定界能力，每类问题回答不同的核心问题。

### 5.1 代码问题定界：变更-失败因果关联

> 回答"**你改了什么导致这个失败**" + "**如何本地复现**"

#### 问题

当前定界只能告诉"tiling_13 失败了"，开发者还要自己去找"我改了哪行代码导致 tiling_13 失败"以及"如何在本地复现"。

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
  ├─ 历史基线对比:
  │   master 分支 tiling_13 通过 → PR 引入变更后失败 → 确认是 PR 导致
  │
  └─ 复现命令提取:
      从日志中提取实际执行的 build_ci.py / pytest / gtest 命令
      生成可直接复制执行的本地复现命令
```

#### 输出示例

```
🔍 代码问题定界:
  失败用例 SparseFlashAttention_910b_tiling_13
  与你修改的 sparse_flash_attention_tiling.cpp 强相关（匹配度 0.95）

  变更位置: 第 87 行，新增 LSE 分支处理
  失败原因: tiling_13 的输入参数走到 LSE 分支后 tilingRet 返回 -1

  建议: 检查 LSE 分支的 boundary_input_idx 范围判断，
        tiling_13 的输入可能不在 LSE 分支预期的处理范围内

🛠️ 本地复现命令:
  source /usr/local/Ascend/cann/bin/setenv.bash
  python3 build_ci.py --frontend=cpp --build_type=Debug \
    --utest --utest_module=codegen:operator \
    --case_filter="*SparseFlashAttention*tiling_13*" -j1 --verbose
```

#### 实现关键

- 解析 `pr_filelist.txt` 获取变更文件列表
- 调 `git diff` 获取变更的具体行号和内容
- 用例名与文件路径做关键词提取 + 匹配（TF-IDF 或简单关键词重叠）
- 对比 master 分支同一用例的执行结果
- 从日志中正则提取 `build_ci.py`、`pytest`、`gtest_filter` 等执行命令
- 按仓库类型生成不同的复现命令模板

### 5.2 工程问题定界：配置项定位与修复推荐

> 回答"**哪个配置错了**" + "**怎么改**"

#### 问题

工程问题（CI 配置/脚本/依赖配置错误）的失败日志往往指向运行时错误（如 `ModuleNotFoundError`、`permission invalid`），但真正的根因在某个配置文件或脚本中。开发者需要自己排查是哪个 `.yml`、`.sh` 或 `Dockerfile` 的配置不对。

#### 方案

```
失败日志: "ModuleNotFoundError: No module named 'pypto'"
  │
  ├─ 规则匹配: R002 → category=config
  │
  ├─ 配置项溯源:
  │   "pypto 未安装" → 搜索 CI 脚本中的安装逻辑
  │   ├─ .gitcode/scripts/pre_smoke.sh: 包下载 URL 路径
  │   ├─ .gitcode/scripts/compile.sh: 编译产物路径
  │   └─ .gitcode/workflows/pypto_action.yml: 包传递逻辑
  │
  ├─ 具体定位:
  │   pre_smoke.sh 第 85 行: wget .../test/pypto/package/cann-pypto_linux-aarch64_ubuntu24.run
  │   → 当前仓库是 opencann/pypto，但 URL 路径用的是 test/pypto
  │   → 路径不匹配，包下载失败导致未安装
  │
  └─ 修复推荐:
      "将 pre_smoke.sh 第 85 行的 URL 路径从 test/pypto 改为 opencann/pypto"
      或推荐知识库中已验证的解决方案
```

#### 输出示例

```
🔧 工程问题定界:
  失败现象: ModuleNotFoundError: No module named 'pypto'
  根因: pre_smoke.sh 中包下载 URL 路径错误

  问题位置: .gitcode/scripts/pre_smoke.sh 第 85 行
  当前值: wget .../test/pypto/package/cann-pypto_linux-aarch64_ubuntu24.run
  期望值: wget .../opencann/pypto/ci/package/6/cann-pypto_linux-aarch64_ubuntu24.run

  修复建议: 修改 URL 路径，与当前仓库的 OBS 路径一致

📋 相似故障推荐:
  此问题与 hcomm PR#3 的 mockcpp 下载失败类似（同属工程配置问题）
  参考: https://gitcode.com/opencann/hcomm/pulls/3
```

#### 实现关键

- 规则匹配后，根据失败类型反查可能涉及的配置文件：
  - `ModuleNotFoundError` → 搜索 `pre_smoke.sh`、`ut.sh`、`compile.sh` 中的安装/下载逻辑
  - `permission invalid` → 搜索 `smoke-conf/*.yaml` 中的 `securityContext`/`runAsUser`
  - `command not found` → 搜索 workflow YAML 中的 `uses`/`with` 配置
  - `PACKAGE_URL` → 搜索 `compile.sh` 中的 `wget` URL
- 对比配置值与预期值（如仓库路径、OBS 路径、镜像名称）
- 知识库匹配已验证的修复方案

### 5.3 环境问题定界：异常识别与重试决策

> 回答"**是环境问题还是代码问题**" + "**能否重试**"

#### 问题

环境问题（网络/设备/超时）的失败表现多样，开发者难以判断是偶发环境问题还是代码导致的。盲目重试浪费资源，不重试又可能错过偶发恢复。

#### 方案

```
失败日志分析
  │
  ├─ 环境异常识别（6 种模式）:
  │   ├─ SIGTERM/SIGKILL → 超时或 OOM，可重试
  │   ├─ getaddrinfo failed → DNS 问题，可重试（若网络恢复）
  │   ├─ Connection refused → 服务不可达，可重试
  │   ├─ rtSetDevice invalid → 设备配置问题，不可重试（需修改配置）
  │   ├─ No space left → 磁盘满，不可重试（需清理）
  │   └─ download timeout → 下载超时，可重试
  │
  ├─ 代码关联排除:
  │   "本 PR 未修改与环境相关的配置（pre_smoke.sh/smoke-conf/workflow）"
  │   → 确认非代码引入的环境问题
  │
  └─ 重试决策:
      ├─ 可重试: 环境偶发问题（网络/超时/OOM）→ 建议自动重试 1 次
      ├─ 不可重试: 配置导致的环境问题（device id/磁盘）→ 需人工修复
      └─ 需观察: 首次出现，无法确认 → 建议人工确认后重试
```

#### 输出示例

```
🌐 环境问题定界:
  失败现象: signal=SIGTERM, check_pr.sh 被终止
  根因: 平台 step 级超时杀死进程（非代码问题）

  环境异常类型: 超时 (SIGTERM)
  可重试: ✅ 是（偶发超时，重试可能通过）

  代码关联: 本 PR 未修改 check_pr 相关配置
  → 确认为环境问题，非代码引入

  建议:
  - 短期: 重试本次流水线
  - 长期: 在 workflow 中为 check-pr step 增加 timeout-minutes: 30
```

#### 实现关键

- 6 种环境异常模式识别（正则匹配）
- 检查 PR 变更文件是否涉及环境配置（`pre_smoke.sh`、`smoke-conf/*.yaml`、`*.yml`）
- 若 PR 未修改环境配置 → 判定为环境偶发问题
- 若 PR 修改了环境配置 → 可能是配置引入的环境问题，需进一步分析
- 重试决策表：可重试/不可重试/需观察

### 5.4 增量定界（同 PR 多次 Run 对比）

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

### 5.5 错误链回溯

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

### 5.6 相似故障推荐

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

````markdown
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
````

### 6.2 Label 打标

| 分类 | Label | 颜色 | 含义 |
|------|-------|------|------|
| 代码问题 | `ci-fail-code` | 🔴 红 | PR 代码逻辑导致失败，需提交者修复 |
| 工程问题 | `ci-fail-config` | 🟡 黄 | CI 配置/脚本错误，需 CI 维护者修复 |
| 工程问题 | `ci-fail-dependency` | 🟤 棕 | 依赖缺失或版本不匹配 |
| 环境问题 | `ci-fail-timeout` | 🟠 橙 | 超时被杀，可能可重试 |
| 环境问题 | `ci-fail-network` | 🔵 蓝 | 网络不通，可能可重试 |
| 环境问题 | `ci-fail-device` | 🟣 紫 | 设备/NPU 异常，通常不可重试 |
| 未知 | `ci-fail-unknown` | ⚪ 白 | 未命中规则，待 LLM 或人工分析 |

### 6.3 智能通知与动作

| 分类 | 通知对象 | 建议动作 |
|------|---------|---------|
| 代码问题 | @PR 提交者 | 修复代码后重新触发 |
| 工程问题 | @CI 维护者 | 修复 CI 配置/脚本 |
| 环境问题（可重试） | @CI 维护者 | 自动重试 1 次，若仍失败再通知 |
| 环境问题（不可重试） | @CI 维护者 + @PR 提交者 | 需人工排查环境配置 |

### 6.4 去重与抑制

- **同 PR 同 Job 同根因**：仅评论 1 次，后续追加"已报告 ×N"
- **同 PR 多 Job 同根因**：合并为 1 条评论
- **重试后成功**：自动追加"✅ 重试后已通过"

---

## 7. 流水线整体评估

### 7.1 评估维度

Pipeline Agent 不仅做单次失败定界，还需对流水线整体健康度做持续评估，从"诊断单次故障"升级到"评估系统稳定性"。

| 维度 | 定义 | 数据来源 | 计算方法 |
|------|------|---------|---------|
| **成功率** | 30 天内流水线通过率 | GitCode API 运行历史 | passed / total |
| **首次通过率** | PR 首次触发即通过的比例 | 同 PR 多次 Run 历史 | first_run_passed / total_pr |
| **平均重试次数** | 同一 PR 平均触发次数 | 同 PR Run 历史 | total_runs / total_pr |
| **平均总耗时** | 流水线从开始到结束的平均时间 | Run 详情 start/end_time | avg(end - start) |
| **P50/P90 耗时** | 耗时中位数 / 90 分位 | Run 详情 | 排序取中位/P90 |
| **Job 级失败率** | 各 Job 的独立失败率 | Job 状态历史 | failed / total per job |
| **Flaky 率** | 同 PR 同 Job 摇摆失败的比例 | 同 PR 多次 Run 对比 | (pass→fail→pass) / total |
| **编译缓存命中率** | ccache 命中率 | 日志中 ccache -s 输出 | hits / (hits + misses) |
| **失败恢复时间** | 从首次失败到最终通过的时间 | 同 PR Run 历史 | last_pass_time - first_fail_time |

### 7.2 仓库健康度评分

综合多维度指标，给每个仓库一个量化健康度分数：

```
健康度 = w1×成功率 + w2×首次通过率 + w3×(1-重试率) + w4×(1-Flaky率) + w5×耗时得分
```

| 权重 | 因子 | 说明 |
|------|------|------|
| 0.30 | 成功率 | 30 天成功率，权重最高 |
| 0.20 | 首次通过率 | 首次即过，反映代码质量和 CI 配置成熟度 |
| 0.15 | 重试率 | 1 - (平均重试次数 / 阈值3)，重试越多扣分越多 |
| 0.15 | Flaky 率 | 摇摆失败占比，反映环境/测试稳定性 |
| 0.10 | 耗时得分 | 1 - (avg耗时 / 基线耗时)，比基线快加分 |
| 0.10 | 编译缓存命中率 | 反映 CI 资源利用效率 |

**评分等级：**

| 分数 | 等级 | 含义 | 建议动作 |
|------|------|------|---------|
| ≥ 90 | A | 优秀 | 保持现状 |
| 75-89 | B | 良好 | 关注薄弱维度 |
| 60-74 | C | 一般 | 需改进，优先处理高频失败 |
| < 60 | D | 差 | 重点关注，CI 阻碍开发效率 |

**输出示例：**

```
┌─────────────────┬──────┬──────┬──────┬──────┬──────┬────────┐
│ 仓库             │ 成功率│ 首次率│ 重试  │ Flaky│ 耗时  │ 健康度  │
├─────────────────┼──────┼──────┼──────┼──────┼──────┼────────┤
│ runtime          │ 95%  │ 82%  │ 1.2  │ 2%   │ 12m  │ A (92) │
│ ops-transformer  │ 88%  │ 70%  │ 1.5  │ 3%   │ 18m  │ B (82) │
│ hcomm            │ 78%  │ 55%  │ 2.1  │ 5%   │ 15m  │ B (75) │
│ pypto            │ 63%  │ 30%  │ 3.5  │ 8%   │ 8m   │ C (61) │
│ cannbot-knowledge│ 40%  │ 20%  │ 0.5  │ 0%   │ 3m   │ D (45) │
└─────────────────┴──────┴──────┴──────┴──────┴──────┴────────┘

⚠️ 预警:
  - pypto: PreSmoke 连续 5 次失败，健康度下降趋势 (C → 建议 priority 处理)
  - cannbot-knowledge: 成功率 40%，但重试率低 → CI 不可用而非代码问题
  - hcomm: Flaky 率 5% → UT 存在不稳定用例
```

### 7.3 失败模式分布分析

按失败类型统计 30 天内的分布，识别系统性问题：

```
失败模式分布（30天）:
  CI配置      ████████████████  35%  (42次)  ← 最多，需优先治理
  代码逻辑    ████████████      25%  (30次)
  环境超时    █████████         18%  (22次)
  网络        █████             10%  (12次)
  设备/NPU   ███                7%  (8次)
  依赖缺失    ██                 4%  (5次)
  未知        █                  1%  (2次)
```

### 7.4 趋势预警规则

| 预警类型 | 触发条件 | 严重度 | 动作 |
|---------|---------|--------|------|
| 连续失败 | 同一 Job 连续 3 次失败 | 🔴 高 | 通知 CI 维护者，建议暂停该 Job |
| 成功率下降 | 周成功率环比下降 > 15% | 🔴 高 | 生成周报，标注下降原因 |
| Flaky 增多 | 同 Job 周内 Flaky ≥ 3 次 | 🟡 中 | 标记不稳定用例，建议增加重试或隔离 |
| 耗时上涨 | 平均耗时环比上涨 > 30% | 🟡 中 | 检查 runner 规格/缓存命中/代码体积 |
| 新失败模式 | 出现知识库中未记录的失败模式 | 🔵 低 | 自动加入知识库待分析队列 |

### 7.5 评估报告输出

**周报**（自动生成，推送至仓库 Issue 或文档）：

```markdown
## 📊 CANN 流水线健康度周报（2026-08-19 ~ 2026-08-25）

### 整体概况
- 本周流水线总运行: 156 次
- 整体成功率: 76.3% (↑ 2.1% vs 上周)
- 首次通过率: 58.2% (↓ 1.5% vs 上周)
- 平均总耗时: 14.2min (→ 持平)

### 各仓库健康度
[仓库健康度表格]

### 本周 Top 3 失败模式
1. CI配置 - 42次 (35%) ↑ - pypto PreSmoke 权限问题
2. 代码逻辑 - 30次 (25%) → - ops-transformer tiling 回归
3. 环境超时 - 22次 (18%) ↑ - cannbot-knowledge check-pr 超时

### 预警
- 🔴 pypto PreSmoke_A3 连续 5 次失败 (CI配置)
- 🟡 hcomm UT Flaky 率上升至 5%
- 🟡 ops-transformer 编译耗时上涨 35%

### 建议优先处理
1. pypto PreSmoke 权限问题（已阻塞 3 个 PR）
2. cannbot-knowledge check-pr 超时（增加 timeout-minutes）
3. hcomm Flaky UT 用例隔离
```

**月报**（趋势分析，对比月度变化）：

包含：
- 月度成功率趋势曲线
- 各仓库健康度月度变化
- 失败模式月度分布对比
- Top 10 高频失败 case 排行
- 平均恢复时间趋势

### 7.6 评估数据存储与计算

| 数据 | 存储 | 更新频率 | 计算方式 |
|------|------|---------|---------|
| Run 历史 | GitCode API 实时查询 | 每次评估时拉取 | API 分页查询 |
| Job 状态 | GitCode API | 同上 | Run 详情解析 |
| 失败分类 | Pipeline Agent 知识库 | 每次定界后更新 | 规则引擎 + LLM |
| 健康度评分 | OBS JSON | 每周计算 | 离线脚本聚合 |
| 周报/月报 | OBS + 仓库 Issue | 每周/每月 | 模板渲染 |

### 7.7 与定界的协同关系

```
单次定界（微观）          整体评估（宏观）
     │                        │
     ├─ 分析本次失败根因       ├─ 统计 30 天失败分布
     ├─ 匹配知识库             ├─ 计算仓库健康度
     ├─ 推送 PR 评论           ├─ 生成趋势预警
     │                        │
     └────────┬───────────────┘
              ▼
     知识库（共享）
     ├─ 单次定界结果 → 沉淀为知识
     ├─ 整体评估 → 从知识库聚合统计
     └─ 周报/月报 → 反哺知识库标注趋势
```

**定界是数据采集端，评估是数据消费端**：
- 每次定界产生的分类结果（code/config/timeout/...）是整体评估的原始数据
- 整体评估发现的高频失败模式，反过来指导规则引擎优先覆盖
- 健康度低的仓库，Pipeline Agent 的评论可以更详细（高优先级处理）

---

## 8. 团队分工与 AI Agent 团队诉求

### 8.1 整体定位

Pipeline Agent 由**工程团队**和 **AI Agent 团队**协同建设。工程团队负责流水线基础设施、数据采集和反馈执行；AI Agent 团队负责规则引擎、LLM 智能分析、知识库语义匹配和持续学习能力。

```
┌─────────────────────────────────────────────────────────────┐
│                    Pipeline Agent 能力分层                    │
│                                                             │
│  ┌─────────────────────────────────────────────────┐        │
│  │  AI Agent 团队负责                                │        │
│  │                                                   │        │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐       │        │
│  │  │ 规则引擎  │  │ LLM 分析  │  │ 知识库    │       │        │
│  │  │ 模式匹配  │  │ Prompt   │  │ Embedding│       │        │
│  │  │ 分类定界  │  │ 工程      │  │ 语义匹配  │       │        │
│  │  └──────────┘  └──────────┘  └──────────┘       │        │
│  │                                                   │        │
│  │  ┌──────────┐  ┌──────────┐                      │        │
│  │  │ 持续学习  │  │ 规则库    │                      │        │
│  │  │ 反馈闭环  │  │ 维护扩展  │                      │        │
│  │  └──────────┘  └──────────┘                      │        │
│  └───────────────────────┬─────────────────────────┘        │
│                          │ 接口                              │
│  ┌───────────────────────┴─────────────────────────┐        │
│  │  工程团队负责                                      │        │
│  │                                                   │        │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐       │        │
│  │  │ 日志获取  │  │ 反馈执行  │  │ 评估看板  │       │        │
│  │  │ API 调用  │  │ PR 评论   │  │ 数据采集  │       │        │
│  │  │ 数据采集  │  │ Label     │  │ 周报月报  │       │        │
│  │  └──────────┘  └──────────┘  └──────────┘       │        │
│  └─────────────────────────────────────────────────┘        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 8.2 对 AI Agent 团队的核心诉求

| # | 诉求 | 优先级 | 说明 |
|---|------|--------|------|
| R1 | **规则引擎**：设计 30+ 失败分类模式，维护规则库并持续扩展 | P0 | Phase 1 核心，覆盖 70%+ 常见失败 |
| R2 | **LLM 分析接口**：提供 REST API，输入日志上下文，输出结构化定界 JSON | P0 | Phase 1 兜底，规则未命中时调用 |
| R3 | **Prompt 工程**：针对 CANN 流水线日志特点优化 Prompt，支持 few-shot | P0 | 通用 LLM 直接用效果差，需领域适配 |
| R4 | **知识库向量化**：将历史失败 case 向量化存储，支持语义检索 | P1 | Phase 2，超越关键词匹配 |
| R5 | **代码-用例语义关联**：PR 变更文件与失败用例的语义匹配（非关键词重叠） | P1 | Phase 2，提升因果关联准确率 |
| R6 | **错误链因果推理**：从 error 回溯到 warning 时，判断因果关联性 | P2 | Phase 2，超越简单行距匹配 |
| R7 | **复现命令生成**：从日志中智能提取和组装可执行的复现命令 | P2 | Phase 2，非简单正则提取 |
| R8 | **反馈闭环**：开发者反馈回流，持续优化规则和 LLM 精度 | P2 | Phase 3，few-shot 样本积累 |
| R9 | **多语言日志支持**：部分日志含中文（CANN 安装脚本），LLM 需兼容 | P1 | CANN 日志中英文混合 |

### 8.3 工程团队职责

| 模块 | 职责 | 交付物 |
|------|------|--------|
| Action 插件 | `ai-triage` 插件开发、触发机制、执行流程 | `action.yml` + `dist/main.js` |
| 日志获取 | GitCode API 调用、失败 Job 筛选、日志下载解压 | 复用 `download-logs` |
| 反馈执行 | PR 评论、Label 打标、通知、去重抑制 | GitCode API 调用 |
| 增量对比 | 同 PR 历史 Run 查询、状态对比 | 复用 `query-pipeline` |
| 健康度评估 | 数据采集、评分计算、周报/月报生成 | 离线脚本 + OBS 存储 |
| 评估看板 | 失败模式分布、趋势预警、健康度展示 | HTML 报告 + Issue 推送 |

### 8.4 AI Agent 团队职责

| 模块 | 职责 | 交付物 |
|------|------|--------|
| 规则引擎 | 30+ 正则模式设计、分类定界逻辑、规则库维护与扩展 | `rules.json` + 分类引擎 |
| LLM 分析 | 规则未命中时的兜底分析，Prompt 工程设计与优化 | Prompt 模板 + LLM 调用接口 |
| 知识库语义匹配 | 历史失败 case 的向量化存储与相似度检索 | Embedding 模型选型 + 向量库方案 |
| 代码-用例语义关联 | PR 变更文件与失败用例名的语义匹配 | 语义匹配模型/方案 |
| 错误链因果推理 | 从 error 回溯 warning 时，判断因果关联性 | 因果推理 Prompt/模型 |
| 复现命令生成 | 从日志中智能提取和组装复现命令 | LLM 生成 + 校验 |
| 持续学习 | 开发者反馈回流，持续优化规则和 LLM 精度 | 反馈闭环机制 + few-shot 样本积累 |

### 8.5 协作里程碑对齐

| 阶段 | 工程团队 | AI Agent 团队 | 集成点 |
|------|---------|--------------|--------|
| **Phase 1** (2周) | 插件 + 日志获取 + PR 评论 + Label + 增量对比 | 规则引擎 + LLM 分析接口 + Prompt 模板 | 工程调规则引擎，未命中调 LLM |
| **Phase 2** (3周) | 配置溯源 + 健康度评分 + 评估看板 | 知识库向量化 + 语义关联 + 复现命令生成 + 规则库扩展 | 知识库更新 + LLM 增强 |
| **Phase 3** (4周+) | 多仓库适配 + 趋势看板 | 反馈闭环 + 持续学习 + 规则自动发现 | 开发者反馈回流 |

### 8.6 验收标准（AI Agent 团队）

| 指标 | Phase 1 目标 | Phase 2 目标 | Phase 3 目标 |
|------|-------------|-------------|-------------|
| LLM 分析准确率 | 70% | 80% | 90% |
| LLM 响应时间 | < 10s | < 5s | < 3s |
| 知识库语义匹配命中率 | — | 50% | 70% |
| 代码-用例关联准确率 | — | 70% | 85% |
| 复现命令可用率 | — | 80% | 95% |
| 开发者反馈准确率 | — | 70% positive | 85% positive |

---

