# -*- coding: utf-8 -*-
"""
CANN PR 门禁检测：URL 链接 & 三方库引用白名单检查。

检测逻辑：
1. 获取开发者提交的代码 patch（优先读取 get-pr 产出的 update_file_detail.txt，
   即 git diff -U0 -w --no-renames origin/<target_branch>...HEAD 的输出；
   文件不存在时尝试在代码仓内重新生成），提取新增行中的：
   - URL 链接（http/https）
   - 三方库引用（add_cann_third_party(xxx)）
   若均未涉及，门禁直接通过。
2. 涉及 URL 或三方库引用时，读取目标分支对应的白名单文件
   pipline_ctrl_<branch>.json（如 master 分支为 pipline_ctrl_master.json）：
   - 代码仓不在白名单文件中：此代码仓不作检查管控，门禁通过；
   - 代码仓在白名单文件中：
     (1) 开发者新增的 URL 必须在 URL 属性内；
     (2) 开发者新增的三方库引用必须在 Third_party 属性内；
     全部通过则门禁通过，否则门禁拦截，打印
     "引入的URL/三方库 不在白名单列表内" 并以非 0 退出。

用法：
    python3 check_url_third_party.py <WORKSPACE> <REPOSITORY_NAME> <GIT_TARGET_BRANCH>

退出码：0 门禁通过；1 门禁拦截
"""

import json
import os
import re
import subprocess
import sys

THIS_FILE_PATH = os.path.dirname(os.path.realpath(__file__))

URL_PATTERN = re.compile(r'https?://[^\s"\'<>\)\\]+', re.IGNORECASE)

THIRD_PARTY_PATTERN = re.compile(
    r'add_cann_third_party\s*\(\s*["\']?([A-Za-z0-9_\-\.]+)["\']?\s*\)',
    re.IGNORECASE,
)

BRANCH_NAME_PATTERN = re.compile(r'^[A-Za-z0-9._\-]+$')

# URL 末尾可能粘连的标点（ASCII 标点、markdown 反引号、全角/中文标点等）
TRAILING_PUNCTUATION = '.,;:!?)]}>\'"`」〉》】〕』”’），；。？！、'

# 全角标点：中文语境下 URL 常与后续说明文字直接粘连（无空格），
# 如 "参考（https://xxx/anaconda）安装"，按此类字符截断生成候选
FULLWIDTH_CUT_CHARS = '，。；：？！、（）「」『』《》〈〉【】〔〕［］“”‘’'

# URL 前缀匹配时允许的边界字符，防止 https://gitcode.com 匹配
# https://gitcode.com.evil.com 这类旁路；} 用于兼容白名单中被截断的
# 占位符条目（如 https://xxx/${obs_path）
PREFIX_BOUNDARY_CHARS = ('/', '?', '#', '&', ';', '}')


def log_info(msg):
    print("[INFO] check_url_third_party: {}".format(msg))


def log_warning(msg):
    print("[WARNING] check_url_third_party: {}".format(msg))


def log_error(msg):
    print("[ERROR] check_url_third_party: {}".format(msg))


