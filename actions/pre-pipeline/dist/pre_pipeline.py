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
PERMISSION_URL = "https://api.gitcode.com/api/v5/repos/{0}/{1}/collaborators/{2}/permission"
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


def get_user_permission(owner, repo, username, token):
    """查询用户对仓库的权限, 返回 (ok, permission, role_name)"""
    url = PERMISSION_URL.format(owner, repo, username)
    status, resp = api_request(url, token)
    if status != 200 or not isinstance(resp, dict) or resp.get("error_code"):
        return False, None, None
    return True, resp.get("permission", ""), resp.get("role_name", "")


def check_push_permission(owner, repo, actor, pr_author, token):
    """检查触发者是否具备目标仓库(owner/repo)的权限, 返回 (通过, 说明文本)"""
    if not actor:
        return True, ""  # 未识别触发者, 不拦截
    if actor == pr_author:
        return True, ""  # PR 作者本人触发 → 通过

    ok, permission, role_name = get_user_permission(owner, repo, actor, token)
    if not ok:
        return False, f"触发者 **{actor}** 非目标仓库 **{owner}/{repo}** 的成员, 不具备目标仓库的权限。"
    if permission in ("push", "admin"):
        return True, ""
    return False, (f"触发者 **{actor}** 对目标仓库 **{owner}/{repo}** "
                   f"仅有 **{permission or '只读'}** 权限, 不具备目标仓库的写权限。")


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
    """批量移除 PR 标签: DELETE /labels/name1,name2 (逗号分隔一次删除)"""
    if not labels:
        return True
    names = ",".join(labels)
    url = f"{PR_LABELS_URL.format(owner, repo, pr_number)}/{names}?access_token={token}"
    for attempt in range(max_retries + 1):
        status, body = api_request(url, token, "DELETE")
        if status in (200, 204):
            print(f"✅ 批量移除标签 [{names}] 成功")
            return True
        if status == 429 and attempt < max_retries:
            wait = 10
            print(f"⚠️ 批量移除标签触发限流，{wait}s 后重试 (attempt {attempt + 1}/{max_retries})")
            time.sleep(wait)
            continue
        if status == 404:
            print(f"ℹ️ 标签 [{names}] 不存在，无需移除")
            return True
        print(f"❌ 批量移除标签 [{names}] 失败: HTTP {status}, {body}")
        return False
    return False


def main():
    parser = argparse.ArgumentParser(description="流水线开始前给 PR 打上 ci-pipeline-running 标签, 并发布流水线链接评论")
    parser.add_argument("--owner", required=True, help="仓库所属组织/用户")
    parser.add_argument("--repo", required=True, help="仓库名称")
    parser.add_argument("--pr_number", type=int, required=True, help="PR 编号")
    parser.add_argument("--pr_author", default="", help="PR 作者用户名(= atomgit.event.pull_request.user.login)")
    parser.add_argument("--token", required=True, help="GitCode 个人访问令牌")
    parser.add_argument("--apply_label", type=lambda x: x.lower() in ("true", "1", "yes"),
                        default=False, help="是否执行打标签逻辑")
    parser.add_argument("--run_url", default="", help="当前流水线运行链接, 传入则发布 PR 评论")
    parser.add_argument("--actor", default="", help="流水线触发者用户名, 用于目标仓库权限检查")
    args = parser.parse_args()

    print(f"{'=' * 70}")
    print(f"  流水线开始：PR #{args.pr_number} ({args.owner}/{args.repo})")
    print(f"{'=' * 70}")

    if not args.apply_label:
        print("apply_label 为 false，跳过打标签与评论")
        return

    # 触发者目标仓库权限检查(失败则发布失败评论并终止)
    perm_ok, perm_msg = check_push_permission(args.owner, args.repo, args.actor, args.pr_author, args.token)
    if not perm_ok:
        print(f"❌ 目标仓库权限检查不通过: {perm_msg}")
        comment_body = (
            "| ❌ CI 流水线启动失败 |\n"
            "| --- |\n"
            f"| ⚠️ 目标仓库权限: {perm_msg} |\n"
            "| 处理: 由具备权限的成员触发, 或为触发者添加仓库权限 |\n"
        )
        if args.run_url:
            comment_body += f"| 📋 执行详情: [点击查看流水线]({args.run_url}) |\n"
        post_pr_comment(args.owner, args.repo, args.pr_number, comment_body, args.token)
        sys.exit(1)

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
