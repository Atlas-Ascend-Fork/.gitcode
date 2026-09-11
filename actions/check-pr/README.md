# check-pr

对 `get-pr` 产出的变更文件进行基础合规检查：

1. 二进制/图片文件路径校验：仅允许 `docs*/.../*.png|*.jpg` 路径下提交图片，其余二进制文件报错（文件列表解码后经 `xargs file` 批量识别，跳过 `.md` 与不存在文件）。
2. Markdown 链接检查：调用 `check_markdown_links.py` 校验 HTTP 链接、相对路径、锚点、图片、邮箱是否有效（支持并发重试）。
3. **OSS 开源依赖门禁（暂仅在 asc-devkit / ops-math 仓生效，其余仓跳过）**：调用 `check_oss_dep.py`，解析 PR patch（`update_file_detail.txt`）中新增的 URL 链接、C 三方库引用（`add_cann_third_party(xxx)`）、Python 依赖声明（`*requirements*.txt`）与 NodeJS 依赖声明（`package.json`），按目标分支读取门禁文件 `oss_dep_security_gate_<branch>.json`（如 master 分支为 `oss_dep_security_gate_master.json`，由 sbom 扫描工程生成，每仓包含 `branch / CANN_CMAKE_TAG / url / opensource_c / opensource_py / opensource_js`）进行管控：
   - 修改不包含 URL、三方库引用或 py/js 依赖声明：门禁通过；
   - 代码仓不在门禁文件 key 中：此代码仓不作检查管控，门禁通过；
   - **豁免路径**（与门禁文件生成侧排除规则一致）：`doc(s)/`、`__pycache__/`、`node_modules/`、`.git/` 目录及 `.md` 文件的新增内容不参与 URL/开源依赖检测，直接放行；
   - 代码仓受控时：
     - 新增 URL 必须在 `url` 白名单内（完全匹配或带边界字符的前缀匹配）；URL 不在白名单内时，若能识别为 Python/NodeJS 依赖组件 URL（pypi 项目页、whl/tgz 制品、npm registry 制品等）且组件版本仍满足 `opensource_py` / `opensource_js` 的版本约束，依然准许合入（宽范围版本放行）；
     - 新增三方库引用必须在 `opensource_c` 属性内；
      - `requirements.txt` / `package.json` 引入的依赖组件：组件在白名单内且版本满足约束则放行；**版本号大于 `opensource_py` / `opensource_js` 允许版本时拦截**，提示需要在相应依赖文件 `requirements.txt` 或 `package.json` 同步更新版本号；组件不在白名单内或版本落在约束范围外时拦截。
4. **门禁日志留档**：常规放行（白名单/版本范围内等）聚合统计输出，避免大 PR 逐条日志刷屏；同步更新放行、豁免与拦截逐条输出。触发门禁豁免（豁免路径）或门禁拦截时，全量检查日志（含仓库/分支/结论/豁免路径/明细）写入 workspace 下 `oss-dep-gate-check.txt`，由流水线 `obs-upload` 步骤（`if: always()`）上传至 OBS `obs_path` 前缀（与 `pr_filelist.txt` / `update_file_detail.txt` 同目录），供后续追溯使用；正常放行（无豁免）不产生日志文件。

## 输入参数

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `workspace` | 是 | 代码检出目录 |
| `repo_name` | 是 | 仓库名称（部分仓库跳过 Markdown 链接检查；URL/三方库门禁以仓库名作为门禁文件 key） |
| `target_branch` | 否 | 目标分支，默认 `master`，决定读取的门禁文件 `oss_dep_security_gate_<branch>.json` |

## 产物

| 文件 | 说明 |
| --- | --- |
| `link_check_report.txt` | 失败链接报告 |
| `link_details.csv` | 全部链接检查明细 |

## 使用示例

```yaml
- name: Checkout
  identifier: process_checkout
  uses: checkout
  with:
    ref: ${{ atomgit.event.pull_request.merge_commit_sha || atomgit.sha }}
    token: ${{ secrets.GIT_TOKEN }}
- name: check-pr
  identifier: check-pr
  uses: cann/.gitcode/actions/check-pr@master
  with:
    repo_name: ${{ env.repo_name }}
    workspace: ${{ steps.process_checkout.outputs.path }}
```
