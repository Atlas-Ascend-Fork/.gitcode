# -*- coding: utf-8 -*-
"""
CANN PR 门禁检测：开源依赖与 URL 白名单检查。

门禁文件：oss_dep_security_gate_<branch>.json（如 master 分支为
oss_dep_security_gate_master.json），由 sbom 扫描工程对各仓扫描生成，
每仓 key 结构：branch / CANN_CMAKE_TAG / url / opensource_c /
opensource_py / opensource_js。

检测逻辑：
1. 获取开发者提交的代码 patch（优先读取 get-pr 产出的 update_file_detail.txt，
   即 git diff -U0 -w --no-renames origin/<target_branch>...HEAD 的输出；
   文件不存在时尝试在代码仓内重新生成），提取新增行中的：
   - URL 链接（http/https）
   - C/C++ 三方库引用（add_cann_third_party(xxx)）
   - Python 依赖声明（*requirements*.txt 新增行、脚本中
     pip install <name><op><version> 引入行）
   - NodeJS 依赖声明（package.json 新增的 "name": "version" 行）
   若均未涉及，门禁直接通过。
2. 读取目标分支对应的门禁文件，代码仓不在文件 key 中：此代码仓不作检查
   管控，门禁通过。
3. 代码仓受控时：
   (1) url 白名单：新增 URL 必须在 url 属性内（完全匹配或带边界字符的
       前缀匹配）。URL 不在 url 白名单内时，若能识别为 Python/NodeJS
       依赖组件 URL（pypi 项目页、whl/tgz 制品、npm registry 制品等），
       且组件版本仍满足 opensource_py / opensource_js 的版本约束，
       依然准许合入（宽范围版本放行）。
   (2) opensource_c 白名单：新增三方库引用必须在 opensource_c 属性内。
   (3) opensource_py / opensource_js 版本管控（依赖文件与脚本引入的
       依赖组件）：
       - 组件在白名单内且版本满足约束：放行；
       - 版本号大于白名单允许版本（或落在约束范围外）：若 PR 已在相应
         依赖文件（requirements.txt / package.json）同步声明该组件版本，
         视为已完成版本同步更新，放行；否则拦截，并提示需要在相应依赖
         文件 requirements.txt 或 package.json 同步更新版本号；
       - 组件不在白名单内：拦截（新组件需先进入门禁基线）。
   全部通过则门禁通过，否则门禁拦截并以非 0 退出。
   脚本内部异常按拦截处理（fail-closed）；patch/门禁文件缺失等数据类
   失败按放行处理（fail-open，避免 CI 基础设施故障误伤）。

用法：
    python3 check_oss_dep.py <WORKSPACE> <REPOSITORY_NAME> <GIT_TARGET_BRANCH>

退出码：0 门禁通过；1 门禁拦截
"""

import json
import os
import re
import subprocess
import sys

try:
    from urllib.parse import unquote
except ImportError:  # py2 兜底
    from urllib import unquote

THIS_FILE_PATH = os.path.dirname(os.path.realpath(__file__))

GATE_FILE_PREFIX = "oss_dep_security_gate_"

URL_PATTERN = re.compile(r'https?://[^\s"\'<>\)\\]+', re.IGNORECASE)

THIRD_PARTY_PATTERN = re.compile(
    r'add_cann_third_party\s*\(\s*["\']?([A-Za-z0-9_\-\.]+)["\']?\s*\)',
    re.IGNORECASE,
)

BRANCH_NAME_PATTERN = re.compile(r'^[A-Za-z0-9._\-]+$')

# Python 依赖文件（*requirements*.txt）
PY_REQ_FILE_RE = re.compile(r'(^|/)requirements[\w.-]*\.txt$', re.IGNORECASE)

# NodeJS 依赖清单（package.json / package-lock.json）
JS_FILE_RE = re.compile(r'(^|/)package(-lock)?\.json$')

# package.json 中承载依赖的 section
JS_SECTION_KEYS = ('dependencies', 'devDependencies', 'optionalDependencies',
                   'peerDependencies', 'overrides')

# package.json 中用于跟踪上下文的 section（含非依赖 section）
JS_SECTION_LINE_RE = re.compile(
    r'"({})"\s*:'.format('|'.join(
        JS_SECTION_KEYS + ('engines', 'scripts', 'resolutions'))))

# package.json 中需要跳过的非依赖 key（section 上下文缺失时兜底过滤）
JS_BLOCKED_KEYS = {
    'name', 'version', 'type', 'main', 'module', 'types', 'typings', 'files',
    'license', 'licence', 'author', 'description', 'private', 'sideEffects',
    'exports', 'imports', 'homepage', 'repository', 'keywords', 'engines',
    'os', 'cpu', 'funding', 'resolutions', 'packageManager', 'resolved',
    'integrity', 'dev', 'optional', 'peer', 'hasInstallScript', 'bin',
    'directories', 'scripts', 'url', 'email', 'icon', 'displayName',
    'publisher', 'categories', 'activationEvents', 'contributes',
}

