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

with open('/tmp/api_check_output.txt', 'r') as file:
    out_result = json.load(file)

data = out_result.get('data', None)
all_messages = []
if not data:
    status = "pass"
    print("check pass")
else:
    all_messages = out_result['data'].get('messages', [])
    status = "pass" if out_result['data'].get('pass', False) else "fail"
    for msg in all_messages:
        print(f"{msg}")

summary_path = os.environ.get("ATOMGIT_STEP_SUMMARY", "")
if summary_path:
    status_icon = "✅" if status == "pass" else "⚠️"
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
EOF

python3 /tmp/get_result.py
echo "<<<<<<<<<<<<<<<<<<<<<<<<<<<"
exit 0
