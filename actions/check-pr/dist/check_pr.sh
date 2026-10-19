#!/bin/bash
########
# Init #
########

#get params
source ${SCRIPT_DIR}/assert.sh
cat ${WORKSPACE}/pr_filelist.txt

LOG_HEAD "Build check PR changes"
cd ${SCRIPT_DIR} || exit

LOG_HEAD "check binary files"
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8

# 解码文件列表：跳过 .md 与不存在的文件，收集待检文件后批量识别类型，
# 避免逐文件 spawn file 进程（decoded_line 需先赋值再使用）
decoded_list="${WORKSPACE}/.pr_filelist_decoded.txt"
: > "${decoded_list}"
while IFS= read -r line; do
    line=${line%$'\r'}
    decoded_line=$(printf '%b' "$line")
    if [[ "$decoded_line" == *.md ]]; then
        continue
    fi
    full_path="${WORKSPACE}/${decoded_line}"
    if [ ! -f "$full_path" ]; then
        echo "Checking: $full_path"
        echo "Warning: File not found: $full_path"
        continue
    fi
    printf '%s\n' "$full_path" >> "${decoded_list}"
done < "${WORKSPACE}/pr_filelist.txt"

if [ -s "${decoded_list}" ]; then
    # 批量执行 file（单进程多文件），按 "path: type" 输出逐行判定
    xargs -d '\n' file < "${decoded_list}" > "${decoded_list}.types" 2>/dev/null
    while IFS= read -r type_line; do
        full_path="${type_line%%:*}"
        file_type="${type_line#*: }"
        decoded_line="${full_path#${WORKSPACE}/}"
        if [[ "$file_type" == "data" || "$file_type" == *"image data"* ]]; then
            if ! [[ "$decoded_line" =~ ^docs?/([^/]*/)*[^/]*\.(png|jpg)$ ]]; then
                LOG_ERROR "Binary image file not allowed in this path: $decoded_line"
                break
            fi
        fi
    done < "${decoded_list}.types"
fi
rm -f "${decoded_list}" "${decoded_list}.types"

python3 ${SCRIPT_DIR}/check_empty_file.py ${WORKSPACE} ${WORKSPACE}/pr_filelist.txt
DP_ASSERT_EQUAL "$?" "0" "check empty file"

if [[ "${REPOSITORY_NAME}" == @(metadef|driver|driver-dev|amct|asc-devkit|pypto|ge|oam-tools|runtime|graph-autofusion|hixl|tensorflow|ops-gnn|hcomm|hccl|ops-ras|asc-tools) ]] && \
   [ "${GIT_TARGET_BRANCH}" != "feature/community-tasks" ] && \
   [ "${GIT_TARGET_BRANCH}" != "feature/tensor_api_from_9.0.0" ];then
    echo "check md files"
    python3  ${SCRIPT_DIR}/check_md_files.py ${REPOSITORY_NAME} ${GIT_TARGET_BRANCH} ${SCRIPT_DIR}/repo_md_files.yaml ${WORKSPACE}/pr_filelist_mod.txt ${WORKSPACE}
    DP_ASSERT_EQUAL "$?" "0" "Check ${REPOSITORY_NAME} md files " "true"
fi

# OSS 开源依赖门禁：暂时仅在以下仓生效，其余仓跳过
# opencann/asc-devkit 为验证用临时受控仓（按全名与短名两种形态匹配）
if [[ "${REPOSITORY_NAME}" == @(asc-devkit|ops-math|opencann/asc-devkit) ]]; then
    LOG_HEAD "Check URL and third-party library gate"
    python3 ${SCRIPT_DIR}/check_oss_dep.py ${WORKSPACE} ${REPOSITORY_NAME} ${GIT_TARGET_BRANCH} "${MERGE_ID:-}"
    DP_ASSERT_EQUAL "$?" "0" "check URL and third-party library gate"
else
    LOG_HEAD "oss dep gate not enabled for ${REPOSITORY_NAME}, skip"
fi

# PR 关联 issue 门禁：仓库配置变量 PR_ISSUE 为 true 时生效，未配置或 false 跳过
if [ "${PR_ISSUE}" = "true" ]; then
    LOG_HEAD "Check PR linked issues"
    PR_OWNER=$(git -C ${WORKSPACE} remote get-url origin | sed -E 's#.*gitcode\.com[/:]([^/]+)/.*#\1#')
    echo "PR owner: ${PR_OWNER}"
    python3 ${SCRIPT_DIR}/check_pr_linked_issue.py "${MERGE_ID:-}" "${PR_OWNER}"
    DP_ASSERT_EQUAL "$?" "0" "Check ${REPOSITORY_NAME} PR(${MERGE_ID:-}) linked issues"
else
    LOG_HEAD "check linked issue not enabled for ${REPOSITORY_NAME} (PR_ISSUE=${PR_ISSUE:-unset}), skip"
fi