# 依赖版本约束的大致形态（用于识别 "name": "version" 依赖行）
JS_SPEC_SHAPE = re.compile(
    r'^(\^|~|>=|<=|>|<|=|\*|v?\d|workspace:|file:|npm:|github:|link:'
    r'|git\+|latest$|https?://)')

# 脚本中的 pip 安装引入（如 build.sh 内 pip3 install torch-npu==2.6.1.post1）：
# 属于"引入"而非"登记"，引入版本超出白名单时需 PR 内依赖文件同步声明
PIP_INSTALL_RE = re.compile(
    r'\bpip3?\s+install\s+(?:-\S+\s+)*'
    r'([A-Za-z0-9][A-Za-z0-9._-]*)\s*(==|>=|<=|>|<|~=)\s*([A-Za-z0-9][\w.+*-]*)',
    re.IGNORECASE)

# URL 末尾可能粘连的标点（ASCII 标点、markdown 反引号、全角/中文标点等）
TRAILING_PUNCTUATION = '.,;:!?)]}>\'"`」〉》】〕』”’），；。？！、'

# 全角标点：中文语境下 URL 常与后续说明文字直接粘连（无空格）
FULLWIDTH_CUT_CHARS = '，。；：？！、（）「」『』《》〈〉【】〔〕［］“”‘’'

# URL 前缀匹配时允许的边界字符，防止 https://gitcode.com 匹配
# https://gitcode.com.evil.com 这类旁路；} 用于兼容白名单中被截断的
# 占位符条目（如 https://xxx/${obs_path）
PREFIX_BOUNDARY_CHARS = ('/', '?', '#', '&', ';', '}')

# ---------------- 版本比较（PEP440-lite / semver-lite） ----------------


def _ver_tuple(v, size=5):
    parts = []
    for seg in str(v).split('.'):
        m = re.match(r'^(\d+)', seg)
        if not m:
            break
        parts.append(int(m.group(1)))
    while len(parts) < size:
        parts.append(0)
    return tuple(parts[:size])


def py_ver_key(v):
    """Python 版本 -> 可比较 key（忽略 local 段，支持 post/dev/rc 后缀）"""
    v = str(v).strip().lower()
    if not v:
        return ((_ver_tuple('0'), (1, 0, 0)))
    v = v.split('+', 1)[0]
    post = None
    m = re.search(r'[.\-_](?:post|rev|r)(\d+)$', v)
    if m:
        post = int(m.group(1))
        v = v[:m.start()]
    pre = None
    m = re.search(r'[.\-_](dev|a|b|rc)(\d+)$', v)
    if m:
        pre = (m.group(1), int(m.group(2)))
        v = v[:m.start()]
    nums = _ver_tuple(v)
    if pre:
        phase = (0, {'dev': 0, 'a': 1, 'b': 2, 'rc': 3}[pre[0]], pre[1])
    elif post is not None:
        phase = (2, 0, post)
    else:
        phase = (1, 0, 0)
    return (nums, phase)


def js_ver_key(v):
    """NodeJS semver 版本 -> 可比较 key"""
    v = str(v).strip().lower().lstrip('v')
    if not v:
        return _ver_tuple('0')
    return _ver_tuple(v.split('+', 1)[0])


def _bump_at(nums, idx):
    """在 idx 段进位，其后（前 3 段内）清零：(3,5,32,0,0)@1 -> (3,6,0,0,0)"""
    out = list(nums)
    out[idx] = out[idx] + 1
    for j in range(idx + 1, 3):
        out[j] = 0
    return tuple(out)


def _bump_partial(val):
    """部分版本上界：'2.1' -> <2.2.0；'2' -> <3.0.0（按原有段数进位）"""
    segs = [s for s in str(val).split('.') if s != '']
    return _bump_at(_ver_tuple(val), max(len(segs) - 1, 0))


def _bump_penultimate(val):
    """次末段进位上界：'1.4.5' -> <1.5.0；'2.2' -> <3.0.0（~= / ~ 语义）"""
    segs = [s for s in str(val).split('.') if s != '']
    return _bump_at(_ver_tuple(val), max(len(segs) - 2, 0))


def _ver_str(nums):
    return '.'.join(str(x) for x in nums)


PY_SPEC_ATOM_RE = re.compile(r'^(==|>=|<=|>|<|~=|\*|=)\s*(.*)$')


def parse_py_spec(spec):
    """
    解析 Python 版本约束为 [[(op, key), ...], ...]（|| 分支 -> 逗号原子）。
    '*' / 空约束 -> 空原子列表（恒真）；无法解析返回 None。
    """
    branches = []
    for part in str(spec).split('||'):
        part = part.strip()
        if not part:
            branches.append([])
            continue
        atoms = []
        for atom in part.split(','):
            atom = atom.strip()
            if not atom or atom == '*':
                continue
            m = PY_SPEC_ATOM_RE.match(atom)
            if not m:
                return None
            op, val = m.group(1), m.group(2).strip()
            if val in ('', '*'):
                continue
            if val.endswith('.*'):
                base = val[:-2]
                atoms.append(('>=', py_ver_key(base)))
                atoms.append(('<', py_ver_key(_ver_str(_bump_partial(base)))))
                continue
            if op == '=':
                op = '=='
            if op == '~=':
                atoms.append(('>=', py_ver_key(val)))
                atoms.append(('<', py_ver_key(_ver_str(_bump_penultimate(val)))))
                continue
            try:
                atoms.append((op, py_ver_key(val)))
            except Exception:
                return None
        branches.append(atoms)
    return branches


