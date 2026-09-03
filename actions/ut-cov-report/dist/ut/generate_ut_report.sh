#!/bin/bash

# Usage:
#    Command: sh graphengine_st.sh -w workspace
#    Options:
#        -w: workspace directory


function genStReport(){
    read -ra modules <<< "${MODULES}"
    process_coverage_modules "${modules[@]}"
    echo "now merge info"
    mkdir -p ${WORKSPACE}/cov
    ls -al ${coverage_path}/
    cov_files=$(ls -a coverage*.info 2>/dev/null | grep -E '^coverage[^/]+\.info$')
    if [ -n "${cov_files}" ]; then
        readarray -t arr <<< "$(echo "${cov_files}" | tr ' ' '\n')"
        num=${#arr[@]}
        
        echo "找到 ${num} 个覆盖率文件: ${cov_files}"
        if [ ${num} -gt 1 ]; then
            echo "开始合并覆盖率报告"
            merge_cmd=""
            for cov_file in "${arr[@]}"; do
                if [ -f "${cov_file}" ]; then
                    merge_cmd="${merge_cmd} -a ${cov_file}"
                fi
            done
            
            # 执行合并命令
            echo "合并命令: lcov ${merge_cmd} -o coverage_merged.info"
            
            # 注意：这里在 lcov 和 ${merge_cmd} 之间需要空格
            lcov ${merge_cmd} -o coverage_merged.info --ignore-errors format
            # 检查合并是否成功
            if [ $? -eq 0 ] && [ -f "coverage_merged.info" ]; then
                echo "覆盖率报告合并成功: coverage_merged.info"
                cp -rf coverage_merged.info "${WORKSPACE}/coverage.info"
                # genhtml coverage_merged.info -o genhtml
                # tar -zcf genhtml genhtml.tar.gz
            else
                echo "覆盖率报告合并失败"
                exit 1
            fi
        else
            echo "只有一个覆盖率文件: ${cov_files}"
            # 复制到输出目录
            cp -a ${cov_files} "${WORKSPACE}/coverage.info"
        fi
    else
        echo "未找到任何覆盖率文件"
        exit 0
    fi
    coverage_info=$(find ${WORKSPACE} -maxdepth 1 -name "coverage.info" | head -n1)
    echo "coverage_info is ${coverage_info}"
    
    echo "run increment coverage tools"
    # lcov --list ${coverage_info}
    bash generate_ut_cov.sh ${UT_FIELD} ${SOURCE_BRANCH} "${WORKSPACE}" True ${coverage_info} ${COVERAGE_NUM} "${WORKSPACE}/pr_filelist_mod.txt"
    ret=$?
    # copy coverage report html
    coverage_path=$(find ${WORKSPACE} -name "cov" | head -n1)
    echo "coverage_report path is ${coverage_path} "
    if [ -d ${coverage_path} ];then
      echo "show coverage of all"
      cd ${coverage_path}
      tar -zcf ut_cov_${UT_FIELD}.tar.gz *
      cp -rf ut_cov_${UT_FIELD}.tar.gz ${WORKSPACE}
      # cp -a ut_cov.tar.gz ${CODE_PATH}
      # ls -l ${CODE_PATH}
    else
      echo "No coverage report found"
    fi
    if [ "${ret}x" == "0x" ];then
        exit 0
    else
        exit 1
    fi

}

function process_coverage_modules() {
    # 字符串转数组
    local modules=("$@")                
    local -A contents                     
    local module

    for module in "${modules[@]}"; do
        wget -nv "https://ascend-ci.obs.cn-north-4.myhuaweicloud.com/${OBS_PATH}/coverage_${module}.info"
        contents["$module"]=$(cat "ut_${module}.txt" | tr -d '\n')
    done

    # 检查所有模块的结果是否均为 "1"
    for module in "${modules[@]}"; do
        if [ "${contents[$module]}" != "1" ]; then
            return 1          # 存在非1的模块
        fi
    done
    echo "not need lcov"
    exit 0
}

function main(){
    #获取参数
    echo "++++++++++++++++++++++++++++++++++++++++++++++=="
    CURR_DIR=$(dirname "${BASH_SOURCE-$0}")
    CURR_DIR=$(cd -P "${CURR_DIR}" || exit; pwd -P)
    REPO_HOME=$(cd -P "${CURR_DIR}/../../../../" || exit; pwd -P)
    #统计责任田文件
    genStReport

}

main $@



