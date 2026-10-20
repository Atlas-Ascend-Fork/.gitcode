#!/bin/bash

GIT_TOKEN="${GIT_TOKEN:-}"

# ---- 软放行判定：仓库参数 UT_SOFT_FAIL_REPOS 已配置（非空）→ 失败也 exit 0；未配置 → 拦截 ----
fail_exit()
{
    local rc="${1:-1}"
    [ "$rc" -eq 0 ] && exit 0
    if [ "${UT_SOFT_FAIL_REPOS:-}" = "true" ]; then
        echo "::warning::覆盖率收集失败(rc=${rc})，仓库参数 UT_SOFT_FAIL_REPOS=true，软放行"
        exit 0
    fi
    echo "[ERROR] 覆盖率收集失败(rc=${rc})，仓库参数 UT_SOFT_FAIL_REPOS 未配置或为 false，拦截"
    exit "$rc"
}

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
    python3 count_files.py "${yaml_path}" "${UT_FIELD}" "${WORKSPACE}" "${WORKSPACE}" || fail_exit "$?"
    bash generate_ut_report.sh || fail_exit "$?"
else
    echo "${UT_PROCESS}"
    if [ "${UT_PROCESS}" = "ut_cov" ];then
      cd "${SCRIPT_DIR}/ut"
      chmod +x ./addlcov
      if [ "${LANGUAGE}" != "ts" ];then
          python3 count_files.py "${WORKSPACE}/classify_rule.yaml" "${UT_TYPE}" "${WORKSPACE}" "${WORKSPACE}" || fail_exit "$?"
      fi
      if [ "${LANGUAGE}" = "cpp" ];then
          bash generate_ut_cov.sh "${UT_TYPE}" "${TARGET_BRANCH}" "${WORKSPACE}" True "${WORKSPACE}/cov/coverage.info" "${COVERAGE_NUM}" "${WORKSPACE}/pr_filelist_mod.txt" \
              || fail_exit "$?"
          coverage_path=$(find "${WORKSPACE}" -name "cov" | head -n1)
          if [ -n "${coverage_path}" ] && [ -d "${coverage_path}" ]; then
              cd "${coverage_path}"
              tar -zcf ut_cov_${UT_TYPE}.tar.gz * || fail_exit 3
              cp -rf ut_cov_${UT_TYPE}.tar.gz "${WORKSPACE}" || fail_exit 4
          else
              echo "[ERROR] 未找到 cov 目录"
              fail_exit 2
          fi
      elif [ "${LANGUAGE}" = "python" ];then
          bash generate_ut_cov_python.sh || fail_exit "$?"
      elif [ "${LANGUAGE}" = "ts" ];then
          bash generate_ut_cov_ts.sh || fail_exit "$?"
      fi
    elif [ "${UT_PROCESS}" = "coverage" ];then
      cd "${WORKSPACE}"
      # 打印环境变量，确认工作目录
      echo "DEBUG WORKSPACE: [${WORKSPACE}]"
      echo "DEBUG UT_TYPE: [${UT_TYPE}]"

      # A native UT run may combine builtin and experimental scopes. Prefer its
      # explicit merged artifact to an arbitrary last-scope build/ops.info.
      merged_scopes="${WORKSPACE}/ut_${UT_TYPE}_scopes.info"
      if [[ -s "${merged_scopes}" ]]; then
          coverage_info="${merged_scopes}"
      else
          coverage_info=$(find "${WORKSPACE}" -type f -name "ops.info" | head -n1)
      fi
      echo "DEBUG 第一轮find ops.info: [${coverage_info}]"

      # 为空则查 coverage.info
      if [[ -z "${coverage_info}" ]]; then
          coverage_info=$(find "${WORKSPACE}" -type f -name "coverage.info" | head -n1)
          echo "DEBUG 第二轮find coverage.info: [${coverage_info}]"
      fi

      # 双重校验：变量非空 + 文件真实存在
      if [[ -z "${coverage_info}" ]]; then
          echo "ERROR: 未找到 ops.info / coverage.info 任意文件"
          fail_exit 1
      fi
      if [[ ! -f "${coverage_info}" ]]; then
          echo "ERROR: 找到的路径不存在文件: ${coverage_info}"
          ls -la "${WORKSPACE}"
          fail_exit 1
      fi

      # 拷贝、重命名，所有变量加双引号兼容空格路径
      cp -f "${coverage_info}" ./coverage.info
      mv ./coverage.info "./coverage_${UT_TYPE}.info"
    fi
fi
# 收尾：成功或软放行清单内 → exit 0；否则透传失败码拦截
fail_exit 0