def load_patch(workspace, target_branch):
    """获取开发者提交的代码 patch（unified diff 全量文本）"""
    patch_file = os.path.join(workspace, "update_file_detail.txt")
    if os.path.isfile(patch_file):
        log_info("读取代码 patch: {}".format(patch_file))
        with open(patch_file, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    # 兜底：update_file_detail.txt 不存在时，尝试在代码仓内重新生成 diff
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
    """
    生成待匹配的 URL 候选列表：
    - 原始串（白名单中存在含粘连标点的原始条目）
    - 去除末尾标点后的串
    - 按第一个全角标点截断后的串（处理中文语境下 URL 与说明文字粘连的场景）
    """
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


def url_in_whitelist(url, url_whitelist):
    """
    判断新增 URL 是否在白名单内。
    匹配规则：完全相等（含末尾斜杠等价），或白名单条目是新增 URL 的前缀
    且带边界字符（白名单中存在裸域名条目和被 { 截断的占位符条目，
    需按前缀放行）。
    """
    url_lower = url.lower()
    for entry in url_whitelist:
        entry = entry.strip().lower()
        if not entry:
            continue
        if url_lower == entry or url_lower == entry.rstrip("/"):
            return True
        if url_lower.startswith(entry) and url_lower[len(entry):len(entry) + 1] \
                in PREFIX_BOUNDARY_CHARS:
            return True
    return False


def normalize_third_party(entry):
    """
    归一化三方库白名单条目。
    兼容两种格式：完整调用 add_cann_third_party(boost) 与裸名称 boost，
    统一提取三方库名称。
    """
    entry = entry.strip()
    match = THIRD_PARTY_PATTERN.search(entry)
    if match:
        return match.group(1).lower()
    return entry.lower()


def main():
    if len(sys.argv) < 4:
        log_error("参数不足，用法: python3 check_url_third_party.py "
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

    new_urls = {}
    new_third_party = {}
    for file_path, line in added_lines:
        for url in URL_PATTERN.findall(line):
            if url:
                new_urls.setdefault(url, set()).add(file_path)
        for name in THIRD_PARTY_PATTERN.findall(line):
            new_third_party.setdefault(name.lower(), set()).add(file_path)

    log_info("PR 新增内容中检测到 URL {} 个，三方库引用 {} 个".format(
        len(new_urls), len(new_third_party)))

    # 2. 不包含 URL 或三方库，门禁通过
    if not new_urls and not new_third_party:
        log_info("开发者修改代码不包含URL或三方库，门禁通过")
        return 0

    # 3. 根据分支读取白名单文件 pipline_ctrl_xxxx.json
    if not BRANCH_NAME_PATTERN.match(target_branch):
        log_warning("分支名 {} 不含可用白名单文件，门禁通过".format(target_branch))
        return 0
    whitelist_file = os.path.join(
        THIS_FILE_PATH, "pipline_ctrl_{}.json".format(target_branch))
    if not os.path.isfile(whitelist_file):
        log_warning("白名单文件 pipline_ctrl_{}.json 不存在，分支 {} 不作检查管控，"
                    "门禁通过".format(target_branch, target_branch))
        return 0

    try:
        with open(whitelist_file, "r", encoding="utf-8-sig") as f:
            whitelist = json.load(f)
    except Exception as e:
        log_warning("白名单文件解析失败: {}，门禁通过".format(e))
        return 0

    # 4. 以代码仓为 key 查询，不在白名单文件内则不管控
    repo_conf = whitelist.get(repo_name)
    if not isinstance(repo_conf, dict):
        log_info("代码仓 {} 不在白名单文件管控列表内，门禁通过".format(repo_name))
        return 0

    url_entries = repo_conf.get("URL") or []
    third_party_entries = repo_conf.get("Third_party") or []
    if not isinstance(url_entries, list) or not isinstance(third_party_entries, list):
        log_warning("代码仓 {} 白名单属性格式异常，门禁通过".format(repo_name))
        return 0
    url_whitelist = [str(u) for u in url_entries]
    third_party_whitelist = set(
        normalize_third_party(t) for t in third_party_entries)
    log_info("代码仓 {} 受控，URL 白名单 {} 条，三方库白名单 {} 条".format(
        repo_name, len(url_whitelist), len(third_party_whitelist)))

    # 5. 检查新增 URL / 三方库是否在白名单属性内
    blocked = False
    for url in sorted(new_urls):
        files = ", ".join(sorted(new_urls[url]))
        candidates = url_candidates(url)
        if any(url_in_whitelist(c, url_whitelist) for c in candidates):
            log_info("新增 URL 在白名单内: {} ({})".format(clean_url(url), files))
        else:
            blocked = True
            log_error("引入的URL 不在白名单列表内: {} (文件: {})".format(
                clean_url(url), files))

    for name in sorted(new_third_party):
        files = ", ".join(sorted(new_third_party[name]))
        if name in third_party_whitelist:
            log_info("新增三方库在白名单内: add_cann_third_party({}) ({})".format(
                name, files))
        else:
            blocked = True
            log_error("引入的三方库 不在白名单列表内: add_cann_third_party({}) "
                      "(文件: {})".format(name, files))

    if blocked:
        log_error("门禁检查未通过：引入的URL/三方库 不在白名单列表内")
        return 1

    log_info("URL/三方库门禁检查通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
