#!/bin/bash
set -e

export USE_CCACHE=1
export PATH=/usr/local/ccache/bin:$PATH
export CCACHE_SECONDARY_STORAGE=redis://10.0.0.135:6379
export CCACHE_COMPILERCHECK=content
export CCACHE_SLOPPINESS=include_file_mtime,time_macros,include_file_ctime
export CCACHE_UMASK=002
export CMAKE_CXX_COMPILER_LAUNCHER=/usr/local/ccache/bin/ccache

# 写入 ATOMGIT_ENV 使环境变量跨 step 传递
ENV_FILE="${ATOMGIT_ENV:-}"
if [ -n "${ENV_FILE}" ]; then
    echo "USE_CCACHE=1" >> "${ENV_FILE}"
    echo "PATH=/usr/local/ccache/bin:${PATH}" >> "${ENV_FILE}"
    echo "CCACHE_SECONDARY_STORAGE=redis://10.0.0.135:6379" >> "${ENV_FILE}"
    echo "CCACHE_COMPILERCHECK=content" >> "${ENV_FILE}"
    echo "CCACHE_SLOPPINESS=include_file_mtime,time_macros,include_file_ctime" >> "${ENV_FILE}"
    echo "CCACHE_UMASK=002" >> "${ENV_FILE}"
    echo "CMAKE_CXX_COMPILER_LAUNCHER=/usr/local/ccache/bin/ccache" >> "${ENV_FILE}"
fi

sudo apt update
sudo apt install -y redis-tools
sudo apt install -y libhiredis-dev
sudo apt install libhiredis0.14 || true
redis-cli -h 10.0.0.135 -p 6379 ping && echo "Redis connection OK" || echo "Redis connection FAILED"
/usr/local/ccache/bin/ccache -V
/usr/local/ccache/bin/ccache -z
