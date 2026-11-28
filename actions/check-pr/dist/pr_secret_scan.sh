#!/bin/bash
#
# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# the CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.
#
# pr_secret_scan.sh — 触发 agent-hub AI 泄密扫描，发送完触发请求即退出（agent 异步检视，结果以行内评论发表在 PR 上）
# 入参: $1 仓库名; $2 PR 编号; 环境变量 AGENT_HUB_TOKEN / AGENT_HUB_URL / GIT_TOKEN（预留）

set -e

REPO="${1:-}"
PR="${2:-}"
TOKEN="${AGENT_HUB_TOKEN:-}"
HUB_URL="${AGENT_HUB_URL:-https://cannbot.hicann.cn/agent-hub}"

ORG="cann"
SESSION_ID="192"
EVENT_KEY="pr_secret_scan"

if [ -z "$REPO" ] || [ -z "$PR" ]; then
    echo "错误: 未指定仓库名或 PR 编号（用法: pr_secret_scan.sh <repository> <pr_id>）"
    exit 1
fi
case "$PR" in
    *[!0-9]*|"") echo "错误: PR 编号非法: ${PR}"; exit 1 ;;
esac
if [ -z "$TOKEN" ]; then
    echo "错误: 未配置 agent-hub token（环境变量 AGENT_HUB_TOKEN）"
    exit 1
fi

PR_URL="https://gitcode.com/${ORG}/${REPO}/pull/${PR}"
CONTENT="使用 pr-secret-review skill 检查PR ${PR_URL} 是否存在泄密，检查存在泄密后发表行内评论，但不重复评论。"

echo "触发 agent-hub AI 泄密扫描"
echo "  仓库: ${ORG}/${REPO}  PR: #${PR}"
echo "  session: ${SESSION_ID}  event_key: ${EVENT_KEY}"
echo "  content: ${CONTENT}"

PAYLOAD=$(printf '{"content": "%s", "event_key": "%s"}' "$CONTENT" "$EVENT_KEY")

# 一次请求同时取响应体与 HTTP 状态码（-w 在响应体末尾追加状态码，按最后一行拆分）
RESP=$(curl -s -w '\n%{http_code}' --max-time 60 \
    -X POST "${HUB_URL}/agenthubs/api/agents/sessions/${SESSION_ID}/trigger" \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD" 2>/dev/null || printf '\n000')
HTTP_CODE="${RESP##*$'\n'}"
BODY="${RESP%$'\n'*}"

if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
    echo "已触发(HTTP ${HTTP_CODE}): $(printf '%s' "$BODY" | head -c 300)"
    echo "泄密扫描已异步执行，检视结果以 agent 在 PR 上的行内评论为准"
    exit 0
else
    echo "错误: 触发失败(HTTP ${HTTP_CODE}): $(printf '%s' "$BODY" | head -c 200)"
    exit 1
fi
