#!/bin/bash
set -euo pipefail
echo "组织org_name: ${org_name}"

REPOSITORY_NAME=$repo_name
WORKSPACE=${WORKSPACE}
GIT_PR_NUMBER=$MERGE_ID
BRANCH=$SOURCE_BRANCH
GIT_TARGET_BRANCH=$TARGET_BRANCH

cd ${WORKSPACE}

echo "===== 开始执行API文档生成与上报 ====="
python /home/api-doc/APIInfoGenTool/ops_analyser.py \
  -t ${REPOSITORY_NAME} \
  -c ${WORKSPACE}/build/ \
  -o /home/api_result \
  -p ${WORKSPACE} \
  --list pr_filelist_mod.txt \
  --mode full \
  --driver_path="/home/jenkins/opensource" \
  --diff_file update_file_detail.txt \
  --pathcheck_api_url http://10.0.0.193:10001/api/scan/path

python /home/api-doc/APIInfoGenTool/uploadData.py \
  -o /home/api_result \
  -t ${REPOSITORY_NAME} \
  --git_url "https://gitcode.com/${org_name}/${REPOSITORY_NAME}/pull/${GIT_PR_NUMBER}" \
  --branch "${BRANCH}" \
  --key ${GIT_PR_NUMBER} \
  -su "https://gitcode.com/${org_name}/${REPOSITORY_NAME}/pull/${GIT_PR_NUMBER}" \
  -sb "${BRANCH}" \
  -tu "https://gitcode.com/${org_name}/${REPOSITORY_NAME}.git" \
  -tb "${GIT_TARGET_BRANCH}" \
  --server_url "http://10.0.0.193:10001/api/import" \
  --mode full \
  --prefix ${WORKSPACE} \
  --driver_path="/home/jenkins/opensource"

echo "执行可用性检查脚本"
python /home/api-doc/APIInfoGenTool/usabilityCheck.py \
  --target ${REPOSITORY_NAME} \
  --out_dir /home/api_result \
  --key ${GIT_PR_NUMBER} \
  --git_url https://gitcode.com/${org_name}/${REPOSITORY_NAME}/pull/${GIT_PR_NUMBER} \
  --branch ${BRANCH} \
  --server_url http://10.0.0.193:10005/check

echo "===== API上报流程执行完成 ====="
exit 0

