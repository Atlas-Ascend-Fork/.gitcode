# GitCode Action 通用配置指导

> 文档版本：v1.0 ｜ 适用平台：GitCode Action (AtomGit) ｜ 工作流目录：`.gitcode/workflows/`

## 目录

- [1. 概述](#1-概述)
- [2. 工作流文件基础](#2-工作流文件基础)
- [3. 触发事件配置](#3-触发事件配置)
- [4. 任务 Jobs 配置](#4-任务-jobs-配置)
- [5. 步骤 Steps 配置](#5-步骤-steps-配置)
- [6. Action 插件使用](#6-action-插件使用)
- [7. 任务编排与执行顺序](#7-任务编排与执行顺序)
- [8. 条件执行](#8-条件执行)
- [9. 矩阵构建](#9-矩阵构建)
- [10. 变量与密钥](#10-变量与密钥)
- [11. 上下文与表达式](#11-上下文与表达式)
- [12. 输出参数传递](#12-输出参数传递)
- [13. 制品与缓存](#13-制品与缓存)
- [14. Runner 运行环境](#14-runner-运行环境)
- [15. 安全与权限](#15-安全与权限)
- [16. 工作流命令](#16-工作流命令)
- [17. 常用配置模板](#17-常用配置模板)

---

## 1. 概述

GitCode Action 是 AtomGit/GitCode 平台上的自动化流水线引擎，通过 YAML 配置文件定义、触发和执行软件交付流程。

### 核心概念

| 概念 | 说明 |
|------|------|
| **Workflow** | 一条完整的自动化流水线，定义在 `.gitcode/workflows/` 目录下的 YAML 文件中 |
| **Stage** | GitCode 特有的阶段机制，Stage 之间串行执行，同一 Stage 内的 Job 并行执行 |
| **Job** | 一个执行单元，包含一组 Step，运行在指定的资源池上 |
| **Step** | Job 内的最小执行步骤，可以是 shell 命令或 Action 组件调用 |
| **Action** | 可复用的自动化组件（如 checkout、setup-python），可跨仓库引用 |
| **Post** | GitCode 特有的后处理阶段，在 Job 结束后自动执行清理、通知等操作 |

### 执行流程

```
Event 触发
  └─ Stage 1（串行）
  │    ├─ Job A（并行）
  │    ├─ Job B（并行）
  │    └─ ...
  └─ Stage 2（Stage 1 全部 Job 成功后执行）
  │    ├─ Job C
  │    └─ ...
  └─ Post（后处理，Job 结束后自动触发）
```

---

## 2. 工作流文件基础

### 2.1 文件位置与命名

工作流文件必须存放在仓库的 **`.gitcode/workflows/`** 目录下（注意：非 `./workflows/`），仅识别 `.yml` 和 `.yaml` 后缀。

| 场景 | 推荐文件名 |
|------|-----------|
| 持续集成 | `ci.yml` |
| 合并请求检查 | `pr-check.yml` |
| 发布 | `release.yml` |
| Docker 镜像构建 | `docker-build.yml` |
| 定时任务 | `nightly.yml` |
| 手动部署 | `deploy.yml` |

### 2.2 基本结构

```yaml
name: 示例流水线          # workflow 展示名称（可省略，缺省使用文件名）

on:                        # 触发条件（必填）
  push:
    branches:
      - main

env:                       # workflow 级环境变量
  APP_NAME: my-app

defaults:                  # 默认设置
  run:
    shell: bash

concurrency:               # 并发控制
  enable: true
  max: 3
  exceed-action: QUEUE

permissions:               # 权限声明
  repository: read
  pr: write

stages:                    # 阶段定义（单阶段时可省略）
  - name: build-stage
    fail_fast: true
    jobs:
      build:
        runs-on: {ubuntu-latest,x64,small}
        steps:
          - uses: checkout
          - run: echo "build"

post:                      # 后处理阶段
  run_always: true
  steps:
    - run: echo "notification"
```

### 2.3 核心字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `name` | 否 | workflow 展示名称 |
| `on` | 是 | 触发条件 |
| `env` | 否 | workflow 级环境变量 |
| `defaults` | 否 | 默认 shell 和 working-directory |
| `concurrency` | 否 | 并发控制 |
| `permissions` | 否 | ATOMGIT_TOKEN 权限范围 |
| `stages` | 否 | 阶段定义（单阶段可省略） |
| `jobs` | 是 | 任务集合（无 stages 时为顶层字段） |
| `post` | 否 | 后处理阶段 |

### 2.4 stages 阶段机制

- **阶段间串行**：前一个 stage 所有 job 完成后才进入下一个 stage
- **阶段内并行**：同一 stage 内的多个 job 默认并行执行
- **fail_fast**：`true` 时任一 job 失败立即终止同阶段其他 Job 并跳过后续所有 stage

```yaml
stages:
  - name: build-stage
    fail_fast: true
    jobs:
      build:
        runs-on: {ubuntu-latest,x64,small}
        steps:
          - run: echo "build"

  - name: test-stage
    jobs:
      unit-test:
        runs-on: {ubuntu-latest,x64,small}
        steps:
          - run: echo "unit test"
```

### 2.5 post 后处理阶段

```yaml
post:
  run_always: true    # 默认 true，无论成功失败都执行；设为 false 仅成功时执行
  steps:
    - name: Send notification
      run: echo "workflow finished"
```

### 2.6 concurrency 并发控制

```yaml
concurrency:
  enable: true                    # 是否启用
  max: 3                          # 最大并发数（1-5）
  exceed-action: QUEUE            # 超出策略：IGNORE（忽略）或 QUEUE（排队）
  preemption:                     # 抢占策略
    enable: true                  # 默认 true
    events: [mr_id]              # 抢占事件，最多 10 个
```

---

## 3. 触发事件配置

### 3.1 支持的事件类型

| 事件 | 说明 | 典型配置 |
|------|------|---------|
| `push` | 代码推送 | `on: push: branches: [main]` |
| `pull_request` | PR 事件（执行 fork 代码，仅 read 权限） | `on: pull_request: branches: [main]` |
| `pull_request_target` | PR 安全事件（执行 base 代码，有写权限） | `on: pull_request_target: branches: [main]` |
| `issue_comment` | Issue/PR 评论 | `on: issue_comment: types: [created]` |
| `pull_request_comment` | 仅 PR 评论 | `on: pull_request_comment: types: [created]` |
| `workflow_dispatch` | 手动触发 | `on: workflow_dispatch: inputs: {...}` |
| `workflow_call` | 可重用调用 | `on: workflow_call: inputs: {...}` |
| `schedule` | 定时触发 | `on: schedule: - cron: '0 2 * * *'` |

### 3.2 push 触发

```yaml
on:
  push:
    branches:
      - main
      - 'releases/**'
    tags:
      - 'v*'
    paths:
      - 'src/**'
      - 'package.json'
    paths-ignore:
      - 'docs/**'
      - '**.md'
```

### 3.3 pull_request 触发

```yaml
on:
  pull_request:
    types: [open, reopen, update, merge]  # 默认 [open, reopen, update]
    branches:          # 匹配 PR 目标分支（base branch）
      - main
    paths:
      - 'src/**'
```

> **注意**：`branches` 过滤的是 PR 的**目标分支**，不指定 types 时默认为 `[open, reopen, update]`。

### 3.4 workflow_dispatch 手动触发

```yaml
on:
  workflow_dispatch:
    inputs:
      environment:
        description: '部署目标环境'
        required: true
        default: 'staging'
        type: string          # 仅支持 string 类型
      version:
        description: '发布版本号'
        required: false
        type: string
```

> inputs 仅支持 `string` 类型，如需数字/布尔语义需在工作流中表达式转换。

### 3.5 workflow_call 可重用工作流

```yaml
on:
  workflow_call:
    inputs:
      config-path:
        description: '配置文件路径'
        required: false
        default: 'config/default.json'
        type: string
    secrets:
      deploy-token:
        description: '部署认证令牌'
        required: true
```

调用方：

```yaml
jobs:
  deploy:
    uses: ./.gitcode/workflows/deploy.yml
    with:
      config-path: 'config/production.json'
    secrets:
      deploy-token: ${{ secrets.DEPLOY_TOKEN }}
```

> 嵌套调用最多支持 2 层。

### 3.6 schedule 定时触发

```yaml
on:
  schedule:
    - cron: '30 5 * * 1,3'    # 每周一、三 05:30 UTC
    - cron: '0 2 * * *'        # 每天 02:00 UTC
```

cron 五段式：`分钟 小时 日 月 星期`，使用 UTC 时区，最短间隔 5 分钟，仅在默认分支生效。

### 3.7 过滤规则

| 过滤器 | 说明 |
|--------|------|
| `branches` / `branches-ignore` | 分支白名单/黑名单（不可同时使用） |
| `paths` / `paths-ignore` | 路径白名单/黑名单（不可同时使用） |
| `tags` / `tags-ignore` | 标签白名单/黑名单（不可同时使用） |
| `!` 前缀 | 否定模式，必须与肯定模式组合使用 |

```yaml
on:
  push:
    branches:
      - 'feature/**'
      - '!feature/experimental'   # 排除特定分支
    paths:
      - 'src/**'
      - '!src/docs/**'            # 排除特定路径
```

### 3.8 多事件组合

```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:
  schedule:
    - cron: "0 2 * * *"
```

---

## 4. 任务 Jobs 配置

### 4.1 基本结构

```yaml
jobs:
  build:
    runs-on: {ubuntu-latest,x64,small}    # 运行环境
    needs: prepare                         # 依赖的其他 job
    if: ${{ atomgit.ref == 'refs/heads/main' }}  # 条件执行
    timeout-minutes: 30                    # 超时时间（默认 360 分钟）
    continue-on-error: true                # 容错（失败不阻断后续）
    env:                                   # job 级环境变量
      APP_ENV: production
    outputs:                               # job 输出
      version: ${{ steps.version.outputs.version }}
    steps:
      - uses: checkout
      - run: ./build.sh
```

### 4.2 核心字段

| 字段 | 说明 |
|------|------|
| `runs-on` | 指定运行器标签 |
| `needs` | 声明依赖的其他 Job |
| `if` | 条件表达式 |
| `env` | Job 级环境变量 |
| `steps` | 步骤列表，串行执行 |
| `timeout-minutes` | 超时时间（默认 360 分钟） |
| `continue-on-error` | Job 失败不阻断后续 |
| `strategy` | 矩阵策略配置 |
| `outputs` | 输出参数 |
| `concurrency` | Job 级并发控制 |

### 4.3 needs 依赖

```yaml
jobs:
  build:
    runs-on: {ubuntu-latest,x64,small}
    steps:
      - run: echo "build"

  test:
    needs: build              # 等待 build 完成后执行
    runs-on: {ubuntu-latest,x64,small}
    steps:
      - run: echo "test"

  deploy:
    needs: [test, lint]       # 多依赖汇聚
    runs-on: {ubuntu-latest,x64,small}
    steps:
      - run: echo "deploy"
```

### 4.4 Job 级并发控制

```yaml
jobs:
  deploy:
    runs-on: {ubuntu-latest,x64,small}
    concurrency:
      enable: true
      max: 1
      exceed-action: IGNORE
      group: production-deploy
      cancel-in-progress: true
    steps:
      - run: echo "deploy"
```

---

## 5. 步骤 Steps 配置

### 5.1 Step 类型

```yaml
steps:
  - name: Checkout code          # Action 类型
    uses: checkout
  - name: Install dependencies   # Script 类型
    run: npm install
  - name: Run tests
    run: npm test
    env:
      NODE_ENV: test
```

### 5.2 核心字段

| 字段 | 说明 |
|------|------|
| `id` | 步骤唯一标识，用于引用输出 `${{ steps.<id>.outputs.<key> }}` |
| `name` | 步骤显示名称 |
| `uses` | 调用 Action 插件 |
| `with` | 向 Action 传递输入参数 |
| `run` | 执行 shell 命令（支持单行/多行） |
| `shell` | Shell 类型：`bash`、`sh`、`pwsh`、`python` |
| `working-directory` | 执行工作目录 |
| `env` | step 级环境变量（仅该 step 可见） |
| `if` | 条件执行 |
| `continue-on-error` | 步骤容错 |
| `timeout-minutes` | 步骤超时 |

### 5.3 working-directory 优先级

优先级从低到高：**Pipeline 级 → Job 级 → Step 级**

```yaml
defaults:
  run:
    working-directory: project

jobs:
  build:
    defaults:
      run:
        working-directory: src      # 覆盖 pipeline 级
    steps:
      - run: echo "in src"
      - working-directory: docs     # 覆盖 job 级
        run: echo "in docs"
```

---

## 6. Action 插件使用

### 6.1 三种引用方式

| 方式 | 语法 | 说明 |
|------|------|------|
| 官方插件 | `uses: action-name@ref` | 直接写插件名称 |
| 开源插件 | `uses: owner/repo/path@ref` | GitCode 公开仓库中的插件 |
| 本仓引用 | `uses: ./path/to/action` | 当前仓库中的插件 |

```yaml
steps:
  - uses: checkout                              # 官方插件
  - uses: setup-node                            # 官方插件
    with:
      node-version: "20"
  - uses: docker/build-push-action@v6           # 开源插件
  - uses: ./.gitcode/actions/my-custom-action   # 本仓引用
```

### 6.2 版本引用方式

| 引用方式 | 说明 | 推荐度 |
|----------|------|--------|
| `@v4`（Tag） | 主版本 Tag，可自动获取补丁更新 | 推荐 |
| `@v4.1.0`（完整版本） | 精确版本，行为稳定 | 安全性最高 |
| `@main`（分支） | 分支最新提交，行为可能变化 | 不推荐 |
| `@a1b2c3d`（SHA） | 精确提交，行为完全确定 | 生产环境推荐 |

### 6.3 本地自定义 Action

本地 Action 需在仓库对应路径下有 `action.yml` 元数据文件：

```yaml
# .gitcode/actions/my-custom-action/action.yml
name: "My Custom Action"
description: "Do something custom"
inputs:
  param1:
    description: "Parameter 1"
    required: false
    default: "default-value"
outputs:
  result:
    description: "Action result"
runs:
  using: 'node16'
  main: 'dist/main.js'
```

---

## 7. 任务编排与执行顺序

### 7.1 needs 与 stages 对比

| 对比项 | needs | stages |
|--------|-------|--------|
| 控制粒度 | job 级别 | stage 级别 |
| 执行模型 | DAG 拓扑 | 阶段串行 + 阶段内并行 |
| 失败策略 | 依赖 job 失败则下游默认不执行 | fail_fast 控制阶段内和跨阶段行为 |
| 适用场景 | 精细依赖编排 | 大阶段分组串行 |

> 两种方式可组合使用：同一 stage 内的 job 仍可通过 needs 配置依赖关系。

### 7.2 needs DAG 编排示例

```
lint ──────────┐
               │
unit-test ─────├── package ── release
               │
int-test ──────┘
```

```yaml
jobs:
  lint:
    runs-on: {ubuntu-latest,x64,small}
    steps:
      - run: echo "lint"
  unit-test:
    runs-on: {ubuntu-latest,x64,small}
    steps:
      - run: echo "unit test"
  integration-test:
    runs-on: {ubuntu-latest,x64,small}
    steps:
      - run: echo "integration test"
  package:
    needs: [lint, unit-test, integration-test]
    runs-on: {ubuntu-latest,x64,small}
    steps:
      - run: echo "package"
  release:
    needs: package
    runs-on: {ubuntu-latest,x64,small}
    steps:
      - run: echo "release"
```

### 7.3 stages 阶段编排示例

```yaml
stages:
  - name: build-stage
    fail_fast: true
    jobs:
      build:
        runs-on: {ubuntu-latest,x64,small}
        steps:
          - run: echo "build"
  - name: test-stage
    jobs:
      unit-test:
        runs-on: {ubuntu-latest,x64,small}
        steps:
          - run: echo "unit test"
      integration-test:
        runs-on: {ubuntu-latest,x64,small}
        steps:
          - run: echo "integration test"
  - name: deploy-stage
    jobs:
      deploy:
        runs-on: {ubuntu-latest,x64,small}
        steps:
          - run: echo "deploy"
```

---

## 8. 条件执行

### 8.1 if 表达式

```yaml
# Job 级 if
jobs:
  deploy:
    if: ${{ atomgit.ref == 'refs/heads/main' }}
    runs-on: {ubuntu-latest,x64,small}
    steps:
      - run: echo "deploy"

# Step 级 if
steps:
  - name: Run on main
    if: ${{ atomgit.ref == 'refs/heads/main' }}
    run: echo "main branch"
```

### 8.2 状态函数

| 函数 | 说明 | 返回 true 的条件 |
|------|------|-----------------|
| `success` | 前置步骤成功 | 前置步骤全部成功（默认行为） |
| `failed` | 前置步骤失败 | 至少一个前置步骤失败 |
| `cancelled` | workflow 被取消 | workflow 被取消 |
| `always` | 无论什么状态 | 任何状态都返回 true |

```yaml
steps:
  - name: Build
    run: ./build.sh
  - name: Notify on success
    if: ${{ success }}
    run: echo "build succeeded"
  - name: Notify on failure
    if: ${{ failed }}
    run: echo "build failed"
  - name: Cleanup
    if: ${{ always }}
    run: ./cleanup.sh
```

### 8.3 运算符与字符串函数

| 运算符/函数 | 说明 | 示例 |
|-------------|------|------|
| `==` / `!=` | 等于/不等于 | `${{ atomgit.ref == 'refs/heads/main' }}` |
| `>` / `<` / `>=` / `<=` | 比较 | `${{ inputs.count > 10 }}` |
| `!` | 逻辑非 | `${{ !cancelled }}` |
| `&&` / `\|\|` | 逻辑与/或 | `${{ success && atomgit.ref == 'refs/heads/main' }}` |
| `contains(str, item)` | 包含 | `${{ contains(atomgit.ref, 'main') }}` |
| `startsWith(str, prefix)` | 前缀匹配 | `${{ startsWith(atomgit.ref, 'refs/tags/') }}` |
| `endsWith(str, suffix)` | 后缀匹配 | `${{ endsWith(atomgit.ref_name, '.rc') }}` |
| `format(template, ...)` | 格式化 | `${{ format('Hello {0}', name) }}` |
| `substring(str, start, len)` | 截取 | `${{ substring(atomgit.sha, 0, 7) }}` |
| `hashFiles(paths...)` | 文件哈希 | `${{ hashFiles('src/**', 'package.json') }}` |

---

## 9. 矩阵构建

### 9.1 基本配置

```yaml
jobs:
  test:
    runs-on: ${{ matrix.os }},${{ matrix.arch }},small
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest]
        arch: [x64]
        node-version: [18, 20]
      exclude:
        - os: windows-latest
          node-version: 18
      include:
        - os: macos-latest
          node-version: 20
          experimental: true
      fail-fast: false
      max-parallel: 4
    steps:
      - uses: checkout
      - uses: setup-node
        with:
          node-version: ${{ matrix.node-version }}
      - run: npm ci && npm test
```

### 9.2 配置说明

| 字段 | 说明 |
|------|------|
| `matrix` | 定义矩阵变量，组合生成 job 实例（二维矩阵生成 N×M 个实例） |
| `include` | 追加特定组合或添加额外变量 |
| `exclude` | 排除特定组合 |
| `fail-fast` | `true`：任一失败立即取消其余；`false`：其余继续执行 |
| `max-parallel` | 最大并行数 |

> `runs-on` 可引用 matrix 变量动态选择 Runner。

---

## 10. 变量与密钥

### 10.1 四级变量体系

| 类型 | 适合存储 | 是否敏感 | 定义位置 | 引用方式 |
|------|---------|---------|---------|---------|
| `env` | workflow 内部临时变量 | 否 | YAML 文件 | `$VAR_NAME` 或 `${{ env.VAR }}` |
| `vars` | 仓库/组织级普通配置 | 否 | GitCode 界面 | `${{ vars.VAR }}` |
| `secrets` | 密码、token、私钥 | 是 | GitCode 界面 | `${{ secrets.NAME }}` |
| `inputs` | workflow_dispatch/call 输入 | 否 | YAML 文件 | `${{ inputs.NAME }}` |

### 10.2 env 环境变量作用域

```yaml
env:
  APP_NAME: demo-app        # Workflow 级，所有 job/step 可见

jobs:
  build:
    env:
      BUILD_MODE: release    # Job 级，该 job 内所有 step 可见
    steps:
      - env:
          STEP_VAR: step-level   # Step 级，仅该 step 可见
        run: echo "$STEP_VAR"
```

**优先级**：Step 级 > Job 级 > Workflow 级

### 10.3 secrets 密钥

```yaml
steps:
  - name: Login registry
    env:
      REGISTRY_USERNAME: ${{ secrets.REGISTRY_USERNAME }}
      REGISTRY_PASSWORD: ${{ secrets.REGISTRY_PASSWORD }}
    run: |
      echo "$REGISTRY_PASSWORD" | docker login example.com -u "$REGISTRY_USERNAME" --password-stdin
```

**安全提示**：
- secrets 值在日志中自动脱敏为 `***`
- 不要在日志中直接打印 secret
- 不要把 secret 写入制品或缓存
- Fork PR 默认不可访问项目级 Secret

### 10.4 ATOMGIT_* 系统变量

| 系统变量 | 说明 |
|---------|------|
| `ATOMGIT_TOKEN` | 工作流认证令牌（自动生成，运行结束失效） |
| `ATOMGIT_SHA` | 触发提交 SHA |
| `ATOMGIT_REF` | 触发引用全名（如 `refs/heads/main`） |
| `ATOMGIT_REF_NAME` | 触发引用短名 |
| `ATOMGIT_EVENT_NAME` | 触发事件名称 |
| `ATOMGIT_REPOSITORY` | 仓库全名（`owner/repo`） |
| `ATOMGIT_WORKSPACE` | Runner 工作区路径 |
| `ATOMGIT_OUTPUT` | 步骤输出文件路径 |
| `ATOMGIT_ENV` | 环境变量文件路径 |
| `ATOMGIT_PATH` | PATH 文件路径 |
| `ATOMGIT_STEP_SUMMARY` | 步骤摘要文件路径 |

### 10.5 变量优先级总览

从高到低：

1. Step 级 env
2. Job 级 env
3. Workflow 级 env
4. vars（配置变量）
5. 系统变量（ATOMGIT_*）

---

## 11. 上下文与表达式

### 11.1 上下文总览

GitCode Action 提供 12 种上下文，通过 `${{ context.property }}` 访问。

| 上下文 | 说明 | 常用访问方式 |
|--------|------|-------------|
| `atomgit` | GitCode 平台与事件信息 | `${{ atomgit.event_name }}`, `${{ atomgit.sha }}` |
| `env` | 自定义环境变量 | `${{ env.MY_VAR }}` |
| `vars` | 组织/项目级配置变量 | `${{ vars.DEPLOY_ENV }}` |
| `job` | 当前 Job 信息 | `${{ job.status }}` |
| `jobs` | 可复用工作流中已运行 Job 的结果 | `${{ jobs.deploy.result }}` |
| `steps` | 当前 Job 中各步骤信息 | `${{ steps.build.outputs.result }}` |
| `runner` | Runner 执行环境信息 | `${{ runner.os }}`, `${{ runner.arch }}` |
| `secrets` | 加密密钥 | `${{ secrets.DEPLOY_TOKEN }}` |
| `strategy` | 矩阵策略信息 | `${{ strategy.job-index }}` |
| `matrix` | 当前矩阵实例的变量值 | `${{ matrix.version }}` |
| `inputs` | dispatch/call 的输入参数 | `${{ inputs.environment }}` |

### 11.2 atomgit 上下文常用属性

| 属性 | 说明 |
|------|------|
| `atomgit.event_name` | 当前触发事件名称 |
| `atomgit.sha` | 触发提交的 SHA |
| `atomgit.ref` | 触发引用（如 `refs/heads/main`） |
| `atomgit.ref_name` | 触发引用短名（如 `main`, `v1.0`） |
| `atomgit.ref_type` | 引用类型：`branch` 或 `tag` |
| `atomgit.event` | 事件完整 payload 对象 |
| `atomgit.token` | ATOMGIT_TOKEN 令牌 |
| `atomgit.repository` | 仓库全名（`owner/repo`） |
| `atomgit.head_ref` | PR 源分支（仅 PR 事件） |
| `atomgit.base_ref` | PR 目标分支（仅 PR 事件） |
| `atomgit.api_url` | GitCode API 基础 URL |

### 11.3 表达式语法

```yaml
steps:
  - name: 仅在 main 分支且成功时执行
    if: ${{ success && atomgit.ref == 'refs/heads/main' }}
    run: echo "Deploy to production"

  - name: 标签推送时构建
    if: ${{ startsWith(atomgit.ref, 'refs/tags/') }}
    run: echo "Build release"

  - name: 使用 format 拼接字符串
    env:
      IMAGE_TAG: ${{ format('{0}:{1}', 'myimage', atomgit.sha) }}
    run: echo $IMAGE_TAG
```

---

## 12. 输出参数传递

### 12.1 三级传递模型

```
Step 输出（ATOMGIT_OUTPUT）
  → 映射到 Job 输出（jobs.<job_id>.outputs）
    → 映射到 Workflow_call 输出
```

### 12.2 Step 输出

```yaml
steps:
  - id: version
    run: echo "version=1.0.0" >> "$ATOMGIT_OUTPUT"
  - name: Use step output
    run: echo "${{ steps.version.outputs.version }}"
```

### 12.3 Job 输出

```yaml
jobs:
  prepare:
    runs-on: {ubuntu-latest,x64,small}
    steps:
      - id: version
        run: echo "version=1.0.0" >> "$ATOMGIT_OUTPUT"

  deploy:
    needs: prepare
    runs-on: {ubuntu-latest,x64,small}
    steps:
      - name: Use job output
        run: echo "version=${{ jobs.prepare.outputs.version }}"
```

### 12.4 多行输出

```yaml
steps:
  - id: multiline-output
    run: |
      EOF=$(dd if=/dev/urandom bs=15 count=1 status=none | base64)
      echo "content<<$EOF" >> "$ATOMGIT_OUTPUT"
      echo "line1" >> "$ATOMGIT_OUTPUT"
      echo "line2" >> "$ATOMGIT_OUTPUT"
      echo "$EOF" >> "$ATOMGIT_OUTPUT"
```

> 每个输出参数的值最大不超过 1MB。

---

## 13. 制品与缓存

### 13.1 制品（Artifacts）

制品用于跨 Job 传递构建产物。

```yaml
# 上传制品
steps:
  - uses: upload-artifact
    with:
      name: app-dist
      path: dist/
      retention-days: 7

# 下载制品
steps:
  - uses: download-artifact
    with:
      name: app-dist
      path: dist/
```

### 13.2 缓存（Cache）

缓存用于加速依赖安装，跨运行复用。

```yaml
steps:
  - uses: cache
    with:
      path: ~/.npm
      key: npm-${{ runner.os }}-${{ hashFiles('package-lock.json') }}
      restore-keys: |
        npm-${{ runner.os }}-
  - run: npm ci
```

**缓存匹配机制**：
1. 首先尝试精确匹配 key
2. 精确匹配失败时，按 restore-keys 顺序尝试前缀匹配
3. 所有匹配失败时，step 执行后保存为新缓存

### 13.3 制品 vs 缓存

| 特性 | 制品 | 缓存 |
|------|------|------|
| 用途 | 传递构建产物（跨 Job） | 加速依赖安装（跨运行） |
| 生命周期 | 可设定保留天数 | 长期保留，LRU 淘汰 |
| 访问范围 | 同 Workflow 的 Job 间 | 同仓库的所有运行 |

### 13.4 常见语言缓存配置

```yaml
# Node.js / npm
- uses: cache
  with:
    path: ~/.npm
    key: npm-${{ runner.os }}-${{ hashFiles('package-lock.json') }}

# Java / Maven
- uses: cache
  with:
    path: ~/.m2/repository
    key: maven-${{ runner.os }}-${{ hashFiles('**/pom.xml') }}

# Java / Gradle
- uses: cache
  with:
    path: |
      ~/.gradle/caches
      ~/.gradle/wrapper
    key: gradle-${{ runner.os }}-${{ hashFiles('**/*.gradle*', 'gradle-wrapper.properties') }}

# Python / pip
- uses: cache
  with:
    path: ~/.cache/pip
    key: pip-${{ runner.os }}-${{ hashFiles('requirements.txt') }}

# Go
- uses: cache
  with:
    path: ~/go/pkg/mod
    key: go-${{ runner.os }}-${{ hashFiles('go.sum') }}
```

---

## 14. Runner 运行环境

### 14.1 官方资源池标签

三段式格式：`{os}-{version},{arch},{spec}`

```yaml
runs-on: {ubuntu-latest,x64,small}
# 或使用默认标签
runs-on: default    # 等效 {ubuntu-latest,x64,small}
```

### 14.2 资源规格表

| 规格 | CPU | 内存 | 磁盘 | 适用场景 |
|------|-----|------|------|---------|
| `slim` | 1 核 | 4 GB | 20 GB | 轻量检查：lint、静态分析 |
| `small` | 2 核 | 8 GB | 50 GB | 常规构建与测试（默认） |
| `medium` | 4 核 | 16 GB | 100 GB | 中型项目编译 |
| `large` | 8 核 | 32 GB | 200 GB | 大规模构建 |
| `xlarge` | 16 核 | 64 GB | 500 GB | 重型计算 |
| `2xlarge` | 32 核 | 128 GB | 1 TB | 极重型计算 |

### 14.3 自托管 Runner

```yaml
jobs:
  gpu-build:
    runs-on: [self-hosted, linux, x64, gpu]
    steps:
      - run: nvidia-smi
```

**标签规则**：
- 必须包含 `self-hosted` 标签
- `runs-on` 中所有标签必须与 Runner 标签集合完全匹配
- 可附加 group（Runner 分组）和自定义 labels

### 14.4 Container 自定义镜像

```yaml
jobs:
  maven-build:
    runs-on: {ubuntu-24,x64,medium}
    container:
      image: maven:3.9-eclipse-temurin-21
      credentials:
        username: ${{ secrets.REGISTRY_USERNAME }}
        password: ${{ secrets.REGISTRY_PASSWORD }}
      env:
        BUILD_MODE: release
      volumes:
        - /data/cache:/cache
      options: --memory 12g
    steps:
      - run: mvn clean package
```

### 14.5 预装工具（Ubuntu 24.04）

| 类别 | 工具 |
|------|------|
| 语言运行时 | Python 3.10/3.11/3.12, Node.js 18/20/22, Go 1.21-1.23, Java 8/11/17/21, Ruby, PHP, Rust, .NET |
| 构建工具 | Maven, Gradle, npm, pip, yarn, pnpm |
| CI 工具 | Git, curl, wget, jq, yq, shellcheck |
| 云工具 | kubectl, helm, aws-cli |

---

## 15. 安全与权限

### 15.1 permissions 权限声明

```yaml
permissions:
  project: read
  pr: write
  issue: read
  note: write
  repository: read
  hook: none
```

快捷语法：
- `permissions: read-all` — 所有权限设为 read
- `permissions: {}` — 所有权限设为 none（最小权限原则）

### 15.2 权限项

| 权限域 | read | write | none |
|--------|------|-------|------|
| `project` | 读取项目信息 | 修改项目设置 | 无权限 |
| `pr` | 读取 PR | 创建/评论/合并 PR | 无权限 |
| `issue` | 读取 Issue | 创建/评论 Issue | 无权限 |
| `note` | 读取评论 | 创建评论 | 无权限 |
| `repository` | 克隆/读取 | 推送/修改仓库 | 无权限 |
| `hook` | 读取 Webhook | 管理 Webhook | 无权限 |

### 15.3 PR 安全：pull_request vs pull_request_target

| 维度 | pull_request | pull_request_target |
|------|-------------|---------------------|
| 执行代码来源 | fork 仓库代码（PR 提交） | 目标仓库代码（main 分支 workflow） |
| ATOMGIT_TOKEN 权限 | 仅 read | 按 permissions 声明的完整权限 |
| Secrets 可访问性 | fork 来源不可访问 | 可访问项目 Secret |
| 适用场景 | 安全的代码检查、lint、构建 | 需要写权限的部署、发布、评论 |

> **关键安全提示**：`pull_request` 来自 fork 时，ATOMGIT_TOKEN 仅 read 权限，无法读取 Secret。若需写权限或访问 Secret，使用 `pull_request_target`，但需谨慎处理 fork PR 的代码执行。

### 15.4 Secrets 管理要点

- **名称规则**：仅大写字母、数字、下划线；不得以 `ATOMGIT_` 开头；不得以数字开头
- **日志遮掩**：Secret 值在日志中自动替换为 `***`
- **不可查看**：创建后无法查看原值，只能更新覆盖
- **Fork 隔离**：fork 的 PR 触发的 workflow 不可访问项目级 Secret
- **作用域**：组织级 > 项目级（项目级同名覆盖组织级）

---

## 16. 工作流命令

### 16.1 设置步骤输出

```bash
echo "result=success" >> $ATOMGIT_OUTPUT
```

### 16.2 设置环境变量

```bash
echo "MY_VAR=my_value" >> $ATOMGIT_ENV
```

### 16.3 添加 PATH

```bash
echo "/custom/bin" >> $ATOMGIT_PATH
```

### 16.4 步骤摘要

```bash
echo "## 构建结果" >> $ATOMGIT_STEP_SUMMARY
echo "| 项目 | 状态 |" >> $ATOMGIT_STEP_SUMMARY
echo "|------|------|" >> $ATOMGIT_STEP_SUMMARY
echo "| App | ✅ 成功 |" >> $ATOMGIT_STEP_SUMMARY
```

### 16.5 日志脱敏

```bash
echo "::add-mask::$MY_SECRET"
```

### 16.6 废弃命令（勿用）

| 废弃命令 | 替代方案 |
|---------|---------|
| `echo "::set-output name=result::success"` | `echo "result=success" >> $ATOMGIT_OUTPUT` |
| `echo "::set-env name=MY_VAR::my_value"` | `echo "MY_VAR=my_value" >> $ATOMGIT_ENV` |
| `echo "::add-path::/custom/bin"` | `echo "/custom/bin" >> $ATOMGIT_PATH` |

---

## 17. 常用配置模板

### 17.1 最小 CI 模板

```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: {ubuntu-latest,x64,small}
    steps:
      - uses: checkout
      - run: npm ci
      - run: npm test
```

### 17.2 多阶段构建发布模板

```yaml
name: Build and Deploy
on:
  push:
    branches: [main]

stages:
  - name: build-stage
    fail_fast: true
    jobs:
      build:
        runs-on: {ubuntu-latest,x64,small}
        steps:
          - uses: checkout
          - run: make build
          - uses: upload-artifact
            with:
              name: build-output
              path: dist/

  - name: test-stage
    jobs:
      test:
        runs-on: {ubuntu-latest,x64,small}
        steps:
          - uses: checkout
          - uses: download-artifact
            with:
              name: build-output
              path: dist/
          - run: make test

  - name: deploy-stage
    jobs:
      deploy:
        runs-on: {ubuntu-latest,x64,small}
        steps:
          - run: make deploy

post:
  run_always: true
  steps:
    - run: echo "Send notification"
```

### 17.3 矩阵测试模板

```yaml
name: Matrix Test
on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: {ubuntu-latest,x64,small}
    strategy:
      matrix:
        node-version: [18, 20, 22]
      fail-fast: false
      max-parallel: 3
    steps:
      - uses: checkout
      - uses: setup-node
        with:
          node-version: ${{ matrix.node-version }}
          cache: 'npm'
      - run: npm ci
      - run: npm test
```

### 17.4 手动部署模板

```yaml
name: Manual Deploy
on:
  workflow_dispatch:
    inputs:
      environment:
        description: '部署环境'
        required: true
        default: 'staging'
        type: string
      version:
        description: '版本号'
        required: true
        type: string

jobs:
  deploy:
    runs-on: {ubuntu-latest,x64,medium}
    steps:
      - uses: checkout
      - name: Deploy
        run: |
          echo "Deploying ${{ inputs.version }} to ${{ inputs.environment }}"
          make deploy ENV=${{ inputs.environment }} VERSION=${{ inputs.version }}
```

### 17.5 PR 检查模板

```yaml
name: PR Check
on:
  pull_request:
    types: [open, update, reopen]
    branches: [main]

permissions:
  contents: read
  pull-requests: write

jobs:
  code-style:
    runs-on: {ubuntu-latest,x64,slim}
    steps:
      - uses: checkout
      - uses: setup-node
        with:
          node-version: '20'
          cache: 'npm'
      - run: npm ci
      - run: npm run lint

  test:
    runs-on: {ubuntu-latest,x64,small}
    steps:
      - uses: checkout
      - uses: setup-node
        with:
          node-version: '20'
          cache: 'npm'
      - run: npm ci
      - run: npm test
```

### 17.6 可重用工作流模板

```yaml
# .gitcode/workflows/reusable-build.yml
name: Reusable Build
on:
  workflow_call:
    inputs:
      environment:
        required: true
        type: string
    secrets:
      deploy-token:
        required: true

jobs:
  build:
    runs-on: {ubuntu-latest,x64,small}
    steps:
      - uses: checkout
      - run: echo "Building for ${{ inputs.environment }}"
```

调用方：

```yaml
jobs:
  call-build:
    uses: ./.gitcode/workflows/reusable-build.yml
    with:
      environment: production
    secrets:
      deploy-token: ${{ secrets.DEPLOY_TOKEN }}
```

---

## 附：配置检查清单

创建工作流前，请确认以下事项：

- [ ] 文件存放在 `.gitcode/workflows/` 目录下，后缀为 `.yml` 或 `.yaml`
- [ ] `on` 触发事件配置正确（注意 `pull_request` 的 branches 过滤的是目标分支）
- [ ] `runs-on` 标签格式正确（官方：`{os,arch,spec}`；自托管：`[self-hosted, ...]`）
- [ ] 遵循最小权限原则配置 `permissions`
- [ ] 敏感信息使用 `secrets`，不在日志中打印
- [ ] Fork PR 场景正确选择 `pull_request` 或 `pull_request_target`
- [ ] 长任务配置合理的 `timeout-minutes`
- [ ] 需要复用的流程考虑使用 `workflow_call` 可重用工作流
- [ ] 依赖安装使用 `cache` 加速
- [ ] 构建产物使用 `upload-artifact` / `download-artifact` 跨 Job 传递

---

*本文档基于 GitCode Action 官方用户帮助文档（v1.0）整理生成。*
