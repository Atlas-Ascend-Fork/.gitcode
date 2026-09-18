#!/bin/bash
set -euo pipefail
echo "当前组织org_name: ${org_name}"

echo ">>>>>>>>>>>>>>>>>>>>>>>>>>>"
remote_url="https://gitcode.com/${org_name}/$repo_name.git"
GIT_PR_NUMBER=$MERGE_ID
echo "http://10.0.0.193:10001/api/pullRequestDetail/check?prId=${remote_url}_${GIT_PR_NUMBER}"
curl "http://10.0.0.193:10001/api/pullRequestDetail/check?prId=${remote_url}_${GIT_PR_NUMBER}" > /tmp/api_check_output.txt 2>/dev/null

cat <<'EOF' > /tmp/get_result.py
import json
import os
import sys

with open('/tmp/api_check_output.txt', 'r') as file:
    out_result = json.load(file)

data = out_result.get('data', None)
all_messages = data.get('messages', []) if data else []
TARGET_CATS = ["包内重复头文件", "包间重复头文件", "废弃接口调用"]

def resolve(data):
    """根据 data.level 的 error/warn/info判断状态"""
    if not data:
        return "pass", "✅", "info"
    level = str(data.get('level', '')).strip().lower()
    if level == "error":
        return "fail", "❌", "error"
    if level == "warn":
        return "pass", "⚠️", "warn"
    # 其余视为 info
    return "pass", "✅", "info"

def parse_rows(messages):
    """解析结构：分类标题（无--前缀）+ 详情（有--前缀），每个分类一行"""
    rows = []
    current_cat = None
    current_details = []
    for msg in messages:
        msg_stripped = msg.strip() if isinstance(msg, str) else str(msg).strip()
        if not msg_stripped:
            continue
        if not msg_stripped.startswith("--"):
            if current_cat is not None:
                rows.append((current_cat, current_details))
            current_cat = msg_stripped
            current_details = []
        else:
            current_details.append(msg_stripped[2:].strip())
    if current_cat is not None:
        rows.append((current_cat, current_details))
    return rows

def is_target_cat(cat):
    """分类标题形如 ***包内重复头文件***，去掉***后判断是否命中目标分类"""
    return any(target in cat.strip().strip("*") for target in TARGET_CATS)

def has_target_detected(rows, data):
    """包内重复头文件/包间重复头文件/废弃接口调用任一项检出即失败：
    1) 消息详情中，目标分类任一条详情非"未检出xxx"；
    2) 结构化详情字段 innerRepeatVo/pkgRepeatVo/deprecatedCall 非空。"""
    for cat, details in rows:
        if is_target_cat(cat):
            for d in details:
                if d and not d.startswith("未检出"):
                    return True
    if data:
        for field in ["innerRepeatVo", "pkgRepeatVo", "deprecatedCall"]:
            if data.get(field):
                return True
    return False

status, status_icon, current_level = resolve(data)
rows = parse_rows(all_messages)
has_detected = has_target_detected(rows, data)

if data:
    for msg in all_messages:
        print(f"{msg}")
    level = data.get('level', '')
    print(f"{level}")

# error -> 失败退出(非零); 或目标分类检出问题 -> 失败退出(非零); warn/info 且未检出 -> 成功退出(0)
failure = (current_level == "error") or has_detected

summary_path = os.environ.get("ATOMGIT_STEP_SUMMARY", "")
if summary_path and failure:
    # 仅失败时输出步骤摘要, 成功不输出
    summary_lines = [
        f"## {status_icon} API 接口校验结果\n",
    ]

    if rows:
        summary_lines.append("\n| 序号 | 测试项目 | 结果 |")
        summary_lines.append("|------|----------|------|")
        for idx, (cat_name, details) in enumerate(rows, 1):
            if details:
                result_text = "<br>".join(d for d in details if d)
            else:
                result_text = "无"
            result_escaped = result_text.replace("|", "\\|")
            cat_escaped = cat_name.replace("|", "\\|")
            summary_lines.append(f"| {idx} | {cat_escaped} | {result_escaped} |")

    with open(summary_path, "a", encoding="utf-8") as f:
        f.write("\n".join(summary_lines) + "\n")

sys.exit(1 if failure else 0)
EOF

python3 /tmp/get_result.py
echo "<<<<<<<<<<<<<<<<<<<<<<<<<<<"
exit 0
