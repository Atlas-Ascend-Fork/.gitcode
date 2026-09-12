#!/usr/bin/env python3
"""流水线开始前给 PR 打上 ci-pipeline-running 标签, 并发布流水线链接评论"""

import argparse
import json
import sys
import time
import urllib.request
import urllib.error

API_BASE = "https://api.gitcode.com"
PR_LABELS_URL = "https://api.gitcode.com/api/v5/repos/{0}/{1}/pulls/{2}/labels"
PR_COMMENT_URL = "https://api.gitcode.com/api/v5/repos/{0}/{1}/pulls/{2}/comments"
LABEL_RUNNING = "ci-pipeline-running"
LABEL_PASS = "ci-pipeline-passed"
LABEL_FAIL = "ci-pipeline-failed"


def api_request(url, token, method="GET", data=None):
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json;charset=UTF-8")
    if data is not None:
        req.data = json.dumps(data).encode("utf-8")
    try:
        with urllib.request.urlopen(req, timeout=200) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else None
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        print(f"网络请求失败: {e.reason}")
        return -1, str(e.reason)


def post_pr_comment(owner, repo, pr_number, body, token, max_retries=1):
    url = PR_COMMENT_URL.format(owner, repo, pr_number)
    post_data = {"access_token": token, "body": body}
    for attempt in range(max_retries + 1):
        status, resp = api_request(url, token, "POST", post_data)
        if status in (200, 201, 204):
            comment_id = resp.get("note_id") if isinstance(resp, dict) else None
            print(f"✅ PR 评论发布成功, comment_id: {comment_id}")
            return True
        if status == 429 and attempt < max_retries:
            wait = 10
            print(f"⚠️ 评论触发限流，{wait}s 后重试 (attempt {attempt + 1}/{max_retries})")
            time.sleep(wait)
            continue
        print(f"❌ PR 评论发布失败: HTTP {status}, {resp}")
        return False
    return False


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


def remove_pr_labels_batch(owner, repo, pr_number, labels, token, max_retries=1):
    """批量移除 PR 标签: 逐个调用 DELETE /labels/{name}
    注: 逗号分隔的批量 URL(/labels/name1,name2) 会被 apig 网关拒绝(HTTP 403), 只能逐个删除"""
    for label in labels:
        url = f"{PR_LABELS_URL.format(owner, repo, pr_number)}/{label}?access_token={token}"
        for attempt in range(max_retries + 1):
            status, body = api_request(url, token, "DELETE")
            if status in (200, 204):
                print(f"✅ 移除标签 [{label}] 成功")
                break
            if status == 429 and attempt < max_retries:
                wait = 10
                print(f"⚠️ 移除标签触发限流，{wait}s 后重试 (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait)
                continue
            if status == 404:
                body_str = body if isinstance(body, str) else json.dumps(body)
                if "project not found" in body_str.lower():
                    print(f"❌ 移除标签 [{label}] 失败: 仓库不存在 (project not found)，请检查 owner/repo 参数")
                    return False
                print(f"ℹ️ 标签 [{label}] 不存在，无需移除")
                break
            print(f"❌ 移除标签 [{label}] 失败: HTTP {status}, {body}")
            break
    return True


def main():
    parser = argparse.ArgumentParser(description="流水线开始前给 PR 打上 ci-pipeline-running 标签, 并发布流水线链接评论")
    parser.add_argument("--owner", required=True, help="仓库所属组织/用户")
    parser.add_argument("--repo", required=True, help="仓库名称")
    parser.add_argument("--pr_number", type=int, required=True, help="PR 编号")
    parser.add_argument("--token", required=True, help="GitCode 个人访问令牌")
    parser.add_argument("--apply_label", type=lambda x: x.lower() in ("true", "1", "yes"),
                        default=False, help="是否执行打标签逻辑")
    parser.add_argument("--run_url", default="", help="当前流水线运行链接, 传入则发布 PR 评论")
    args = parser.parse_args()

    print(f"{'=' * 70}")
    print(f"  流水线开始：PR #{args.pr_number} ({args.owner}/{args.repo})")
    print(f"{'=' * 70}")

    if not args.apply_label:
        print("apply_label 为 false，跳过打标签与评论")
        return

    # 发布流水线链接评论
    if args.run_url:
        comment_body = (
            "| 🚀 CI 流水线已启动 |\n"
            "| --- |\n"
            f"| 📋 执行详情: [点击查看流水线]({args.run_url}) |\n"
        )
        post_pr_comment(args.owner, args.repo, args.pr_number, comment_body, args.token)
    else:
        print("未传入 run_url，跳过流水线链接评论")
    print()

    # 一次批量移除旧 CI 标签
    remove_pr_labels_batch(args.owner, args.repo, args.pr_number, [LABEL_PASS, LABEL_FAIL], args.token)
    add_pr_label(args.owner, args.repo, args.pr_number, LABEL_RUNNING, args.token)
    print()


if __name__ == "__main__":
    main()
