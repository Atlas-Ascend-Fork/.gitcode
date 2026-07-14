# CANN CI Actions

本目录收录 CANN 项目在 GitCode CI 流水线中复用的一组 GitHub Actions（`using: node16`）。每个 Action 通过 `dist/main.js` 入口读取 `action.yml` 中声明的输入参数，并透传给同目录下的 Shell / Python 脚本完成具体检查任务。

## Action 列表

| Action | 说明 |
| --- | --- |
| [get-pr](get-pr/README.md) | 获取 PR 相对目标分支的变更文件清单 |
| [check-pr](check-pr/README.md) | 检查 PR 变更内容（二进制文件、Markdown 链接） |
| [staticcheck](staticcheck/README.md) | 静态检查（MarkdownLint、docs-ci 文档规范） |
| [precommit](precommit/README.md) | 基于 `.pre-commit-config.yaml` 的代码格式检查 |
| [api-check](api-check/README.md) | API 文档生成与上报 / PR 接口校验 |
| [verify-package](verify-package/README.md) | 编译产物安装与卸载验证 |
| [ut-cov-report](ut-cov-report/README.md) | 单元测试覆盖率打包与报告生成 |
| [revise-img](revise-img/README.md) | 解析仓库各构建阶段对应的镜像 |
| [query_pipeline](query_pipeline/README.md) | 查询流水线执行情况（运行详情、Job 列表、步骤明细） |
| [download_logs](download_logs/README.md) | 下载流水线运行日志并打包（全部日志 + 失败日志） |

> 通用约定：多数 Action 依赖前置 `get-pr` 产出的 `pr_filelist.txt` / `pr_filelist_mod.txt` 等变更文件清单，建议在流水线中先调用 `get-pr`。
