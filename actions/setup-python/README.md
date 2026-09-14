# setup-python (GitCode action)

参考 [actions/setup-python](https://github.com/actions/setup-python) 实现，适配 GitCode Actions 自托管 runner 场景。

## 与 GitHub 原版的对齐/差异

| 能力 | GitHub setup-python v7 | 本 action | 说明 |
|------|----------------------|----------|------|
| `python-version` 输入 | ✅ SemVer 范围 | ✅ 同款（3.12 / 3.12.x / >=3.10,<3.13 / ~3.11） | 纯 JS 零依赖实现 |
| `.python-version` 文件 | ✅ | ✅ | pyenv 风格，缺省查找 |
| `python-version-file` | ✅ | ✅ | 自定义路径 |
| PATH 注入 | ✅ tool cache + addPath | ✅ 候选集 + addPath | GITHUB_PATH 语义 |
| 在线安装 | ✅ actions/python-versions | ❌ **不下载** | 内网约束 + 供应链安全（不做 curl\|bash / TLS OFF 下载） |
| 本地候选集 | runner tool cache | `/opt/buildtools/python-<v>` + `/usr/local/bin` + `/usr/bin` + uv 目录 | CANN CI 预装位优先 |
| 架构输入 | ✅ x86/x64/arm64 | ⚠️ 按宿主处理 | 交叉解释器需预装 |
| pip 缓存 | ✅ cache 输入 | ❌ | CANN CI 已有 CloudCache，避免双缓存冲突 |
| **venv 创建** | ❌ | ✅ `create-venv: true` | CANN 多 python 生态隔离刚需（呼应 Python 归一方案 L0） |
| **register-all** | ❌ | ✅ | 多版本并列（呼应双解释器镜像 L1） |
| allow-missing | ❌（缺版本直接 fail） | ✅ 可回退系统 python3 + 告警 | CANN 66 仓无声明场景宽容性 |
| outputs | python-path / python-version | ✅ 同款 + installed | |
| 缓存依赖 (pip/poetry) | ✅ | ❌ | 走 CI 既有 CloudCache |

## 实现细节

### 版本解析优先级（对齐原版）
```
python-version 输入 > python-version-file > .python-version > PATH 默认 python3（warning）
```

### 本地候选集扫描顺序
1. `/opt/buildtools/python-3.12.x/bin/python3`（CANN CI 镜像预装，优先级最高）
2. `~/.local/share/uv/python/cpython-3.12.x-*/bin/python3`（uv 管理版本）
3. `/usr/local/bin/python3.12` / `/usr/bin/python3.12`（deadsnakes 常见位）
4. PATH 上的 `python3`（保底）

精确版本通过 `python -c "import sys;print('%d.%d.%d'%sys.version_info[:3])"` 实测，不靠目录名猜测。

### SemVer 匹配（零外部依赖的纯 JS 实现）
```
'3.12'      → 主=3, 次=12, 补丁任意
'3.12.x'    → 同上（x 通配）
'>=3.10,<3.13' → 范围与
'~3.11'     → >=3.11.0, <3.12.0
'^3'        → >=3.0.0, <4.0.0
```
未声明位视为通配；多原子取 AND。

### 缺失时的行为
- `allow-missing: false`（默认）→ **setFailed**，错误信息列出全部可用本地版本与扫描范围
- `allow-missing: true` → warning + 回退系统 python3

### venv 模式（CANN 增量）
```
create-venv: true → 命中解释器 python -m venv <venv-path>
  venv/bin 加入 PATH + export VIRTUAL_ENV
  已存在则复用（幂等）
```

## 用法

**基础（对齐原版）**
```yaml
- uses: cann/.gitcode/actions/setup-python@master
  with:
    python-version: '3.12'
```

**范围 + venv（CANN Python 归一 L0 venv 隔离）**
```yaml
- uses: cann/.gitcode/actions/setup-python@master
  with:
    python-version: '>=3.10,<3.13'
    create-venv: true
```

**双解释器注册（归一 L1 双解释器镜像）**
```yaml
- uses: cann/.gitcode/actions/setup-python@master
  with:
    python-version: '3.12'
    register-all: true
```

## 输出

| 输出 | 说明 |
|------|------|
| python-path | 命中 python 绝对路径 |
| python-version | 实际解析版本 x.y.z |
| installed | true（本地复用；本版无在线安装） |

## 后续（P1+）

- pip-cache 输入（若 CI 决策不走 CloudCache 时补齐）
- architecture 跨架构支持
- combine with OSS 门禁白名单联动（.python-version 违背检查）
