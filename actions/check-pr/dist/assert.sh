#!/bin/bash

# Color
Red='\e[0;31m'          # Red
Green='\e[0;32m'        # Green
BRed='\e[1;31m'         # Red
BGreen='\e[1;32m'       # Green
BCyan='\e[1;36m'        # Cyan
Purple='\e[0;35m'       # Purple
BPurple='\e[1;35m'      # Bold Purple
Color_Off='\e[0m'       # Text Reset
Now=`date +"%Y-%m-%d %H:%M:%S"`
# Log head
function LOG_HEAD() {
    local assert_msg=${1}
    date_time=$(date +%Y%m%d-%H%M%S)
    echo -e "\n[INFO] ${date_time} ${assert_msg}"
}

# Log info
function LOG_INFO() {
    local assert_msg=${1}
    date_time=$(date +%Y%m%d-%H%M%S)
    echo -e "[INFO] ${date_time} ${assert_msg}"
}

# Log error
function LOG_ERROR() {
    local assert_msg=${1}
    date_time=$(date +%Y%m%d-%H%M%S)
    echo -e "[ERROR] ${date_time} ${assert_msg}"
}

# Log command
function LOG_CMD() {
   local cmd="$*"
   date_time=$(date +%Y%m%d-%H%M%S)
   echo -e "[Command] ${date_time} ${cmd}"
}

# Print and execute command
function LOG_DO() {
   local cmd="$*"
   date_time=$(date +%Y%m%d-%H%M%S)
   echo -e "[Command]${date_time} ${cmd}"
   ${cmd}
}

# Assert A is equal to B
# True: equal
# False: not equal
function DP_ASSERT_EQUAL() {
    local actual_value=${1}
    local expect_value=${2}
    local assert_msg=${3}
    local log_flag=${4:-"true"}
    local log_path=${5}
    if [ "${actual_value}" != "${expect_value}" ]; then
        if [ -n "${log_path}" ] && [ -f "${log_path}" ]; then
            cat ${log_path}
        fi
        LOG_ERROR "${assert_msg} is failed."
        exit 1
    else
        if [ "${log_flag}" = "true" ]; then
            LOG_INFO "${assert_msg} is success."
        fi
    fi
}

function DP_ASSERT_CHECK_SKIP() {
    local actual_value=${1}
    local assert_msg=${2}
    if [ "${actual_value}" != "0" ] && [ "${actual_value}" != "200" ]; then
        LOG_ERROR "${assert_msg} is failed."
        exit 1
    else
        LOG_INFO "${assert_msg} is success."
    fi
}

# Assert A is not equal to B
# True: not equal
# False: equal
function DP_ASSERT_NOT_EQUAL() {
    local actual_value=${1}
    local expect_value=${2}
    local assert_msg=${3}
    local log_flag=${4:-"true"}
    local log_path=${5}
    if [ "${actual_value}" = "${expect_value}" ]; then
        if [ -n "${log_path}" ] && [ -f "${log_path}" ]; then
            cat ${log_path}
        fi
        LOG_ERROR "${assert_msg} is failed."
        exit 1
    else
        if [ "${log_flag}" = "true" ]; then
            LOG_INFO "${assert_msg} is success."
        fi
    fi
}

# Check to see if the file exist
function DP_ASSERT_FILE () {
    local file_name=${1}
    local assert_msg=${2}
    local log_flag=${3:-"true"}
    if [ ! -f "${file_name}" ]; then
        LOG_ERROR "${assert_msg} is failed."
        exit 1
    else
        if [ "${log_flag}" = "true" ]; then
            LOG_INFO "${assert_msg} is success."
        fi
    fi
}

# Check to see if the file empty
function DP_ASSERT_FILE_EMPTY () {
    local file_name=${1}
    local assert_msg=${2}
    local log_flag=${3:-"true"}
    if [ ! -s "${file_name}" ]; then
        LOG_ERROR "${assert_msg} is failed."
        exit 1
    else
        if [ "${log_flag}" = "true" ]; then
            LOG_INFO "${assert_msg} is success."
        fi
    fi
}

# Check to see if the directory exist
function DP_ASSERT_DIRECTORY () {
    local file_name=${1}
    local assert_msg=${2}
    local log_flag=${3:-"true"}
    if [ ! -d "${file_name}" ]; then
        LOG_ERROR "${assert_msg} is failed."
        exit 1
    else
        if [ "${log_flag}" = "true" ]; then
            LOG_INFO "${assert_msg} is success."
        fi
    fi
}

# Check to see if the string empty
function DP_ASSERT_STRING_EMPTY() {
    local var=${1}
    if [ -z "${var}" ]; then
        LOG_ERROR "String is empty."
        exit 1
    fi
}

function redis_ccache() {
    export USE_CCACHE=1
    export PATH=/usr/local/ccache/bin:$PATH
    export CCACHE_SECONDARY_STORAGE=redis://10.0.0.135:6379
    export CCACHE_COMPILERCHECK=content
    export CCACHE_SLOPPINESS=include_file_mtime,time_macros,include_file_ctime
    export CCACHE_UMASK=002
    export CMAKE_CXX_COMPILER_LAUNCHER=/usr/local/ccache/bin/ccache
    # export CCACHE_DEBUG=1
    # export CCACHE_DEBUG=true
    sudo apt update
    sudo apt install -y redis-tools
    sudo apt install -y libhiredis-dev
    sudo apt install libhiredis0.14
    redis-cli -h 10.0.0.135 -p 6379 ping && echo "Redis connection OK" || echo "Redis connection FAILED"
    /usr/local/ccache/bin/ccache -V
    /usr/local/ccache/bin/ccache -z  
}

