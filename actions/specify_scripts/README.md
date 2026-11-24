# specify_scripts

独立 action：从评论中解析 `@<分支>`，拉取 CI 仓库（`https://gitcode.com/opencann/.gitcode.git`）对应分支的 `scripts/<repo_name>/` 目录下全部脚本并上传到 OBS（覆盖同对象键），供流水线后续阶段（compile / UT / PreSmoke 等）通过 `obs-download` 获取。

## 行为

1. 从 `comment` 解析分支名：取 `compile` 后第一个 `@` 之后的非空白串，如 `compile@feat-ci` → `feat-ci`、`/compile@feat-ci @reviewer` → `feat-ci`。
2. 无 `@` → 跳过指定（exit 0），不影响流水线。
3. `git clone -b <分支>` 拉取 CI 仓库（传入 `token` 时自动配置 git 鉴权，日志不打印仓库地址）,克隆超时 5 分钟。
4. 拉取不到分支脚本（分支不存在/目录缺失/目录为空）→ 打 `::warning::` 后退出（exit 0），不阻断流水线，沿用先前已上传的默认脚本。
5. 目录下全部文件按相对路径递归上传：`scripts/<repo_name>/ut.sh` → `<object-prefix>/ut.sh`，`scripts/<repo_name>/sub/x.py` → `<object-prefix>/sub/x.py`。与流水线中 `obs-upload` 步骤的对象键一致时，本 action 后执行可覆盖先前上传的脚本。

## 输入参数

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `repo_name` | 是 | - | 仓库名称（决定 CI 仓库中的 `scripts/<repo_name>/` 目录） |
| `comment` | 否 | - | 触发评论正文，action 从中解析 `@<分支>` |
| `token` | 否 | - | 拉取 CI 仓库的 git token |
| `endpoint` | 是 | - | OBS endpoint，如 `https://obs.cn-north-4.myhuaweicloud.com` |
| `bucket` | 是 | - | OBS 桶名 |
| `access-key` | 否 | - | OBS Access Key，未传时回退 OIDC 临时凭证环境变量 `HUAWEICLOUD_OIDC_AK` |
| `secret-key` | 否 | - | OBS Secret Key，未传时回退 OIDC 临时凭证环境变量 `HUAWEICLOUD_OIDC_SK` |
| `object-prefix` | 是 | - | OBS 对象前缀，如 `org/repo/ci/package/<pr_id>/` |

> **凭证说明**：推荐配合 `huaweicloud-oidc-auth` 插件使用（在同 Job 的前置步骤调用），本 action 自动读取其写入的 `HUAWEICLOUD_OIDC_AK / HUAWEICLOUD_OIDC_SK` 环境变量，无需配置永久 AK/SK。

## 输出

通过 `ATOMGIT_OUTPUT` 写出，可通过 `${{ steps.<identifier>.outputs.<name> }}` 获取：

| 输出 | 说明 |
| --- | --- |
| `ci_branch` | 从 `comment` 解析出的 CI 仓库分支（未解析到为空） |
| `scripts_path` | 本地脚本目录路径（未拉取为空） |
| `specified_files` | 成功上传的脚本数量 |

## 使用示例

```yaml
      JOB_specify_scripts:
        name: specify_scripts
        steps:
          -
            name: oidc_auth
            uses: huaweicloud-oidc-auth
            with:
              audience: ${{ secrets.audience }}
              agency_urn: ${{ secrets.agency_urn }}
              provider_urn: ${{ secrets.provider_urn }}
              region: cn-north-4
              duration: 3600
          -
            name: specify_scripts
            identifier: specify_scripts
            uses: cann/.gitcode/actions/specify_scripts@master
            with:
              repo_name: ${{ env.repo_name }}
              comment: ${{ atomgit.event.comment.body }}
              token: ${{ secrets.TESTTOKEN }}
              endpoint: "https://obs.cn-north-4.myhuaweicloud.com"
              bucket: "ascend-ci"
              # access-key/secret-key 省略，自动回退 oidc_auth 写入的临时凭证
              object-prefix: ${{ env.obs_path }}/
        runs-on: ["self-hosted", "arch=x64", "spec=slim"]
        container:
          image: swr.cn-north-4.myhuaweicloud.com/ci_cann/ubuntu20.04.05_x86:k8s_v1.1006
```
