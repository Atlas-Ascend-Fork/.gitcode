#!/bin/bash
set -euo pipefail
echo "当前组织org_name: ${org_name}"

echo ">>>>>>>>>>>>>>>>>>>>>>>>>>>"
remote_url="https://test.gitcode.net/${org_name}/$repo_name.git"
GIT_PR_NUMBER=$MERGE_ID
echo "http://10.0.0.193:10001/api/pullRequestDetail/check?prId=${remote_url}_${GIT_PR_NUMBER}"
curl "http://10.0.0.193:10001/api/pullRequestDetail/check?prId=${remote_url}_${GIT_PR_NUMBER}" > /tmp/api_check_output.txt 2>/dev/null

cat <<EOF > /tmp/get_result.py
import json
with open('/tmp/api_check_output.txt', 'r') as file:
    out_result = json.load(file)
data = out_result.get('data', None)
if not data:
    print(f"check pass")
else:
    total = out_result['data']['messages']
    for msg in total:
        print(f"{msg}")
EOF

python3 /tmp/get_result.py
echo "<<<<<<<<<<<<<<<<<<<<<<<<<<<"
exit 0