JS_NON_RANGE_PREFIX_RE = re.compile(
    r'^(workspace:|file:|npm:|github:|link:|git\+|https?://)')
JS_TOKEN_RE = re.compile(r'^([\^~]|>=|<=|>|<|=)?\s*(.+)$')


def _parse_js_token(tok):
    """单个 semver token -> [(op, key), ...]；'*'/无法解析 -> []（无约束）"""
    tok = tok.strip()
    if not tok or tok in ('*', 'x', 'X', 'latest'):
        return []
    if JS_NON_RANGE_PREFIX_RE.match(tok):
        return []
    m = JS_TOKEN_RE.match(tok)
    if not m:
        return None
    op, val = (m.group(1) or ''), m.group(2).strip()
    if not re.match(r'^v?\d', val):
        return None
    nums = _ver_tuple(val.lstrip('v'))
    segs = val.lstrip('v').split('.')
    if op == '^':
        if nums[0] > 0:
            upper = _bump_at(nums, 0)
        elif len(segs) > 1 and nums[1] > 0:
            upper = _bump_at(nums, 1)
        else:
            upper = _bump_at(nums, 2)
        return [('>=', nums), ('<', upper)]
    if op == '~':
        return [('>=', nums), ('<', _bump_penultimate(val))]
    if op == '':
        if len(segs) < 3:
            return [('>=', nums), ('<', _bump_partial(val))]
        return [('==', nums)]
    if op == '=':
        return [('==', nums)]
    return [(op, nums)]


JS_HYPHEN_RANGE_RE = re.compile(r'^(.+?)\s+-\s+(.+)$')


def parse_js_spec(spec):
    """解析 NodeJS 版本约束为 [[(op, key), ...], ...]；无法解析返回 None"""
    s = str(spec).strip()
    if not s:
        return [[]]
    branches = []
    for part in s.split('||'):
        part = part.strip()
        if not part:
            branches.append([])
            continue
        m = JS_HYPHEN_RANGE_RE.match(part)
        if m:  # 连字符区间 a - b
            hi = m.group(2).strip()
            hi_atom = (('<', _bump_partial(hi)) if len(hi.split('.')) < 3
                       else ('<=', js_ver_key(hi)))
            branches.append([('>=', js_ver_key(m.group(1))), hi_atom])
            continue
        atoms = []
        for tok in part.split():
            parsed = _parse_js_token(tok)
            if parsed is None:
                return None
            atoms.extend(parsed)
        branches.append(atoms)
    return branches


def _atom_ok(vkey, op, k):
    if op == '==':
        return vkey == k
    if op == '>=':
        return vkey >= k
    if op == '<=':
        return vkey <= k
    if op == '>':
        return vkey > k
    if op == '<':
        return vkey < k
    return True


def _better_upper(cand, cur):
    """上界 (key, inclusive) 取更宽松者"""
    if cur is None:
        return cand
    if cand[0] > cur[0] or (cand[0] == cur[0] and cand[1] and not cur[1]):
        return cand
    return cur


def _branch_upper(atoms):
    """分支上界 (key, inclusive)；无上界返回 None"""
    upper = None
    for op, k in atoms:
        if op in ('==', '<='):
            upper = _better_upper((k, True), upper)
        elif op == '<':
            upper = _better_upper((k, False), upper)
    return upper


def check_version_key(vkey, wl_parsed, upper_keys_exclusive=None):
    """
    版本 key 对白名单约束集的判定（单次遍历）。
    返回 ('ok'|'greater'|'out', upper)。
    """
    upper = None
    has_unbounded = False
    for branches in wl_parsed:
        if all(_atom_ok(vkey, op, k) for op, k in branches):
            return 'ok', None
        b = _branch_upper(branches)
        if b is None:
            has_unbounded = True
        else:
            upper = _better_upper(b, upper)
    if has_unbounded:
        # 存在无上界分支却仍未满足 -> 范围外（如低于下限）
        return 'out', None
    if upper is not None and (vkey > upper[0]
                              or (vkey == upper[0] and not upper[1])):
        # 开发者约束的排他上界与白名单排他上界相同（如 ^3.5.34 vs ^3.5.32）
        if (upper_keys_exclusive and vkey in upper_keys_exclusive
                and vkey == upper[0] and not upper[1]):
            return 'ok', upper
        return 'greater', upper
    return 'out', upper


def spec_has_unbounded_branch(branches_list):
    for branches in branches_list:
        if _branch_upper(branches) is None:
            return True
    return False


# ---------------- 生态配置与公共判定 ----------------

# 生态相关配置统一在此分发，避免散落的 if/else
ECO_CONF = {
    'py': {'label': 'Python', 'attr': 'opensource_py',
           'dep_file': 'requirements.txt',
           'parse': parse_py_spec, 'keyfn': py_ver_key},
    'js': {'label': 'NodeJS', 'attr': 'opensource_js',
           'dep_file': 'package.json',
           'parse': parse_js_spec, 'keyfn': js_ver_key},
}


