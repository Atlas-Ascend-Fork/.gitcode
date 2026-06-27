#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sys
import csv
import argparse
from pathlib import Path
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ========== 工具函数 ==========
def create_session():
    session = requests.Session()
    retry_strategy = Retry(
        total=2,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=20, pool_maxsize=20)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({
        "User-Agent": "Markdown-Link-Checker/1.0"
    })
    return session

# 提取所有链接：普通链接 + 图片 + 锚点 + 邮箱
def extract_links_from_md(file_path: Path, content: str):
    links = []

    # 1. 普通链接和图片: [text](url) 和 ![alt](url)
    inline_pattern = r'(!?)\[(.*?)\]\((.*?)\)'
    for match in re.finditer(inline_pattern, content):
        is_image = bool(match.group(1))
        url = match.group(3).strip()
        if url:
            link_type = 'image' if is_image else 'link'
            links.append((url, link_type))

    # 2. 自动链接 <url>
    autolink_pattern = r'<(https?://[^>\s]+)>'
    for match in re.finditer(autolink_pattern, content):
        links.append((match.group(1).strip(), 'link'))

    # 3. 邮箱自动链接 <email@example.com>
    email_autolink = r'<([^>\s]+@[^>\s]+\.[^>\s]+)>'
    for match in re.finditer(email_autolink, content):
        links.append((f"mailto:{match.group(1)}", 'email'))

    return links

# 生成锚点 ID（模拟 GitHub/GitLab 行为）
def generate_anchor_id(header_text: str) -> str:
    # 移除前导/尾随空格
    s = header_text.strip()
    # 转小写
    s = s.lower()
    # 移除标点（保留连字符、下划线、字母数字）
    s = re.sub(r'[^\w\-_ ]', '', s)
    # 空格转连字符
    s = re.sub(r' +', '-', s)
    return s

# 解析 Markdown 文件中的所有标题（用于锚点检查）
def extract_headers_from_md(content: str):
    headers = set()
    # 匹配 # Header, ## Header, 或者 Header\n=== 形式
    atx_pattern = r'^(#{1,6})\s+(.*)$'
    setext_pattern = r'^(.+)\n([=-])\2{2,}$'

    for line in content.splitlines():
        # ATX 样式 (# Header)
        atx_match = re.match(atx_pattern, line)
        if atx_match:
            header_text = atx_match.group(2)
            anchor = generate_anchor_id(header_text)
            headers.add(anchor)
        # Setext 样式 (Header\n===)
        # （简单处理：只检查下一行是否为 === 或 ---）

    # 处理 Setext 样式（多行）
    lines = content.splitlines()
    for i in range(len(lines) - 1):
        current = lines[i].strip()
        next_line = lines[i + 1].strip()
        if current and (next_line == '=' * len(next_line) or next_line == '-' * len(next_line)):
            if len(next_line) >= 3:
                anchor = generate_anchor_id(current)
                headers.add(anchor)

    return headers

# 分类链接
def classify_link(url):
    if url.startswith('mailto:'):
        return 'email', url[7:]  # 返回纯邮箱
    if url.startswith('tel:'):
        return 'skip', 'tel'
    if url.startswith('#'):
        return 'anchor', url[1:]  # 返回锚点ID
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme in ('http', 'https'):
        return 'http', url
    if not scheme:
        return 'relative', url
    return 'skip', f'unsupported: {scheme}'

# 检查邮箱格式
def check_email(email: str):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if re.match(pattern, email):
        return "OK", None
    else:
        return "FAILED", "Invalid email format"

# 检查锚点（需传入当前文件内容）
def check_anchor(anchor_id: str, headers_in_file: set):
    if anchor_id in headers_in_file:
        return "OK", None
    else:
        return "FAILED", f"Anchor not found: #{anchor_id}"

