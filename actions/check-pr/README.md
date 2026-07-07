# check-pr

对 `get-pr` 产出的变更文件进行基础合规检查：

1. 二进制/图片文件路径校验：仅允许 `docs*/.../*.png|*.jpg` 路径下提交图片，其余二进制文件报错。
2. Markdown 链接检查：调用 `check_markdown_links.py` 校验 HTTP 链接、相对路径、锚点、图片、邮箱是否有效（支持并发重试）。

## 输入参数

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `workspace` | 是 | 代码检出目录 |
| `repo_name` | 是 | 仓库名称（部分仓库跳过 Markdown 链接检查） |

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
