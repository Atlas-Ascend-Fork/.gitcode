#!/bin/bash
# ===========================================================================================================
# check_yaml.sh — YAML 格式问题检测
#
# 用法:
#   ./check_yaml.sh <yaml文件...>      直接检查指定的 yaml
#   ./check_yaml.sh <filelist.txt>     从 pr_filelist.txt 提取修改的 .yaml/.yml 并检查
#   ./check_yaml.sh                    缺省检查 images.yaml
#
# 检查项（按约定，GBK 注释与 CRLF 不算问题，不做误报）:
#   [ERROR] TAB       —— 行内出现影响解析的 TAB：缩进TAB/空格+TAB混合缩进/行中TAB/行尾TAB
#   [ERROR] 行尾空白    —— 行尾纯空格（asc-stl PR 那种；TAB 结尾由 TAB 检查覆盖）
#   [ERROR] 全角/隐形字符 —— 键位全角冒号"："、全角空格、零宽空格、行中 BOM（中文输入法常见手误）
#   [ERROR] 重复键       —— 同一层级出现同名 key（会静默覆盖，需 PyYAML，缺失则跳过）
#   [INFO]  结构解析     —— 尽力而为（utf-8 → gbk 容忍解码）
#
# 退出码: 0=通过或无 yaml 需检查；1=存在问题
# ===========================================================================================================
rc=0
yaml_count=0

check_one() {
    local f="$1"
    echo "===== 检查: $f ====="
    if [ ! -f "$f" ]; then
        echo "[ERROR] 文件不存在: $f"
        return 1
    fi

    err=0

    # 1) TAB 检查（引号/注释感知：只报影响解析的 TAB，见 python 段）
    #    无 python 时退化为全量 grep（宁严勿漏）
    PY="$(command -v python3 || command -v python)"
    if [ -z "$PY" ]; then
        tabs=$(grep -nP '\t' "$f")
        if [ -n "$tabs" ]; then
            err=1
            echo "[ERROR] TAB 字符（无 python 环境，按最严格口径全报）:"
            echo "$tabs" | head -20 | while IFS= read -r l; do
                n="${l%%:*}"
                echo "  行 $n: $(sed -n "${n}p" "$f" | cat -A | cut -c1-80)"
            done
        fi
    fi

    # 2) 行尾空白（纯空格结尾；TAB 结尾已由 TAB 检查覆盖，不重复报）
    tws=$(grep -nP '\S[ ]+\r?$' "$f")
    if [ -n "$tws" ]; then
        err=1
        cnt=$(echo "$tws" | wc -l)
        echo "[ERROR] 行尾空白（纯空格，${cnt} 行）:"
        echo "$tws" | head -20 | while IFS= read -r l; do
            n="${l%%:*}"
            echo "  行 $n: $(sed -n "${n}p" "$f" | cat -A | cut -c1-80)"
        done
        [ "$cnt" -gt 20 ] && echo "  ... 其余 $((cnt-20)) 行略"
    fi

    # 3) TAB(引号/注释感知) + 全角/隐形字符 + 重复键 + 结构解析（python）
    if [ -n "$PY" ]; then
        "$PY" - "$f" <<'PYEOF'
import re, sys
raw = open(sys.argv[1], "rb").read()
text = None
for enc in ("utf-8", "gbk", "latin-1"):
    try:
        text = raw.decode(enc)
        break
    except UnicodeDecodeError:
        continue
bad = 0

def tab_affects_parse(line):
    """TAB 是否影响解析：引号外且注释外的 TAB 才影响（PyYAML 实测口径）"""
    in_d = in_s = False
    i, n = 0, len(line)
    while i < n:
        c = line[i]
        if in_d:
            if c == "\\":
                i += 2
                continue
            if c == '"':
                in_d = False
        elif in_s:
            if c == "'":
                if i + 1 < n and line[i + 1] == "'":
                    i += 2
                    continue
                in_s = False
        else:
            if c == '"':
                in_d = True
            elif c == "'":
                in_s = True
            elif c == "#" and (i == 0 or line[i - 1] in " \t"):
                return False
            elif c == "\t":
                return True
        i += 1
    return False

for i, ln in enumerate(text.splitlines(), 1):
    body = ln.rstrip("\r")
    if tab_affects_parse(body):
        print(f"[ERROR] 行 {i}: TAB 影响解析（缩进/分隔区；引号与注释内的 TAB 不报）: {body.strip()[:60]}")
        bad = 1
    if "\u3000" in body:
        print(f"[ERROR] 行 {i}: 全角空格(U+3000)"); bad = 1
    if "\u200b" in body or "\ufeff" in body:
        print(f"[ERROR] 行 {i}: 零宽字符/BOM混入"); bad = 1
    if re.match(r'^\s*[\w.-]+：', body):
        print(f"[ERROR] 行 {i}: 键位使用了全角冒号'：'"); bad = 1
try:
    import yaml
except ImportError:
    print("[INFO] 环境无 PyYAML，跳过重复键与结构校验")
    sys.exit(1 if bad else 0)

class UniqueKeyLoader(yaml.SafeLoader):
    pass
def _no_dup(loader, node, deep=False):
    seen = set()
    for k_node, _ in node.value:
        k = loader.construct_object(k_node, deep=True)
        if k in seen:
            raise yaml.MarkedYAMLError(
                f"重复键: {k!r} (行 {k_node.start_mark.line + 1})",
                k_node.start_mark)
        seen.add(k)
    return yaml.SafeLoader.construct_mapping(loader, node, deep)
UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_dup)

