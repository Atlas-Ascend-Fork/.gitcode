#!/bin/bash
#############
sc_tool_file=$(readlink -f "$0")  #获取当前脚本绝对路径
sc_tool_dir=$(dirname "$sc_tool_file")
echo "script directory: ${sc_tool_dir}"
echo ""
REPOSITORY_NAME=$2
WORKSPACE=$1
GIT_TARGET_BRANCH=$3
COMMIT_ID=$4
###### start markdownlint-cli2 check
tool_name="markdownlint"

cd ${WORKSPACE}
cp ${sc_tool_dir}/.markdownlint.json .   # 拷贝规则屏蔽文件到检查根目录
# 获取屏蔽目录和文件，空格隔开filter_str
# filter_str=$(python3 ${script_dir}/markdownlint_filter.py ${script_dir}/markdownlint_filter.yaml ${REPOSITORY_NAME})
# echo "filter_str:${filter_str}"
# IFS=' ' read -r -a filter_array <<< "${filter_str}"

markdownlint-cli2  "**/**/*.md" 2> markdown_result.txt

#cat markdown_result.txt
pr_filelist=${WORKSPACE}/pr_filelist.txt  #变更列表
result_md_file=${WORKSPACE}/${tool_name}.md  # 结果文件
touch ${result_md_file}
result_file=${WORKSPACE}/${tool_name}.csv
touch ${result_file}
# 结果进行处理，行号判断和屏蔽，输出markdownlint.md，workspace markdown_result.txt master pr_filelist.txt ops-nn
python3 ${sc_tool_dir}/markdownlint.py ${WORKSPACE} ${sc_tool_dir} \
     ${GIT_TARGET_BRANCH} ${pr_filelist} ${REPOSITORY_NAME} ${tool_name} ${COMMIT_ID}

#result_file=${WORKSPACE}/${tool_name}.md

echo "**********************"
cat ${result_md_file}
echo "**********************"

line_count=$(wc -l < "${result_md_file}")
mkdir -p  ${WORKSPACE}/build_out
if [ -f "${result_file}" ];then
    if [ "$line_count" -gt 0 ];then
        cp ${result_file} ${WORKSPACE}/build_out/
    else
        echo "pass"
        cp ${result_file} ${WORKSPACE}/build_out/
        line_count=0
    fi
else
    echo "${result_file} not found "
    # 结果文件不存在，则必须添加空文件，否则OBS会报错
    touch ${WORKSPACE}/build_out/${tool_name}.csv
    line_count=0
fi

exit $line_count
# 写入 StaticCheck.js 告警个数，上传到OBS（流水新增OBS上传）
#python3  ${WORKSPACE}/CI/cann/pipeline/bin/common/StaticCheck.py ${REPOSITORY_NAME} \
#          ${GIT_PR_NUMBER} ${line_count} ${tool_name} ${COMMIT_ID}