# 检查相对路径（复用）
def check_relative_link(base_dir: Path, rel_url: str):
    try:
        if rel_url.startswith('/'):
            target_path = base_dir / rel_url[1:]
        else:
            target_path = (base_dir / rel_url).resolve()
        if target_path.exists():
            return "OK", None
        else:
            return "FAILED", f"File not found: {target_path}"
    except Exception as e:
        return "ERROR", str(e)

# 检查 HTTP（复用）
def check_http_link(session, url, timeout=10):
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if hostname in ('localhost', '127.0.0.1', '::1'):
            return "SKIPPED", "local address"
        response = session.get(url, timeout=timeout, allow_redirects=True)
        status = response.status_code
        if 200 <= status < 400:
            return "OK", status
        else:
            return "FAILED", status
    except Exception as e:
        return "ERROR", str(e)

# 扫描单个文件
def scan_file(file_path: Path):
    tasks = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 提取所有链接
        raw_links = extract_links_from_md(file_path, content)
        # 提取标题（用于锚点检查）
        headers = extract_headers_from_md(content)

        for url, link_category in raw_links:
            if link_category == 'link':
                link_type, normalized = classify_link(url)
                if link_type == 'skip':
                    continue
                tasks.append({
                    'file': str(file_path),
                    'link': url,
                    'type': link_type,
                    'category': 'link',
                    'base_dir': str(file_path.parent),
                    'headers': headers  # 仅锚点需要，但统一传
                })
            elif link_category == 'image':
                link_type, normalized = classify_link(url)
                if link_type == 'skip':
                    continue
                tasks.append({
                    'file': str(file_path),
                    'link': url,
                    'type': link_type,
                    'category': 'image',
                    'base_dir': str(file_path.parent)
                })
            elif link_category == 'email':
                tasks.append({
                    'file': str(file_path),
                    'link': url,
                    'type': 'email',
                    'category': 'email',
                    'base_dir': str(file_path.parent)
                })
    except Exception as e:
        print(f"⚠️ 无法读取文件 {file_path}: {e}", file=sys.stderr)
    return tasks

# 检查任务
def check_task(task, http_session):
    file_path = task['file']
    link = task['link']
    link_type = task['type']
    category = task['category']
    base_dir = Path(task['base_dir'])

    display_type = category.upper()  # LINK, IMAGE, EMAIL, ANCHOR

    if link_type == 'anchor':
        anchor_id = link
        headers = task.get('headers', set())
        status, detail = check_anchor(anchor_id, headers)
        return {
            "file": file_path,
            "url": f"#{anchor_id}",
            "type": "ANCHOR",
            "status": status,
            "detail": detail
        }
    elif link_type == 'email':
        email = link
        status, detail = check_email(email)
        return {
            "file": file_path,
            "url": f"mailto:{email}",
            "type": "EMAIL",
            "status": status,
            "detail": detail
        }
    elif link_type == 'http':
        status, detail = check_http_link(http_session, link)
        return {
            "file": file_path,
            "url": link,
            "type": "HTTP" if category == 'link' else "IMAGE_HTTP",
            "status": status,
            "detail": detail
        }
    elif link_type == 'relative':
        status, detail = check_relative_link(base_dir, link)
        return {
            "file": file_path,
            "url": link,
            "type": "RELATIVE" if category == 'link' else "IMAGE_RELATIVE",
            "status": status,
            "detail": detail
        }
    else:
        return {
            "file": file_path,
            "url": link,
            "type": "UNKNOWN",
            "status": "SKIPPED",
            "detail": "unknown"
        }

