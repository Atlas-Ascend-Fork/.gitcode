#!/bin/bash
# 解析 codecheck_style.yaml，输出当前仓库的 codecheck_parent_task_id
# 用法: TASK_ID=$(parse_codecheck_style.sh) || exit 0
# 依赖环境变量: repo_name
# 找到: 输出 task_id 到 stdout, 返回 0
# 未找到: 输出提示到 stderr, 返回 1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
YAML_FILE="${SCRIPT_DIR}/codecheck_style.yaml"

if [[ -z "${repo_name}" ]]; then
    echo "⚠️ 环境变量 repo_name 未设置，跳过 codecheck_style" >&2
    exit 1
fi

if [[ ! -f "${YAML_FILE}" ]]; then
    echo "⚠️ 未找到 ${YAML_FILE}，跳过 codecheck_style" >&2
    exit 1
fi

task_id=$(grep -E "^\s+${repo_name}:" "${YAML_FILE}" | awk '{print $2}')

if [[ -z "${task_id}" ]]; then
    echo "ℹ️ 仓库 ${repo_name} 未在 codecheck_style.yaml 中配置，跳过 codecheck_style" >&2
    exit 1
fi

echo "${task_id}"
