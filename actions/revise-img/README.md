# revise-img

根据 CI 仓库中 `image-conf/<target_branch>/images.yaml` 的配置，解析指定仓库各构建阶段对应的镜像 tag。

默认从公开的 `cann/.gitcode` 仓库默认分支读取配置；当评论或输入中指定了 `ci_branch` 时，自动切换到内部 CI 仓库的对应分支拉取配置（后台完成，调用方无需感知仓库地址与鉴权）。

## 镜像配置结构

`images.yaml` 包含三层镜像定义，查找顺序为：

1. `repos.<repo_name>.os_mirror` —— 仓库级覆盖（如 `api_check` 专用镜像）
2. `global.os_mirror` —— 全局默认镜像
3. `gray_global.os_mirror` —— 灰度镜像

每个仓库的 `stages` 声明了阶段名到镜像引用的映射，格式为 `os_ver:arch:tag`，脚本据此在上述三层中逐级查找实际镜像名。

末尾固定追加 precommit / codecheck / staticcheck 三个通用镜像。

## 输入参数

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `repo_name` | 是 | - | 仓库名称 |
| `target_branch` | 是 | - | 目标分支（决定读取哪个版本的 `image-conf/<branch>/images.yaml`） |
| `repo_url` | 否 | `https://gitcode.com/cann/.gitcode.git` | 默认 CI 仓库地址（仅当未指定 ci_branch 时使用） |
| `comment` | 否 | - | 触发评论正文；action 自动从中解析 `@<分支>` 得到 ci_branch；为空时读取环境变量 `comment` |
| `ci_branch` | 否 | - | 显式指定 CI 仓库分支，提供时优先于 `comment` 自动解析 |
| `token` | 否 | - | 拉取私有 CI 仓库所用的 git token（仅 ci_branch 非空时使用） |

## ci_branch 解析与切换

`ci_branch` 取值优先级：

1. 显式输入 `ci_branch`；
2. 从 `comment` 中解析最后一个 `@` 之后、空格之前的非空白串，例如 `compile@feat-ci` → `feat-ci`、`a@b@c` → `c`；
3. 都为空 → 不切换。

- **有 ci_branch**：后台切换到内部 CI 仓库的 `ci_branch` 分支，用 `token` 配置 git 鉴权后执行 `git clone -b <ci_branch>`；仓库地址与鉴权不在调用方暴露，日志也不打印该地址。
- **无 ci_branch**：`git clone <repo_url>` 默认分支，行为与历史一致。

## 输出

每行一个 `stage:image`。以 `ops-nn`（master 分支）为例：

```
Compile_Ascend_X86:ubuntu24.04_x86:lv6_v1.1073
Compile_Ascend_X86_ubuntu24:ubuntu24.04_x86:lv6_v1.1073
Compile_Ascend_ARM:ubuntu24.04_arm:lv6_v1.1072
Compile_Ascend_ARM_ubuntu24:ubuntu24.04_arm:lv6_v1.1072
API_Check:ubuntu24.04.3_x86:lv6_v1.1076
UT_Test_ophost:ubuntu24.04_x86:lv6_v1.1073
UT_Test_opapi:ubuntu24.04_x86:lv6_v1.1073
precommit:ubuntu20.04.05_x86:alpha113
codecheck:ubuntu24.04_x86:lv1_v1.1032
staticcheck:ubuntu24.04.03:v1.0
```

下游 job 通过 `${{ jobs.<image_job>.outputs.<stage_name> }}` 获取对应镜像，例如 `${{ jobs.JOB_image.outputs.Compile_Ascend_X86 }}`（其中 `JOB_image` 为执行 `revise-img` 的 job 名称）。

## 使用示例

```yaml
- name: revise_image
  identifier: revise_image
  uses: cann/.gitcode/actions/revise-img@master
  with:
    repo_name: ${{ env.repo_name }}
    target_branch: ${{ env.TARGET_BRANCH }}
    comment: ${{ atomgit.event.comment.body }}
    token: ${{ secrets.GIT_TOKEN }}
```
