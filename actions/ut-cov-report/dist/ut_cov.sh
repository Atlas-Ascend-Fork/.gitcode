#!/bin/bash

GIT_TOKEN="${GIT_TOKEN:-}"
cd "${WORKSPACE}"

# 先拿到原始远程地址
ORIG_URL=$(git remote get-url origin)
echo ${ORIG_URL}

# 配置远端分支映射规则
git config --local remote.origin.fetch "+refs/heads/*:refs/remotes/origin/*"

# if [[ -n "${GIT_TOKEN}" ]]; then
#   AUTH_URL=$(echo "$ORIG_URL" | sed "s|https://|https://cann-robot:${GIT_TOKEN}@|")
#   git fetch "${AUTH_URL}" "+refs/heads/*:refs/remotes/origin/*" --unshallow
# else
#   echo "未传入GIT_TOKEN，直接拉取公开仓库"
#   git fetch origin "+refs/heads/*:refs/remotes/origin/*" --unshallow
# fi

if [[ -n "${GIT_TOKEN}" ]]; then
  AUTH_URL=$(echo "$ORIG_URL" | sed "s|https://|https://cann-robot:${GIT_TOKEN}@|")
  git fetch "${AUTH_URL}" "${TARGET_BRANCH}:refs/remotes/origin/${TARGET_BRANCH}" --unshallow
else
  echo "公开仓库，无Token直接拉取"
  git fetch origin "${TARGET_BRANCH}" --unshallow
fi

if [ "${COV_MODE}" = "report" ];then
    cd "${SCRIPT_DIR}/ut"
    chmod +x ./addlcov
    if [ "${UT_FIELD}" = "ops-transformer" ];then
        python3 ${WORKSPACE}/cmake/scripts/convert_yaml.py ${WORKSPACE}/tests/test_config.yaml
        yaml_path="${WORKSPACE}/tests/test_config.yaml"
    else
        yaml_path="${WORKSPACE}/classify_rule.yaml"
    fi
    python3 count_files.py "${yaml_path}" "${UT_FIELD}" "${WORKSPACE}" "${WORKSPACE}"
    bash generate_ut_report.sh
else
    echo "${UT_PROCESS}"
    if [ "${UT_PROCESS}" = "ut_cov" ];then
      cd "${SCRIPT_DIR}/ut"
      chmod +x ./addlcov
      if [ "${LANGUAGE}" != "ts" ];then
          python3 count_files.py "${WORKSPACE}/classify_rule.yaml" "${UT_TYPE}" "${WORKSPACE}" "${WORKSPACE}"
      fi
      if [ "${LANGUAGE}" = "cpp" ];then
          bash generate_ut_cov.sh "${UT_TYPE}" "${TARGET_BRANCH}" "${WORKSPACE}" True "${WORKSPACE}/cov/coverage.info" "${COVERAGE_NUM}" "${WORKSPACE}/pr_filelist_mod.txt"
          coverage_path=$(find "${WORKSPACE}" -name "cov" | head -n1)
          cd "${coverage_path}"
          tar -zcf ut_cov_${UT_TYPE}.tar.gz *
          cp -rf ut_cov_${UT_TYPE}.tar.gz "${WORKSPACE}"
      elif [ "${LANGUAGE}" = "python" ];then
          bash generate_ut_cov_python.sh
      elif [ "${LANGUAGE}" = "ts" ];then
          bash generate_ut_cov_ts.sh
      fi
    elif [ "${UT_PROCESS}" = "coverage" ];then
      cd "${WORKSPACE}"
      # 打印环境变量，确认工作目录
      echo "DEBUG WORKSPACE: [${WORKSPACE}]"
      echo "DEBUG UT_TYPE: [${UT_TYPE}]"

      # 查找 ops.info
      coverage_info=$(find "${WORKSPACE}" -type f -name "ops.info" | head -n1)
      echo "DEBUG 第一轮find ops.info: [${coverage_info}]"

      # 为空则查 coverage.info
      if [[ -z "${coverage_info}" ]]; then
          coverage_info=$(find "${WORKSPACE}" -type f -name "coverage.info" | head -n1)
          echo "DEBUG 第二轮find coverage.info: [${coverage_info}]"
      fi

      # 双重校验：变量非空 + 文件真实存在
      if [[ -z "${coverage_info}" ]]; then
          echo "ERROR: 未找到 ops.info / coverage.info 任意文件"
          exit 0
      fi
      if [[ ! -f "${coverage_info}" ]]; then
          echo "ERROR: 找到的路径不存在文件: ${coverage_info}"
          ls -la "${WORKSPACE}"
          exit 0
      fi

      # 拷贝、重命名，所有变量加双引号兼容空格路径
      cp -f "${coverage_info}" ./coverage.info
      mv ./coverage.info "./coverage_${UT_TYPE}.info"
    fi
fi
