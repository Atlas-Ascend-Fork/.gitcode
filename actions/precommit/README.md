# precommit

读取仓库根目录的 `.pre-commit-config.yaml`，安装 pre-commit 后对变更文件执行格式检查：

- 自动将 GitHub 仓库地址替换为 GitCode 镜像，并移除 `oat-check` hook。
- 若仓库无 `.pre-commit-config.yaml` 则直接通过。
- 检查结果写入 `codecheck.json`（`precommit_result: pass/fail`），明细写入 `pre-commit.txt`。

## 输入参数

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `merge_id` | 是 | PR/MR merge id |
| `repo_name` | 是 | 仓库名称 |
| `workspace` | 是 | 代码仓库根目录 |

## 产物

| 文件 | 说明 |
| --- | --- |
| `codecheck.json` | 检查结果汇总 |
| `pre-commit.txt` | pre-commit 完整输出（含 diff） |

## 步骤摘要

检查结果会自动写入 `$ATOMGIT_STEP_SUMMARY`，在流水线运行详情页展示：
- 检查状态（通过/失败）
- 各 hook 检查项的明细表格（Passed/Failed/Skipped）

## 使用示例

```yaml
- name: Checkout
  identifier: process_checkout
  uses: checkout
  with:
    ref: ${{ atomgit.event.pull_request.merge_commit_sha || atomgit.sha }}
    token: ${{ secrets.GIT_TOKEN }}
- name: precommit
  identifier: precommit
  uses: cann/.gitcode/actions/precommit@master
  with:
    merge_id: ${{ env.MERGE_ID }}
    repo_name: ${{ env.repo_name }}
    workspace: ${{ steps.process_checkout.outputs.path }}
```
