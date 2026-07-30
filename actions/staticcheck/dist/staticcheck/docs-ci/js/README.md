# 说明

1、芯片标签的合法性检查：

1.1）①固定样式\<!-- npu=""950,A3"" id1 -->xxx\<!-- end id1 -->，注意空格位置；②id保证配对且单个md文件内唯一
1.2）npu取值要求：950/A3/910b/910/310p/310b/IPV350/x90/9030，后续有扩展后需要修改

2、位置标签的合法性检查：

2.1）①固定样式：
\<!-- @ref: 仓名/res/.../xx_res.md#idxxxxx -->，如：\<!-- @ref: pypto/res/docs/a/a1_res.md#id1 -->；②其中id无需保证文件内唯一，和规则1区分校验"

## npus.json

该文档为配置npu属性的白名单，需要和脚本在同一级目录下

## tag_checker.js

该文件为执行脚本：

使用方法：

```bash
node tag_checker.js <markdown文件/文件夹路径> <输出结果文件夹路径> <仓名>
```

使用示例：

**文件夹**

```bash
node "tag_checker.js" D:\~\markdown\new  D:\~\output workspace
```

**单一文件**

```bash
node "tag_checker.js" D:\~\markdown\new\111.md  D:\~\output workspace
```

### 检查结果示例

检查结果文件名称：D:\~\output\tag_check_result.json

内容：

```json
[
  {
    "rule_group": "通用规则",
    "rule_item": "StaticCheck_compliance",
    "rule_type": "规范性",
    "rule_name": "芯片标签的合法性检查",
    "snippet": "<!-- npu=\"910\" id3 -->",
    "description": "ID重复: id3 在第 296 行和第 293 行重复出现",
    "rule_level": "严重",
    "file_name": "cann_sim工具指南.md",
    "line_number": "296",
    "location": "D:\\~\\new\\cc\\cann_sim工具指南.md:296",
    "suggestion": "请使用唯一的ID标识符，避免在同一文档中重复使用相同的ID"
  }
]
```
