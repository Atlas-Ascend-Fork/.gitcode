#!/bin/bash

WORKSPACE="$1"
package_path="$2"
package_type="$3"
cd "${WORKSPACE}"
compile_package_name=$(ls "${WORKSPACE}/${package_path}" | grep -E "\.${package_type}$" | head -n1)
echo "compile package name is: ${compile_package_name}"
if [[ -z "${compile_package_name}" ]]; then
    echo "ERROR: Not find *.${package_type} in  ${WORKSPACE}/${package_path}!"
    exit 1
fi
chmod +x ./${package_path}/${compile_package_name}
echo "y" | ./${package_path}/${compile_package_name} --full --install-path=${WORKSPACE}/tmp 2>&1 | tee ${WORKSPACE}/compile_log.txt
if grep -q "ERROR" ${WORKSPACE}/compile_log.txt; then
    echo "find key word 'ERROR' in logs"
    exit 1
else
    echo "verify the package: ${compile_package_name} success"
fi
echo "y" | ./${package_path}/${compile_package_name} --uninstall --install-path=${WORKSPACE}/tmp 2>&1 | tee ${WORKSPACE}/compile_uninstall_log.txt
if grep -qE "ERROR" ${WORKSPACE}/compile_uninstall_log.txt; then
    echo "find key word 'ERROR' in uninstall logs"
    exit 1
else
    echo "verify the package: ${compile_package_name} success"
fi
if [ ! -d "${WORKSPACE}/tmp" ]; then
    echo "uninstall success: directory removed"
elif [ -z "$(ls -A ${WORKSPACE}/tmp 2>/dev/null)" ]; then
    echo "uninstall success: directory empty"
    rmdir ${WORKSPACE}/tmp 2>/dev/null
else
    echo "uninstall failed: ${WORKSPACE}/tmp not empty"
    ls -la ${WORKSPACE}/tmp
    exit 1
fi