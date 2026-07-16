#!/bin/bash
set -e

export USE_CCACHE=1
export PATH=/usr/local/ccache/bin:$PATH
export CCACHE_SECONDARY_STORAGE=redis://10.0.0.135:6379
export CCACHE_COMPILERCHECK=content
export CCACHE_SLOPPINESS=include_file_mtime,time_macros,include_file_ctime
export CCACHE_UMASK=002
export CMAKE_CXX_COMPILER_LAUNCHER=/usr/local/ccache/bin/ccache

sudo apt update
sudo apt install -y redis-tools
sudo apt install -y libhiredis-dev
sudo apt install libhiredis0.14 || true
redis-cli -h 10.0.0.135 -p 6379 ping && echo "Redis connection OK" || echo "Redis connection FAILED"
/usr/local/ccache/bin/ccache -V
/usr/local/ccache/bin/ccache -z
