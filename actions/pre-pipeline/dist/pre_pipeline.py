#!/usr/bin/env python3
"""流水线开始前给 PR 打上 ci-pipeline-running 标签"""

import argparse
import json
import sys
import time
import urllib.request
import urllib.error

API_BASE = "https://api.gitcode.com"
PR_LABELS_URL = "https://api.gitcode.com/api/v5/repos/{0}/{1}/pulls/{2}/labels"
LABEL_RUNNING = "ci-pipeline-running"
LABEL_PASS = "ci-pipeline-passed"
LABEL_FAIL = "ci-pipeline-failed"


def api_request(url, token, method="GET", data=None):
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    if data is not None:
        req.data = json.dumps(data).encode("utf-8")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else None
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        print(f"网络请求失败: {e.reason}")
        return -1, str(e.reason)


def add_pr_label(owner, repo, pr_number, label, token, max_retries=1):
    url = f"{PR_LABELS_URL.format(owner, repo, pr_number)}?access_token={token}"
    for attempt in range(max_retries + 1):
        status, body = api_request(url, token, "POST", [label])
        if status == 201:
            print(f"✅ 打标签 [{label}] 成功")
            return True
        if status == 429 and attempt < max_retries:
            wait = 10
            print(f"⚠️ 打标签触发限流，{wait}s 后重试 (attempt {attempt + 1}/{max_retries})")
            time.sleep(wait)
            continue
        print(f"❌ 打标签 [{label}] 失败: HTTP {status}, {body}")
        return False
    return False


def remove_pr_label(owner, repo, pr_number, label, token, max_retries=1):
    url = f"{PR_LABELS_URL.format(owner, repo, pr_number)}/{label}?access_token={token}"
    for attempt in range(max_retries + 1):
        status, body = api_request(url, token, "DELETE")
        if status == 204:
            print(f"✅ 移除标签 [{label}] 成功")
            return True
        if status == 429 and attempt < max_retries:
            wait = 10
            print(f"⚠️ 移除标签触发限流，{wait}s 后重试 (attempt {attempt + 1}/{max_retries})")
            time.sleep(wait)
            continue
        if status == 404:
            print(f"ℹ️ 标签 [{label}] 不存在，无需移除")
            return True
        print(f"❌ 移除标签 [{label}] 失败: HTTP {status}, {body}")
        return False
    return False


def main():
    parser = argparse.ArgumentParser(description="流水线开始前给 PR 打上 ci-pipeline-running 标签")
    parser.add_argument("--owner", required=True, help="仓库所属组织/用户")
    parser.add_argument("--repo", required=True, help="仓库名称")
    parser.add_argument("--pr_number", type=int, required=True, help="PR 编号")
    parser.add_argument("--token", required=True, help="GitCode 个人访问令牌")
    parser.add_argument("--apply_label", type=lambda x: x.lower() in ("true", "1", "yes"),
                        default=True, help="是否执行打标签逻辑")
    args = parser.parse_args()

    if not args.apply_label:
        print("apply_label 为 false，跳过打标签")
        return

    print(f"{'=' * 70}")
    print(f"  流水线开始：PR #{args.pr_number} ({args.owner}/{args.repo})")
    print(f"{'=' * 70}")

    remove_pr_label(args.owner, args.repo, args.pr_number, LABEL_PASS, args.token)
    remove_pr_label(args.owner, args.repo, args.pr_number, LABEL_FAIL, args.token)
    add_pr_label(args.owner, args.repo, args.pr_number, LABEL_RUNNING, args.token)
    print()


if __name__ == "__main__":
    main()
