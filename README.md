# CANN 项目 Issue 与 PR 模板

本仓库包含适配 CANN 项目标准的 Issue 和 Pull Request 模板。

## 目录结构
# test
```
.gitcode/
├── ISSUE_TEMPLATE/
│   ├── bug-report.yml        # 缺陷反馈模板
│   ├── feature-request.yml   # 功能需求模板
│   ├── question.yml          # 问题咨询模板
│   ├── documentation.yml     # 文档反馈模板
│   ├── help-wanted.yml       # 任务认领模板
│   └── config.yml            # 模板配置
├── PULL_REQUEST_TEMPLATE.zh-CN.md  # PR 模板（中文）
└── PULL_REQUEST_TEMPLATE.md        # PR 模板（英文）
```

## CANN 标准特性

### 1. 环境信息标准化

CANN 项目要求提供完整的昇腾环境信息：
- 昇腾硬件型号（Ascend 910B/310P 等）
- CANN 版本

### 2. 功能分类体系

针对昇腾 AI 生态的功能分类：
- 算子功能
- 通信功能
- 图编译
- 模型转换
- 性能
- 稳定性

### 3. 测试规范

CANN 项目的测试要求：
- 单元测试
- 集成测试
- 冒烟测试
- 算子泛化测试
- 性能测试
- 兼容性测试

### 4. 使用方法

1. 将 `.gitcode` 目录复制到项目根目录
2. 根据项目特点调整 `config.yml` 中的链接
3. 可根据需要在各模板中添加项目特定的选项

## 参考文档

- [CANN 官方文档](https://www.hiascend.com/cann/document)
- [昇腾开发者社区](https://www.hiascend.com/forum/forum-0106101385921175004-1.html)
