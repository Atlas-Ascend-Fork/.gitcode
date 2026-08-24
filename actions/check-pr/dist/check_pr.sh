#!/bin/bash
########
# Init #
########

#get params
source ${SCRIPT_DIR}/assert.sh 
pip3 install requests urllib3
cat ${WORKSPACE}/pr_filelist.txt

LOG_HEAD "Build check PR changes"
cd ${SCRIPT_DIR} || exit

LOG_HEAD "check binary files"
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8

type_flag=0
while IFS= read -r line; do
    line=${line%$'\r'}
    decoded_line=$(printf '%b' "$line")
    full_path="${WORKSPACE}/${decoded_line}"
    echo "Checking: $full_path"
    if [[ "$decoded_line" == *.md ]]; then
        continue
    fi
    if [ ! -f "$full_path" ]; then
        echo "Warning: File not found: $full_path"
        continue
    fi
    file_type=$(file -b "$full_path")
    echo "Type: $file_type"
    if [[ "$file_type" == "data" || "$file_type" == *"image data"* ]]; then
        if ! [[ "$decoded_line" =~ ^docs?/([^/]*/)*[^/]*\.(png|jpg)$ ]]; then
            LOG_ERROR "Binary image file not allowed in this path: $decoded_line"
            type_flag=1
            break
        fi
    fi
done < "${WORKSPACE}/pr_filelist.txt"

python3 ${SCRIPT_DIR}/check_empty_file.py ${WORKSPACE} ${WORKSPACE}/pr_filelist.txt
DP_ASSERT_EQUAL "$?" "0" "check empty file"

# if [ "${REPOSITORY_NAME}" == "canndev" ];then
#     LOG_HEAD "Build check Check_TBE_interface"
#     LOG_DO bash ${WORKSPACE}/CI/cann/pipeline/ascend/canndev/scripts/canndev_compile.sh -b master -p check_tbe_interface -t ubuntu_x86
#     DP_ASSERT_EQUAL "$?" "0" "Build check Check_TBE_interface"
#     LOG_HEAD "Build check illegal words"
#     python3 isIllegal.py ${REPOSITORY_NAME} ${WORKSPACE}/CI/cann/public/illegal_word.yaml ${WORKSPACE}/canndev
#     checkCode=$?
#     echo "isIllegal checkcode is ${checkCode} illegal_word check end"
# fi

# LOG_HEAD "Check markdown links"
# md_files=()  # 声明一个数组

# while IFS= read -r line; do
#     line=${line%$'\r'}
#     decoded_line=$(printf '%b' "$line")
#     full_path="${WORKSPACE}/${decoded_line}"
#     # 只处理以 .md 结尾的文件
#     if [[ "$decoded_line" != *.md ]]; then
#         continue
#     fi
#     if [ ! -f "$full_path" ]; then
#         echo "Warning: File not found: $full_path" >&2
#         continue
#     fi
#     md_files+=("$full_path")
# done < "${WORKSPACE}/pr_filelist.txt"

# # 如果有 .md 文件，才调用 Python 脚本
# if [[ ${#md_files[@]} -gt 0 ]] && [[ "${REPOSITORY_NAME}" != @(asc-devkit|pypto|pypto-tools|asc-tools|pyasc|ops-nn|ops-transformer|ops-math|ops-cv|opbase) ]]; then
#     python3 "${SCRIPT_DIR}/check_markdown_links.py" "${md_files[@]}" --only-failed
#     REPORT_FILE="{$SCRIPT_DIR}/link_check_report.txt"
#     if [ -f "${REPORT_FILE}" ]; then
#         cat "${REPORT_FILE}"
#     fi
# else
#     echo "No valid Markdown files to check."
# fi
cd ${SCRIPT_DIR}


if [[ "${REPOSITORY_NAME}" == @(metadef|driver|driver-dev|amct|asc-devkit|pypto|ge|oam-tools|runtime|graph-autofusion|hixl|tensorflow|ops-gnn|hcomm|hccl|ops-ras|asc-tools) ]] && \
   [ "${GIT_TARGET_BRANCH}" != "feature/community-tasks" ] && \
   [ "${GIT_TARGET_BRANCH}" != "feature/tensor_api_from_9.0.0" ];then
    echo "check md files"
    python3  ${SCRIPT_DIR}/check_md_files.py ${REPOSITORY_NAME} ${SCRIPT_DIR}/repo_md_files.yaml ${WORKSPACE}/pr_filelist_mod.txt ${WORKSPACE}
    DP_ASSERT_EQUAL "$?" "0" "Check ${REPOSITORY_NAME} md files " "true"
fi
# if [[ "${GIT_TARGET_BRANCH}" != @(8.5.0|9.0.0|r1.25.0|8.5.0-beta.1|9.0.0-beta.1|9.0.0-beta.2) && "${REPOSITORY_NAME}" == @(ops-nn|ops-cv|ops-math|ops-transformer) && "${sub_pipeline}x" != "truex" ]];then
#     bash -x ${WORKSPACE}/CI/pipeline/scripts/check_sensitive_words.sh
# fi
# if [[ "${REPOSITORY_NAME}" == "driver-dev" ]];then
#     python3  ${WORKSPACE}/CI/pipeline/scripts/check_ai_review.py ${REPOSITORY_NAME} ${GIT_PR_NUMBER} ${access_token} ${WORKSPACE}/pr_filelist.txt
# fi