def parse_specs(specs, ecosystem):
    """多 spec（' || ' 并集）解析为扁平分支列表，忽略无法解析项"""
    parse = ECO_CONF[ecosystem]['parse']
    out = []
    for s in specs or []:
        try:
            b = parse(s)
        except Exception:
            b = None
        if b is not None:
            out.extend(b)
    return out


# ---------------- 依赖组件识别 ----------------


def normalize_py_name(name):
    return re.sub(r'[-_.]+', '-', str(name).strip().lower())


def parse_py_req_line(line):
    """解析 requirements 新增行 -> (name, spec) 或 None"""
    t = line.strip()
    if not t or t.startswith('#') or t.startswith('-'):
        return None
    t = re.sub(r'\s+#.*$', '', t).strip()
    if not t:
        return None
    t = t.split(';', 1)[0].strip()
    m = re.match(r'^([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[[^\]]*\])?\s*(.*)$', t)
    if not m:
        return None
    name = m.group(1)
    spec = re.sub(r'\s*([<>=!~,;@])\s*', r'\1', m.group(2).strip())
    return name, (spec or '*')


def parse_js_dep_line(line, section):
    """解析 package.json 新增行 -> (name, spec) 或 None"""
    m = re.search(r'"([^"]+)"\s*:\s*"([^"]*)"', line)
    if not m:
        return None
    key, val = m.group(1).strip(), m.group(2).strip()
    if not key or key.startswith('//'):
        return None
    if section is not None:
        if section not in JS_SECTION_KEYS:
            return None
    elif key in JS_BLOCKED_KEYS:
        return None
    if not JS_SPEC_SHAPE.match(val):
        return None
    return key, val


ARTIFACT_EXTS = ('.whl', '.tar.gz', '.tgz', '.zip')
ARTIFACT_SEG_RE = re.compile(
    r'^([A-Za-z0-9][A-Za-z0-9_.@+-]*?)-'
    r'(\d+(?:\.\d+)+(?:\.(?:post|dev|rc)\d+)*(?:\+[\w.]+)?)'
    r'(?:[-.].*)?$')

PYPI_PROJECT_RE = re.compile(
    r'^https?://pypi\.org/project/([A-Za-z0-9._-]+)'
    r'(?:/([0-9][A-Za-z0-9.+*-]*))?', re.IGNORECASE)
NPM_SCOPED_RE = re.compile(
    r'^https?://registry\.npmjs\.org/(@[^/]+)/([^/]+)/-/'
    r'[^/]+-([0-9][\w.+-]*)\.(?:tgz|tar\.gz)$')
NPM_PLAIN_RE = re.compile(
    r'^https?://registry\.npmjs\.org/([^/@][^/]*)/-/'
    r'[^/]+-([0-9][\w.+-]*)\.(?:tgz|tar\.gz)$')


def _artifact_from_last_segment(seg):
    for ext in ARTIFACT_EXTS:
        if seg.endswith(ext):
            seg = seg[:-len(ext)]
            break
    else:
        return None
    m = ARTIFACT_SEG_RE.match(seg)
    if not m:
        return None
    return m.group(1), m.group(2)


def extract_dep_from_url(url):
    """
    识别 Python/NodeJS 依赖组件 URL。
    返回 (name, version|None)；非依赖组件 URL 返回 None。
    """
    u = url.split('#', 1)[0].split('?', 1)[0]
    try:
        u = unquote(u)
    except Exception:
        pass
    m = PYPI_PROJECT_RE.match(u)
    if m:
        return m.group(1), m.group(2)
    m = NPM_SCOPED_RE.match(u)
    if m:
        return '{}/{}'.format(m.group(1), m.group(2)), m.group(3)
    m = NPM_PLAIN_RE.match(u)
    if m:
        return m.group(1), m.group(2)
    # 通用制品：取 URL 最后一段解析 <name>-<version>.<ext>
    return _artifact_from_last_segment(u.rstrip('/').split('/')[-1])


def version_from_url_spec(spec):
    """从 '@https://...' / 'git+https://...' 直引约束中提取制品版本"""
    m = re.search(r'https?://[^\s;]+', spec)
    if not m:
        return None
    dep = extract_dep_from_url(m.group(0))
    if dep and dep[1]:
        return dep[1]
    return None


def is_url_spec(spec):
    """是否为 URL 直引约束"""
    return spec.startswith('@') or '://' in spec or spec.startswith('git+')


# ---------------- 日志 ----------------


def log_info(msg):
    print("[INFO] check_oss_dep: {}".format(msg))


def log_warning(msg):
    print("[WARNING] check_oss_dep: {}".format(msg))


def log_error(msg):
    print("[ERROR] check_oss_dep: {}".format(msg))


# ---------------- patch 获取与解析 ----------------


