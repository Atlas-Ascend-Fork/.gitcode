#!/bin/bash
#######
sc_tool_file=$(readlink -f "$0")  #获取当前脚本绝对路径
# script_dir=/home/jenkins/share-data/gitcode/cann/ops-math-dev/code/compile/7427/ci/cann/pipeline/bin/common/docs-ci
sc_tool_dir=$(dirname "$sc_tool_file")
echo "script directory: ${sc_tool_dir}"
echo "1111111111111111111111111111111111111111"

REPOSITORY_NAME=$2
WORKSPACE=$1
GIT_TARGET_BRANCH=$3
COMMIT_ID=$4
tool_name=$5
pr_filelist=${WORKSPACE}/pr_filelist.txt  #变更文件
###### start codespell-check   英文单词拼写检查
# codespell_check
# tag_closed_check
# resource_existence_check
# link_validity_check
# tool_name="codespell_check"
# 工具检查前先安装npm依赖
cd ${WORKSPACE}
cp ${sc_tool_dir}/package.json  .
cp ${sc_tool_dir}/.npmrc  .
echo "222222222222222222222222222222222222222"
npm i > /dev/null 2>&1
echo "3333333333333333333333333333"
python3 ${sc_tool_dir}/docs-ci.py ${tool_name} \
    ${WORKSPACE} ${pr_filelist} ${sc_tool_dir} ${GIT_TARGET_BRANCH} ${REPOSITORY_NAME} ${COMMIT_ID}
return_value=$?
echo "warning num: ${return_value}"
output_file=${WORKSPACE}/output.md
#result_file=${WORKSPACE}/${tool_name}.md
result_file=${WORKSPACE}/${tool_name}.csv
#cat ${output_file}
mkdir -p ${WORKSPACE}/build_out/
if [ -f "$result_file" ];then
    # 告警大于0扫描有告警
    if [ ${return_value} -gt 0 ];then
        cp ${result_file} ${WORKSPACE}/build_out/
    else
        echo "pass ${return_value}, no warning, success"
        cp ${result_file} ${WORKSPACE}/build_out/
        return_value=0
    fi
else
    echo "${result_file} not found "
    # 结果文件不存在，则必须添加空文件，否则OBS会报错
    touch ${WORKSPACE}/build_out/${tool_name}.csv
    return_value=0
fi

if { [[ "$tool_name" = "resource_existence_check" ]] || [[ "$tool_name" = "link_validity_check" ]]; } && [[ "$return_value" -ne 0 ]]; then
    exit "$return_value"
fi

