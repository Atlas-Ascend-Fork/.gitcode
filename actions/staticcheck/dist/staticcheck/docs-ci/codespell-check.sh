#!/bin/bash
#######
script_file=$(readlink -f "$0")  #获取当前脚本绝对路径
# script_dir=/home/jenkins/share-data/gitcode/cann/ops-math-dev/code/compile/7427/ci/cann/pipeline/bin/common/docs-ci
script_dir=$(dirname "$script_file")
echo "script directory: ${script_dir}"
echo ""
pr_filelist=${WORKSPACE}/pr_filelist.txt  #变更文件
###### start codespell-check   英文单词拼写检查
# codespell_check
# tag_closed_check
# resource_existence_check
# lint_validity_check
tool_name="codespell_check"
# 工具检查前先安装npm依赖
cd ${WORKSPACE}
cp ${script_dir}/package.json  .
cp ${script_dir}/.npmrc  .
npm i
python3 ${script_dir}/docs-ci.py ${tool_name} \
    ${WORKSPACE} ${pr_filelist} ${script_dir} ${GIT_TARGET_BRANCH} ${REPOSITORY_NAME} ${ORGANIZATION_NAME}
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
# 写入 StaticCheck.js 告警个数，上传到OBS（流水新增OBS上传）
python3  ${WORKSPACE}/CI/cann/pipeline/bin/common/StaticCheck.py ${REPOSITORY_NAME} \
          ${GIT_PR_NUMBER} ${return_value} ${tool_name} ${COMMIT_ID}