def load_patch(workspace, target_branch):
    """获取开发者提交的代码 patch（unified diff 全量文本）"""
    patch_file = os.path.join(workspace, "update_file_detail.txt")
    if os.path.isfile(patch_file):
        log_info("读取代码 patch: {}".format(patch_file))
        with open(patch_file, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    log_warning("代码 patch 文件不存在: {}，尝试通过 git diff 生成".format(patch_file))
    ref = "origin/{}".format(target_branch)
    try:
        check = subprocess.run(
            ["git", "-C", workspace, "rev-parse", "--verify", "--quiet", ref],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60,
        )
        if check.returncode != 0:
            log_warning("代码仓内不存在引用 {}".format(ref))
            return None
        result = subprocess.run(
            ["git", "-C", workspace, "diff", "-U0", "-w", "--no-renames",
             "{}...HEAD".format(ref)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300,
        )
        return result.stdout.decode("utf-8", errors="replace")
    except Exception as e:
        log_warning("git diff 生成代码 patch 失败: {}".format(e))
        return None


def parse_added_lines(diff_text):
    """解析 unified diff，返回 [(文件路径, 新增行内容), ...]"""
    added = []
    current_file = ""
    for line in diff_text.splitlines():
        if line.startswith("+++"):
            path = line[4:]
            if path.startswith("b/"):
                path = path[2:]
            current_file = path
        elif line.startswith("+"):
            added.append((current_file, line[1:]))
    return added


def clean_url(url):
    """去除 URL 末尾粘连的标点"""
    return url.rstrip(TRAILING_PUNCTUATION)


def url_candidates(url):
    """生成待匹配的 URL 候选（原始串 / 去尾标点 / 全角截断）"""
    candidates = []
    for cand in (url, clean_url(url)):
        if cand and cand not in candidates:
            candidates.append(cand)
    for idx, char in enumerate(url):
        if char in FULLWIDTH_CUT_CHARS:
            cut = clean_url(url[:idx])
            if cut and cut not in candidates:
                candidates.append(cut)
            break
    return candidates


def url_in_whitelist(url, wl_entries, wl_exact):
    """URL 完全匹配（O(1) 集合）或带边界字符的前缀匹配"""
    u = url.lower()
    if u in wl_exact:
        return True
    for entry in wl_entries:
        if u.startswith(entry) and u[len(entry):len(entry) + 1] \
                in PREFIX_BOUNDARY_CHARS:
            return True
    return False


def normalize_third_party(entry):
    """归一化 opensource_c 条目为三方库名称"""
    entry = entry.strip()
    m = THIRD_PARTY_PATTERN.search(entry)
    if m:
        return m.group(1).lower()
    return entry.lower()


# ---------------- 白名单加载 ----------------


def load_py_whitelist(py_conf):
    """opensource_py -> {归一化包名: [spec, ...]}"""
    wl = {}
    if isinstance(py_conf, dict):
        for name, spec in py_conf.items():
            if isinstance(spec, str):
                wl.setdefault(normalize_py_name(name), []).append(spec)
    return wl


def load_js_whitelist(js_conf):
    """opensource_js（含 dependencies/devDependencies/overrides/lock 等）->
    {包名: [spec, ...]}"""
    wl = {}

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(v, str):
                    wl.setdefault(str(k), []).append(v)
                elif isinstance(v, dict):
                    walk(v)

    walk(js_conf if isinstance(js_conf, dict) else {})
    return wl


def js_lookup(table, name):
    """js 表（大小写不敏感）查找 -> specs 或 None"""
    if name in table:
        return table[name]
    if name.lower() in table:
        return table[name.lower()]
    return None


def resolve_dep_ecosystem(dep_name, py_wl, js_wl):
    """依赖组件名 -> (ecosystem, 白名单 specs)；未知组件返回 (None, None)"""
    py_key = normalize_py_name(dep_name)
    if py_key in py_wl:
        return 'py', py_wl[py_key]
    specs = js_lookup(js_wl, dep_name)
    if specs is not None:
        return 'js', specs
    return None, None


# ---------------- 主流程 ----------------


def collect_changes(added_lines):
    """从新增行提取 URL / C 三方库 / py 依赖 / js 依赖 / 依赖文件同步声明"""
    new_urls = {}
    new_third_party = {}
    new_py_deps = {}
    new_js_deps = {}
    py_sync = {}
    js_sync = {}
    js_section = {}
    for file_path, line in added_lines:
        if not file_path:
            continue
        norm_path = file_path.replace('\\', '/')
        base_name = norm_path.rsplit('/', 1)[-1].lower()
        is_py_file = PY_REQ_FILE_RE.search(norm_path) is not None
        is_js_file = JS_FILE_RE.search(norm_path) is not None
        # 行级 fast-skip：非依赖文件仅处理含特征标记（http/三方库/pip）的行
        low = line.lower()
        if not (is_py_file or is_js_file or 'http' in low
                or 'add_cann_third_party' in low or 'pip' in low):
            continue
        if 'http' in low:
            for url in URL_PATTERN.findall(line):
                if url:
                    new_urls.setdefault(url, set()).add(file_path)
        if 'add_cann_third_party' in low:
            for name in THIRD_PARTY_PATTERN.findall(line):
                new_third_party.setdefault(name.lower(), set()).add(file_path)
        if is_py_file:
            dep = parse_py_req_line(line)
            if dep:
                new_py_deps.setdefault(dep, set()).add(file_path)
                if base_name == 'requirements.txt':
                    py_sync.setdefault(normalize_py_name(dep[0]), []).append(dep[1])
        if is_js_file:
            m = JS_SECTION_LINE_RE.search(line)
            if m:
                js_section[file_path] = m.group(1)
            else:
                dep = parse_js_dep_line(line, js_section.get(file_path))
                if dep:
                    new_js_deps.setdefault(dep, set()).add(file_path)
                    if base_name == 'package.json':
                        js_sync.setdefault(dep[0], []).append(dep[1])
        # 脚本等任意文件中的 pip install <name><op><ver> 引入（非登记）
        if 'pip' in low and not line.strip().startswith('#'):
            for pm in PIP_INSTALL_RE.finditer(line):
                dep = (pm.group(1), pm.group(2) + pm.group(3))
                new_py_deps.setdefault(dep, set()).add(file_path)
    return new_urls, new_third_party, new_py_deps, new_js_deps, py_sync, js_sync


def describe_files(files):
    return ", ".join(sorted(files))


def sync_covers(ecosystem, vkey, sync_specs):
    """
    判断 PR 依赖文件（requirements.txt / package.json）中是否已同步声明
    覆盖 vkey 的版本约束（版本同步更新完成的判定）。
    """
    if not sync_specs:
        return False
    conf = ECO_CONF[ecosystem]
    for s in sync_specs:
        s = str(s).strip()
        if is_url_spec(s):
            ver = version_from_url_spec(s)
            if ver is None:
                return True  # 声明为URL且无法解析版本，按已登记放行
            if vkey == conf['keyfn'](ver):
                return True
            continue
        try:
            branches = conf['parse'](s)
        except Exception:
            branches = None
        if branches is None:
            return True  # 声明无法解析，按已登记放行
        for b in branches:
            if all(_atom_ok(vkey, op, k) for op, k in b):
                return True
    return False


def check_dep_version(ecosystem, name, spec, wl_specs, files, sync_specs=None):
    """
    检查依赖声明（requirements.txt / package.json / 脚本 pip install 新增行）
    的版本合规性。版本超出白名单时，若 PR 依赖文件已同步声明该版本则放行。
    返回 True 放行 / False 拦截。
    """
    conf = ECO_CONF[ecosystem]
    eco_label, attr, dep_file = conf['label'], conf['attr'], conf['dep_file']
    sync_specs = sync_specs or []
    if is_url_spec(spec):
        ver = version_from_url_spec(spec)
        if ver is None:
            log_info("新增{}依赖组件 {} 以URL方式引入且组件在{}白名单内，放行 ({})"
                     .format(eco_label, name, attr, describe_files(files)))
            return True
        vkey = conf['keyfn'](ver)
        dev_excl = None
    else:
        try:
            branches = conf['parse'](spec)
        except Exception:
            branches = None
        if branches is None:
            log_warning("依赖 {} 的版本约束 '{}' 无法解析，按组件白名单放行 ({})"
                        .format(name, spec, describe_files(files)))
            return True
        eq_keys = [k for b in branches for op, k in b if op == '==']
        upper_vals = [u for u in (_branch_upper(b) for b in branches) if u]
        if eq_keys or upper_vals:
            # 开发者声明了确定/上界版本：以其上界参与白名单比较
            vkey = max(eq_keys + [k for k, _ in upper_vals])
            dev_excl = set(k for k, incl in upper_vals if not incl)
        else:
            # 开发者约束无上界（如 >=x / *）
            wl_parsed = parse_specs(wl_specs, ecosystem)
            if wl_parsed and spec_has_unbounded_branch(wl_parsed):
                log_info("新增{}依赖组件 {} 版本约束 '{}' 在{}宽范围版本内，放行 ({})"
                         .format(eco_label, name, spec, attr,
                                 describe_files(files)))
                return True
            if sync_specs:
                log_info("新增{}依赖组件 {} 版本约束 '{}' 超出{}允许版本 {}，"
                         "但PR已在依赖文件 {} 同步更新版本号，放行 ({})"
                         .format(eco_label, name, spec, attr,
                                 ' || '.join(wl_specs), dep_file,
                                 describe_files(files)))
                return True
            log_error("引入的{}依赖组件 {} 版本约束 '{}' 无上界，超出{}允许版本 {}，"
                      "拦截：需要在相应依赖文件 {} 同步更新版本号 (文件: {})"
                      .format(eco_label, name, spec, attr,
                              ' || '.join(wl_specs), dep_file,
                              describe_files(files)))
            return False
    wl_parsed = parse_specs(wl_specs, ecosystem)
    if not wl_parsed:
        log_warning("依赖 {} 的白名单版本约束无法解析，按组件白名单放行 ({})"
                    .format(name, describe_files(files)))
        return True
    status, _upper = check_version_key(vkey, wl_parsed, dev_excl)
    if status == 'ok':
        log_info("新增{}依赖组件 {}@'{}' 在{}白名单版本范围内，放行 ({})"
                 .format(eco_label, name, spec, attr, describe_files(files)))
        return True
    if sync_covers(ecosystem, vkey, sync_specs):
        log_info("新增{}依赖组件 {}@'{}' 版本超出{}白名单允许版本 {}，"
                 "但PR已在依赖文件 {} 同步更新版本号，放行 ({})"
                 .format(eco_label, name, spec, attr,
                         ' || '.join(wl_specs), dep_file,
                         describe_files(files)))
        return True
    if status == 'greater':
        log_error("引入的{}依赖组件 {} 版本号('{}') 大于{}白名单允许版本 {}，"
                  "拦截：需要在相应依赖文件 {} 同步更新版本号 (文件: {})"
                  .format(eco_label, name, spec, attr,
                          ' || '.join(wl_specs), dep_file,
                          describe_files(files)))
        return False
    log_error("引入的{}依赖组件 {} 版本('{}') 不在{}白名单版本约束 {} 范围内 (文件: {})"
              .format(eco_label, name, spec, attr, ' || '.join(wl_specs),
                      describe_files(files)))
    return False


def check_url_entry(url, files, url_wl, url_exact, py_wl, js_wl, py_sync, js_sync):
    """
    单个新增 URL 的门禁判定（url 白名单 + py/js 组件宽范围版本放行 +
    依赖文件同步声明豁免）。返回 True 放行 / False 拦截。
    """
    candidates = url_candidates(url)
    if any(url_in_whitelist(c, url_wl, url_exact) for c in candidates):
        log_info("新增 URL 在白名单内: {} ({})"
                 .format(clean_url(url), describe_files(files)))
        return True
    dep = extract_dep_from_url(clean_url(url))
    if not dep:
        log_error("引入的URL 不在白名单列表内: {} (文件: {})"
                  .format(clean_url(url), describe_files(files)))
        return False
    dep_name, dep_ver = dep
    eco, specs = resolve_dep_ecosystem(dep_name, py_wl, js_wl)
    if eco is None:
        log_error("引入的URL 不在url白名单列表内，且识别为依赖组件 "
                  "{}@{} 不在opensource_py/opensource_js白名单内: "
                  "{} (文件: {})"
                  .format(dep_name, dep_ver or '-', clean_url(url),
                          describe_files(files)))
        return False
    conf = ECO_CONF[eco]
    attr, dep_file = conf['attr'], conf['dep_file']
    eco_label = conf['label']
    if dep_ver is None:
        log_info("新增 URL 不在url白名单内，但依赖组件 {} 在{}白名单内，"
                 "按组件白名单放行: {} ({})"
                 .format(dep_name, attr, clean_url(url), describe_files(files)))
        return True
    vkey = conf['keyfn'](dep_ver)
    wl_parsed = parse_specs(specs, eco)
    if not wl_parsed:
        log_warning("依赖组件 {} 白名单版本约束无法解析，按组件白名单放行: {} ({})"
                    .format(dep_name, clean_url(url), describe_files(files)))
        return True
    status, _upper = check_version_key(vkey, wl_parsed)
    if status == 'ok':
        log_info("新增 URL 不在url白名单内，但依赖组件 {} 版本 {} 仍在{}"
                 "允许范围 {} 内，准许合入: {} ({})"
                 .format(dep_name, dep_ver, attr, ' || '.join(specs),
                         clean_url(url), describe_files(files)))
        return True
    if eco == 'py':
        sync_specs = py_sync.get(normalize_py_name(dep_name))
    else:
        sync_specs = js_lookup(js_sync, dep_name)
    if sync_covers(eco, vkey, sync_specs):
        log_info("新增 URL 引入的{}依赖组件 {} 版本({}) 超出{}白名单允许版本 {}，"
                 "但PR已在依赖文件 {} 同步更新版本号，准许合入: {} ({})"
                 .format(eco_label, dep_name, dep_ver, attr,
                         ' || '.join(specs), dep_file,
                         clean_url(url), describe_files(files)))
        return True
    if status == 'greater':
        log_error("新增 URL 引入的{}依赖组件 {} 版本号({}) 大于{}白名单允许版本 {}，"
                  "拦截：需要在相应依赖文件 {} 同步更新版本号: {} (文件: {})"
                  .format(eco_label, dep_name, dep_ver, attr,
                          ' || '.join(specs), dep_file,
                          clean_url(url), describe_files(files)))
    else:
        log_error("新增 URL 引入的{}依赖组件 {} 版本({}) 不在{}白名单版本约束 {} "
                  "范围内: {} (文件: {})"
                  .format(eco_label, dep_name, dep_ver, attr,
                          ' || '.join(specs), clean_url(url),
                          describe_files(files)))
    return False


def main():
    if len(sys.argv) < 4:
        log_error("参数不足，用法: python3 check_oss_dep.py "
                  "<WORKSPACE> <REPOSITORY_NAME> <GIT_TARGET_BRANCH>")
        return 1

    workspace = sys.argv[1]
    repo_name = sys.argv[2]
    target_branch = sys.argv[3] or "master"

    # 1. 获取开发者提交的代码 patch
    diff_text = load_patch(workspace, target_branch)
    if diff_text is None:
        log_warning("无法获取代码 patch，跳过 URL/三方库门禁检查，门禁通过")
        return 0

    added_lines = parse_added_lines(diff_text)
    new_urls, new_third_party, new_py_deps, new_js_deps, py_sync, js_sync = \
        collect_changes(added_lines)

    log_info("PR 新增内容中检测到 URL {} 个，C三方库引用 {} 个，"
             "Python依赖声明 {} 个，NodeJS依赖声明 {} 个".format(
                 len(new_urls), len(new_third_party),
                 len(new_py_deps), len(new_js_deps)))

    if not new_urls and not new_third_party and not new_py_deps \
            and not new_js_deps:
        log_info("开发者修改代码不包含URL/三方库/依赖组件，门禁通过")
        return 0

    # 2. 读取门禁文件 oss_dep_security_gate_<branch>.json
    if not BRANCH_NAME_PATTERN.match(target_branch):
        log_warning("分支名 {} 不含可用门禁文件，门禁通过".format(target_branch))
        return 0
    gate_file = os.path.join(
        THIS_FILE_PATH, "{}{}.json".format(GATE_FILE_PREFIX, target_branch))
    if not os.path.isfile(gate_file):
        log_warning("门禁文件 {}{}.json 不存在，分支 {} 不作检查管控，门禁通过"
                    .format(GATE_FILE_PREFIX, target_branch, target_branch))
        return 0

    try:
        with open(gate_file, "r", encoding="utf-8-sig") as f:
            gate = json.load(f)
    except Exception as e:
        log_warning("门禁文件解析失败: {}，门禁通过".format(e))
        return 0

    # 3. 以代码仓为 key 查询，不在门禁文件内则不管控
    repo_conf = gate.get(repo_name)
    if not isinstance(repo_conf, dict):
        log_info("代码仓 {} 不在门禁文件管控列表内，门禁通过".format(repo_name))
        return 0

    url_entries = repo_conf.get("url") or []
    c_entries = repo_conf.get("opensource_c") or []
    py_conf = repo_conf.get("opensource_py") or {}
    js_conf = repo_conf.get("opensource_js") or {}
    if not isinstance(url_entries, list) or not isinstance(c_entries, list):
        log_warning("代码仓 {} 门禁属性格式异常，门禁通过".format(repo_name))
        return 0
    # 白名单条目归一化一次 + 精确匹配集合（O(1) 命中）
    url_wl = [str(u).strip().lower() for u in url_entries if str(u).strip()]
    url_exact = set(url_wl)
    for entry in url_wl:
        if entry.endswith('/'):
            url_exact.add(entry.rstrip('/'))
    c_whitelist = set(normalize_third_party(t) for t in c_entries)
    py_wl = load_py_whitelist(py_conf)
    js_wl = load_js_whitelist(js_conf)
    log_info("代码仓 {} 受控，url 白名单 {} 条，opensource_c {} 条，"
             "opensource_py {} 项，opensource_js {} 项".format(
                 repo_name, len(url_wl), len(c_whitelist),
                 len(py_wl), len(js_wl)))

    blocked = False

    # 4. C 三方库引用检查（opensource_c）
    for name in sorted(new_third_party):
        files = new_third_party[name]
        if name in c_whitelist:
            log_info("新增三方库在白名单内: add_cann_third_party({}) ({})"
                     .format(name, describe_files(files)))
        else:
            blocked = True
            log_error("引入的三方库 不在opensource_c白名单列表内: "
                      "add_cann_third_party({}) (文件: {})"
                      .format(name, describe_files(files)))

    # 5. Python 依赖声明检查（opensource_py）
    for (name, spec) in sorted(new_py_deps):
        files = new_py_deps[(name, spec)]
        key = normalize_py_name(name)
        if key not in py_wl:
            blocked = True
            log_error("引入的Python依赖组件 {} 不在opensource_py白名单列表内 "
                      "(文件: {})".format(name, describe_files(files)))
        elif not check_dep_version('py', name, spec, py_wl[key], files,
                                   py_sync.get(key)):
            blocked = True

    # 6. NodeJS 依赖声明检查（opensource_js）
    for (name, spec) in sorted(new_js_deps):
        files = new_js_deps[(name, spec)]
        specs = js_lookup(js_wl, name)
        if specs is None:
            blocked = True
            log_error("引入的NodeJS依赖组件 {} 不在opensource_js白名单列表内 "
                      "(文件: {})".format(name, describe_files(files)))
        elif not check_dep_version('js', name, spec, specs, files,
                                   js_lookup(js_sync, name)):
            blocked = True

    # 7. URL 检查（url 白名单 + opensource_py/js 宽范围版本放行）
    for url in sorted(new_urls):
        if not check_url_entry(url, new_urls[url], url_wl, url_exact,
                               py_wl, js_wl, py_sync, js_sync):
            blocked = True

    if blocked:
        log_error("门禁检查未通过：引入的URL/三方库/依赖组件不合规")
        return 1

    log_info("URL/三方库/开源依赖门禁检查通过")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:
        # fail-closed：脚本内部异常按拦截处理，避免异常路径成为绕过面
        log_error("门禁脚本内部异常（按拦截处理）: {}".format(exc))
        sys.exit(1)
