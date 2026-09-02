# check-pr

对 `get-pr` 产出的变更文件进行基础合规检查：

1. 二进制/图片文件路径校验：仅允许 `docs*/.../*.png|*.jpg` 路径下提交图片，其余二进制文件报错。
2. Markdown 链接检查：调用 `check_markdown_links.py` 校验 HTTP 链接、相对路径、锚点、图片、邮箱是否有效（支持并发重试）。
3. URL/三方库门禁检查：调用 `check_url_third_party.py`，解析 PR patch（`update_file_detail.txt`）中新增的 URL 链接与三方库引用（`add_cann_third_party(xxx)`），按目标分支读取白名单 `pipline_ctrl_<branch>.json`（如 master 分支为 `pipline_ctrl_master.json`）进行管控：
   - 修改不包含 URL 或三方库引用：门禁通过；
   - 代码仓不在白名单文件 key 中：此代码仓不作检查管控，门禁通过；
   - 代码仓受控时，新增 URL 必须在 `URL` 属性内，新增三方库引用必须在 `Third_party` 属性内，否则门禁拦截并打印"引入的URL/三方库 不在白名单列表内"。

## 输入参数

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `workspace` | 是 | 代码检出目录 |
| `repo_name` | 是 | 仓库名称（部分仓库跳过 Markdown 链接检查；URL/三方库门禁以仓库名作为白名单 key） |
| `target_branch` | 否 | 目标分支，默认 `master`，决定读取的白名单文件 `pipline_ctrl_<branch>.json` |

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