# ========== 主函数（保持不变，仅调整调用）==========
def main():
    parser = argparse.ArgumentParser(description="全面检查 Markdown 链接：HTTP、相对路径、锚点、图片、邮箱")
    parser.add_argument("paths", nargs='+', help="一个或多个 Markdown 文件或目录路径")
    parser.add_argument("-o", "--output", default="link_check_report.txt", help="报告输出文件")
    parser.add_argument("--csv", default="link_details.csv", help="详细结果 CSV 文件")
    parser.add_argument("-t", "--threads", type=int, default=10, help="并发线程数（仅用于 HTTP 链接）")
    parser.add_argument("--only-failed", action="store_true", help="仅在报告中显示失败的链接")

    args = parser.parse_args()

    all_tasks = []
    for path_str in args.paths:
        target = Path(path_str)
        if not target.exists():
            print(f"❌ 路径不存在，跳过: {target}", file=sys.stderr)
            continue
        if target.is_file():
            if target.suffix.lower() == '.md':
                all_tasks.extend(scan_file(target))
            else:
                print(f"⚠️  跳过非 Markdown 文件: {target}", file=sys.stderr)
        elif target.is_dir():
            for md_file in target.rglob("*.md"):
                all_tasks.extend(scan_file(md_file))
        else:
            print(f"⚠️  无效路径: {target}", file=sys.stderr)

    if not all_tasks:
        print("ℹ️  未找到任何可检查的链接", file=sys.stderr)
        sys.exit(0)

    print(f"🔍 共发现 {len(all_tasks)} 个链接，开始检查...")

    http_tasks = [t for t in all_tasks if t['type'] in ('http',)]
    non_http_tasks = [t for t in all_tasks if t['type'] != 'http']

    results = []

    # 非 HTTP 任务（同步）
    for task in non_http_tasks:
        results.append(check_task(task, None))

    # HTTP 任务（并发）
    if http_tasks:
        session = create_session()
        with ThreadPoolExecutor(max_workers=args.threads) as executor:
            future_to_task = {
                executor.submit(check_task, task, session): task for task in http_tasks
            }
            for future in as_completed(future_to_task):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    task = future_to_task[future]
                    results.append({
                        "file": task['file'],
                        "url": task['link'],
                        "type": "HTTP",
                        "status": "EXCEPTION",
                        "detail": str(e)
                    })

    passed = [r for r in results if r["status"] == "OK"]
    failed = [r for r in results if r["status"] in ("FAILED", "ERROR", "EXCEPTION")]
    skipped = [r for r in results if r["status"] == "SKIPPED"]

    # 生成报告
    with open(args.output, 'w', encoding='utf-8') as f:
        if args.only_failed:
            f.write("❌ 失败的链接:\n")
            if failed:
                for item in failed:
                    f.write(f"  - [{item['type']}] {item['url']} → {item['status']}: {item['detail']} (来自 {item['file']})\n")
            else:
                f.write("  无\n")
        else:
            f.write("✅ 通过的链接:\n")
            if passed:
                for item in passed:
                    f.write(f"  - [{item['type']}] {item['url']} (来自 {item['file']})\n")
            else:
                f.write("  无\n")

            f.write("\n❌ 失败的链接:\n")
            if failed:
                for item in failed:
                    f.write(f"  - [{item['type']}] {item['url']} → {item['status']}: {item['detail']} (来自 {item['file']})\n")
            else:
                f.write("  无\n")

            if skipped:
                f.write(f"\n⏭️  跳过的链接 ({len(skipped)} 个):\n")
                for item in skipped[:5]:
                    f.write(f"  - [{item['type']}] {item['url']} (来自 {item['file']})\n")
                if len(skipped) > 5:
                    f.write(f"  ... 还有 {len(skipped)-5} 个\n")

    # CSV
    with open(args.csv, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['file', 'url', 'type', 'status', 'detail']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\n📊 检查完成!")
    print(f"  通过: {len(passed)}")
    print(f"  失败: {len(failed)}")
    print(f"  跳过: {len(skipped)}")
    print(f"📄 报告: {os.path.abspath(args.output)}")
    print(f"📊 CSV: {os.path.abspath(args.csv)}")

    if failed:
        sys.exit(1)

if __name__ == "__main__":
    main()