try:
    yaml.load(text, Loader=UniqueKeyLoader)
    if not bad:
        print("[INFO] 结构与重复键检查通过（容忍编码模式）")
except yaml.YAMLError as e:
    print("[ERROR]", str(e).splitlines()[0])
    bad = 1
sys.exit(1 if bad else 0)
PYEOF
        [ $? -ne 0 ] && err=1
    fi

    if [ "$err" -eq 1 ]; then
        echo "结论: 存在 ERROR，需要修复"
        return 1
    fi
    echo "结论: 通过"
    return 0
}

# ---- 从 filelist 提取 yaml 修改文件（相对路径基于 ${WORKSPACE} 解析，未设置则用当前目录） ----
check_filelist() {
    local list="$1" f raw found=0 target
    local base="${WORKSPACE:-.}"
    if [ ! -f "$list" ]; then
        echo "[ERROR] filelist 不存在: $list"
        return 1
    fi
    while IFS= read -r raw; do
        f="${raw%$'\r'}"
        f="${f#\"}"; f="${f%\"}"
        f="${f#\xef\xbb\xbf}"
        f="${f#./}"
        case "$f" in \#*|"") continue ;; esac
        case "$f" in
            *.yaml|*.yml)
                case "$f" in
                    /*) target="$f" ;;
                    *)  target="${base}/${f}" ;;
                esac
                if [ -f "$target" ]; then
                    found=$((found + 1))
                    check_one "$target" || rc=1
                else
                    echo "[WARN] filelist 中的 yaml 不存在: $target"
                fi
                ;;
        esac
    done < "$list"
    yaml_count=$found
    if [ "$found" -eq 0 ]; then
        echo "filelist 中没有修改的 yaml 文件，免检"
    else
        echo "filelist 提取 yaml: ${found} 个"
    fi
}

# ---- 分发 ----
ARGS=("$@")
[ ${#ARGS[@]} -eq 0 ] && ARGS=("images.yaml")

for arg in "${ARGS[@]}"; do
    case "$arg" in
        *.yaml|*.yml)
            yaml_count=$((yaml_count + 1))
            check_one "$arg" || rc=1
            ;;
        *)
            check_filelist "$arg" || rc=1
            ;;
    esac
done

[ "$yaml_count" -gt 0 ] && echo "共检查 yaml: ${yaml_count} 个"
exit "$rc"
