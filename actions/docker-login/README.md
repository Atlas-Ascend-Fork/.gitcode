# docker-login

登录 Docker 镜像仓库，一比一复刻 `docker/login-action` 能力，适配 GitCode CI 平台。

## 输入参数

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `registry` | 否 | `docker.io` | 镜像仓库地址（如 `swr.cn-north-4.myhuaweicloud.com`） |
| `username` | 否 | | 用户名 |
| `password` | 否 | | 密码或 Token |
| `ecr` | 否 | `auto` | 是否为 AWS ECR 仓库（`auto`、`true`、`false`） |
| `scope` | 否 | | 认证 token 的作用域（需 Buildx 0.31.0+） |
| `logout` | 否 | `true` | job 结束时是否自动登出 |
| `registry-auth` | 否 | | 多仓库登录，YAML 格式 |

> `registry-auth` 不能与 `registry`/`username`/`password`/`scope`/`ecr` 同时使用。

## 环境变量

| 变量 | 说明 |
| --- | --- |
| `DOCKERHUB_OIDC_CONNECTIONID` | Docker Hub OIDC 连接 ID（用于 OIDC 登录） |
| `DOCKERHUB_OIDC_EXPIREIN` | OIDC token 有效期（秒，300-21600，默认 300） |
| `AWS_ACCOUNT_IDS` | 额外的 AWS 账号 ID（逗号分隔，仅 ECR） |
| `AWS_REGION` / `AWS_DEFAULT_REGION` | AWS 区域（仅公共 ECR，默认 `us-east-1`） |
| `DOCKER_LOGIN_SCOPE_DISABLED` | 禁用 scope 功能（设为 `true`） |

## 功能

- ✅ `docker login --password-stdin` 安全传密码
- ✅ 密码自动掩码（`::add-mask::`），不泄露到日志
- ✅ job 结束自动 `docker logout` 清理凭证（post action）
- ✅ 多仓库登录（`registry-auth`）
- ✅ AWS ECR 自动检测与认证（通过 `aws ecr get-login-password`）
- ✅ AWS 公共 ECR（`public.ecr.aws`）支持
- ✅ Buildx scope 作用域（凭据写入独立 DOCKER_CONFIG）
- ✅ 失败时输出 exit code + signal

## 使用示例

### 单仓库登录

```yaml
- name: Login
  uses: cann/.gitcode/actions/docker-login@master
  with:
    registry: ${{ env.IMAGE_REGISTRY }}
    username: ${{ secrets.REGISTRY_USERNAME }}
    password: ${{ secrets.REGISTRY_PASSWORD }}
```

### 多仓库登录

```yaml
- name: Login to multiple registries
  uses: cann/.gitcode/actions/docker-login@master
  with:
    registry-auth: |
      - username: ${{ vars.DOCKERHUB_USERNAME }}
        password: ${{ secrets.DOCKERHUB_TOKEN }}
      - registry: ghcr.io
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}
```

### AWS ECR 登录

```yaml
- name: Login to ECR
  uses: cann/.gitcode/actions/docker-login@master
  with:
    registry: <aws-account-number>.dkr.ecr.<region>.amazonaws.com
    username: ${{ vars.AWS_ACCESS_KEY_ID }}
    password: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
```

### 使用 scope

```yaml
- name: Login to Docker Hub (scoped)
  uses: cann/.gitcode/actions/docker-login@master
  with:
    username: ${{ vars.DOCKERHUB_USERNAME }}
    password: ${{ secrets.DOCKERHUB_TOKEN }}
    scope: 'myorg/myimage@push'
```

### 禁用自动登出

```yaml
- name: Login
  uses: cann/.gitcode/actions/docker-login@master
  with:
    registry: ${{ env.IMAGE_REGISTRY }}
    username: ${{ secrets.REGISTRY_USERNAME }}
    password: ${{ secrets.REGISTRY_PASSWORD }}
    logout: false
```

## 与 docker/login-action 对应关系

| docker/login-action | docker-login | 说明 |
| --- | --- | --- |
| `registry` | `registry` | ✅ 相同 |
| `username` | `username` | ✅ 相同 |
| `password` | `password` | ✅ 相同 |
| `ecr` | `ecr` | ✅ 相同（auto/true/false） |
| `scope` | `scope` | ✅ 相同（Buildx config 隔离） |
| `logout` | `logout` | ✅ 相同（post action） |
| `registry-auth` | `registry-auth` | ✅ 相同 |
| Docker Hub OIDC | OIDC 检测 | ⚠️ 检测逻辑完整，但 OIDC token 获取需平台 `id-token: write` 支持 |
| AWS ECR | `aws ecr get-login-password` | ✅ 通过 AWS CLI 实现 |
| AWS 公共 ECR | `aws ecr-public get-login-password` | ✅ 通过 AWS CLI 实现 |

## 差异说明

1. **运行时**：使用 `node16` 而非 `node24`，纯 JavaScript 无外部依赖
2. **AWS ECR 实现**：通过 `aws` CLI 获取 token 而非 `@aws-sdk/client-ecr`，需 runner 预装 AWS CLI
3. **Docker Hub OIDC**：检测逻辑完整（`DOCKERHUB_OIDC_CONNECTIONID` + 无 password），但 OIDC token 交换需平台提供 `core.getIDToken()` 支持，当前会抛出明确错误提示
4. **scope**：通过 `DOCKER_CONFIG` 环境变量隔离凭据，与 docker/login-action 行为一致
