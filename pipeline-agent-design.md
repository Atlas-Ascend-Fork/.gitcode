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
| G7 | **健康度评估**：持续评估流水线整体稳定性，量化各仓库 CI 质量 | 周报自动生成，预警及时触达 |

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

## 5. 智能定界核心能力

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

### 5.4 相似故障推荐

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

#### 评分等级

| 分数 | 等级 | 含义 | 建议动作 |
|------|------|------|---------|
| ≥ 90 | A | 优秀 | 保持现状 |
| 75-89 | B | 良好 | 关注薄弱维度 |
| 60-74 | C | 一般 | 需改进，优先处理高频失败 |
| < 60 | D | 差 | 重点关注，CI 阻碍开发效率 |

#### 输出示例

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

#### 周报（自动生成，推送至仓库 Issue 或文档）

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

#### 月报（趋势分析，对比月度变化）

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

*本方案用于串讲评估，欢迎反馈意见。*
