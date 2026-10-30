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
all_messages = []

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

# 确定性违例类别: 服务端聚合成 warn, 但属于必须拦截的规范违例
# (案例: PR cann/asc-devkit!5896 合入包内重复头文件 mmad_impl.h, 服务检出为 warn 被放行)
# 注: 包内/包间接口调用暂不拦截, 存量代码命中面大, 需先完成存量治理后再纳入
BLOCK_CATEGORIES = [
    "包内重复头文件", "包间重复头文件", "废弃接口调用",
]

def block_category_violations(messages):
    """逐类别解析 ***类别*** 分组: 类别有内容且非'未检出' -> 违例列表。"""
    violations = []
    current_cat = None
    cat_items = {}
    for msg in messages or []:
        m = str(msg).strip()
        if m.startswith("***") and m.endswith("***"):
            current_cat = m.strip("*").strip()
            cat_items.setdefault(current_cat, [])
        elif current_cat is not None and m:
            cat_items[current_cat].append(m)
    for cat in BLOCK_CATEGORIES:
        items = [m.lstrip("-").strip() for m in cat_items.get(cat, [])
                 if m.strip() and "未检出" not in m]
        if items:
            violations.append((cat, items))
    return violations

status, status_icon, current_level = resolve(data)

# 确定性违例强制判红(不依赖服务端聚合 level)
block_violations = block_category_violations(all_messages or (data or {}).get('messages'))
if block_violations:
    status, status_icon, current_level = "fail", "❌", "error"

if data:
    all_messages = data.get('messages', [])
    for msg in all_messages:
        print(f"{msg}")
    level = data.get('level', '')
    print(f"{level}")

summary_path = os.environ.get("ATOMGIT_STEP_SUMMARY", "")
if summary_path and status == "fail":
    # 仅失败时输出步骤摘要, 成功不输出
    summary_lines = [
        f"## {status_icon} API 接口校验结果\n",
    ]

    if all_messages:
        # 解析结构：分类标题（无--前缀）+ 详情（有--前缀），每个分类一行
        rows = []
        current_cat = None
        current_details = []
        for msg in all_messages:
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

# error -> 失败退出(非零), warn/info -> 成功退出(0)
sys.exit(1 if current_level == "error" else 0)
EOF

python3 /tmp/get_result.py
echo "<<<<<<<<<<<<<<<<<<<<<<<<<<<"
exit 0
