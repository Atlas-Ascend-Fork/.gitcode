#!/usr/bin/env python3
"""GitCode API 查询流水线执行情况"""

import argparse
import json
import re
import sys
import time
import urllib.request
import urllib.error

API_BASE = "https://api.gitcode.com"
PR_LABELS_URL = "https://api.gitcode.com/api/v5/repos/{0}/{1}/pulls/{2}/labels"

STATUS_ICON = {
    "COMPLETED": "✅",
    "SUCCEEDED": "✅",
    "SUCCESS": "✅",
    "FAILED": "❌",
    "FAILURE": "❌",
    "CANCELED": "⏹️",
    "CANCELLED": "⏹️",
    "SKIPPED": "⏭️",
    "RUNNING": "⏳",
    "QUEUED": "⏸️",
    "PENDING": "⏸️",
}

FAILED_STATUSES = {"FAILED", "FAILURE"}

LABEL_PASS = "ci-pipeline-passed"
LABEL_FAIL = "ci-pipeline-failed"


def api_get(url, token):
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"API 请求失败: HTTP {e.code}")
        print(e.read().decode("utf-8"))
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"网络请求失败: {e.reason}")
        sys.exit(1)


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


def get_pr_labels(owner, repo, pr_number, token):
    url = f"{PR_LABELS_URL.format(owner, repo, pr_number)}?access_token={token}&page=1&per_page=100"
    status, body = api_request(url, token, "GET")
    if status == 200 and isinstance(body, list):
        return [item.get("name", "") for item in body]
    print(f"获取 PR 标签列表失败: HTTP {status}")
    return []


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


def apply_label_by_jobs(owner, repo, pr_number, jobs, token):
    if not pr_number:
        return
    print(f"\n{'=' * 70}")
    print("  根据任务执行结果打标签")
    print(f"{'=' * 70}")
    print(f"  PR: #{pr_number}  任务总数: {len(jobs)}")
    success_statuses = {"COMPLETED", "SUCCEEDED", "SUCCESS"}
    failed_jobs = [j for j in jobs if j.get("status") in FAILED_STATUSES]
    non_success_jobs = [j for j in jobs if j.get("status") not in success_statuses]
    remove_pr_label(owner, repo, pr_number, LABEL_PASS, token)
    remove_pr_label(owner, repo, pr_number, LABEL_FAIL, token)
    if non_success_jobs:
        print(f"  非成功任务数: {len(non_success_jobs)} (失败: {len(failed_jobs)})")
        for j in non_success_jobs:
            print(f"    {j.get('display_name', j.get('name', 'N/A'))}: {j.get('status', 'N/A')}")
        add_pr_label(owner, repo, pr_number, LABEL_FAIL, token)
    else:
        print(f"  全部任务成功")
        add_pr_label(owner, repo, pr_number, LABEL_PASS, token)
    print()


def ts_to_str(ts):
    if not ts or ts <= 0:
        return "N/A"
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts / 1000))


def ms_to_str(ms):
    if not ms or ms <= 0:
        return "-"
    if ms < 60000:
        return f"{ms / 1000:.1f}s"
    m, s = divmod(ms // 1000, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}h{m}m{s}s"
    return f"{m}m{s}s"


def query_run_detail(owner, repo, run_id, token):
    url = f"{API_BASE}/api/v8/repos/{owner}/{repo}/actions/runs/{run_id}"
    return api_get(url, token)


def query_jobs(owner, repo, run_id, token):
    url = f"{API_BASE}/api/v8/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"
    return api_get(url, token)


def print_run_detail(data):
    print("=" * 70)
    print("  流水线运行详情")
    print("=" * 70)
    print(f"  名称:     {data.get('workflow_name', 'N/A')}")
    print(f"  状态:     {data.get('status', 'N/A')}")
    print(f"  运行编号: #{data.get('run_number', 'N/A')}")
    print(f"  分支:     {data.get('head_branch', 'N/A')}")
    print(f"  事件:     {data.get('event', 'N/A')}")
    sha = data.get("head_sha", "")
    print(f"  提交 SHA: {sha[:12] if sha else 'N/A'}")
    pr_id = data.get("pull_request_id", "")
    if pr_id:
        print(f"  PR 编号:  #{pr_id}")
    actor = data.get("actor", {})
    actor_name = actor.get("login", "N/A") if isinstance(actor, dict) else str(actor)
    print(f"  触发者:   {actor_name}")
    print(f"  开始时间: {ts_to_str(data.get('start_time'))}")
    print(f"  结束时间: {ts_to_str(data.get('end_time'))}")

    stages = data.get("stages", [])
    if stages:
        normal_stages = [s for s in stages if s.get("identifier") != "post_pipeline_stage" and s.get("category") != "post"]
        print(f"\n  阶段执行情况 ({len(normal_stages)} 个阶段):")
        print(f"  {'阶段名称':<20} {'状态':<14} {'开始时间':<22} {'结束时间'}")
        print(f"  {'-' * 20} {'-' * 14} {'-' * 22} {'-' * 22}")
        for stage in normal_stages:
            s_name = stage.get("name", "N/A")
            s_status = stage.get("status", "N/A")
            s_start = ts_to_str(stage.get("start_time"))
            s_end = ts_to_str(stage.get("end_time"))
            icon = STATUS_ICON.get(s_status, "⏳")
            print(f"  {icon} {s_name:<17} {s_status:<14} {s_start:<22} {s_end}")

    print()


def print_jobs(jobs_data, run_detail=None):
    all_jobs = jobs_data if isinstance(jobs_data, list) else jobs_data.get("jobs", [])

    # 过滤掉后处理阶段的 Job 和 workflow_call 类型的父 Job
    # 后处理 Job 的 identifier 为 job_post 或属于 post 阶段
    post_job_ids = set()
    if run_detail:
        for stage in run_detail.get("stages", []):
            if stage.get("identifier") == "post_pipeline_stage" or stage.get("category") == "post":
                for j in stage.get("jobs", []):
                    post_job_ids.add(j.get("identifier"))

    # 从 workflow_call 父 Job 构建 identifier -> name 映射
    parent_names = {}
    for j in all_jobs:
        if j.get("job_type") == "workflow_call":
            parent_names[j.get("identifier", "")] = j.get("name", "")

    jobs = []
    for j in all_jobs:
        if j.get("identifier") in post_job_ids or j.get("identifier") == "job_post":
            continue
        if j.get("job_type") == "workflow_call":
            continue
        # 如果是子 Job，用父 Job 名称做前缀，避免同名混淆
        ident = j.get("identifier", "")
        if "_" in ident:
            parts = ident.rsplit("_", 1)
            if parts[0] in parent_names and parts[1].isdigit():
                j = dict(j)
                parent_name = parent_names[parts[0]]
                j["display_name"] = f"{parent_name} / {j.get('name', 'N/A')}"
            else:
                j = dict(j)
                j["display_name"] = j.get("name", "N/A")
        else:
            j = dict(j)
            j["display_name"] = j.get("name", "N/A")
        jobs.append(j)

    print("=" * 70)
    print(f"  任务执行结果 (共 {len(jobs)} 个任务)")
    print("=" * 70)

    print(f"  {'任务名称':<55} {'状态':<14} {'耗时'}")
    print(f"  {'-' * 55} {'-' * 14} {'-' * 12}")

    success = failed = skipped = other = 0
    for job in jobs:
        name = job.get("display_name", "N/A")
        status = job.get("status", "N/A")
        cost = job.get("execute_cost_time", 0)
        icon = STATUS_ICON.get(status, "⏳")
        print(f"  {icon} {name:<52} {status:<14} {ms_to_str(cost)}")

        if status in ("COMPLETED", "SUCCEEDED", "SUCCESS"):
            success += 1
        elif status in ("FAILED", "FAILURE"):
            failed += 1
        elif status in ("SKIPPED",):
            skipped += 1
        else:
            other += 1

    print(f"  {'-' * 55} {'-' * 14} {'-' * 12}")
    print(f"  ✅ 完成: {success}  ❌ 失败: {failed}  ⏭️ 跳过: {skipped}  其他: {other}")
    print()
    return jobs


def parse_url(url):
    """从流水线页面 URL 提取 owner/repo/run_id"""
    pattern = r"gitcode\.com/([^/]+)/([^/]+)/actions/runs/([a-f0-9]+)"
    m = re.search(pattern, url)
    if not m:
        print(f"无法从 URL 解析流水线参数: {url}")
        sys.exit(1)
    return m.group(1), m.group(2), m.group(3)


def main():
    parser = argparse.ArgumentParser(description="查询 GitCode 流水线执行情况")
    parser.add_argument("--owner", help="仓库所属组织/用户")
    parser.add_argument("--repo", help="仓库名称")
    parser.add_argument("--run-id", help="流水线运行 ID")
    parser.add_argument("--url", help="流水线页面 URL（与 owner/repo/run-id 二选一）")
    parser.add_argument("--token", required=True, help="GitCode 个人访问令牌")
    parser.add_argument("--json", action="store_true", help="输出原始 JSON")
    parser.add_argument("--pr-number", default=None, help="PR 编号，传入后根据任务执行结果打标签")
    parser.add_argument("--apply-label", action="store_true", help="是否执行打标签逻辑")

    args = parser.parse_args()

    if args.url:
        args.owner, args.repo, args.run_id = parse_url(args.url)
    elif not all([args.owner, args.repo, args.run_id]):
        parser.error("请提供 --url 或同时提供 --owner --repo --run-id")

    run_detail = query_run_detail(args.owner, args.repo, args.run_id, args.token)
    jobs_data = query_jobs(args.owner, args.repo, args.run_id, args.token)

    if args.json:
        print("=== Run Detail ===")
        print(json.dumps(run_detail, indent=2, ensure_ascii=False))
        print("\n=== Jobs ===")
        print(json.dumps(jobs_data, indent=2, ensure_ascii=False))
        return

    print_run_detail(run_detail)
    jobs = print_jobs(jobs_data, run_detail)

    # 列出失败的 Job 供进一步查看
    failed_jobs = [j for j in jobs if j.get("status") in ("FAILED", "FAILURE")]
    if failed_jobs:
        print("  失败的 Job (可用 --job-id 查看详情):")
        for j in failed_jobs:
            print(f"    {j.get('name', 'N/A')}  ->  {j.get('id', 'N/A')}")
        print()

    # 根据 PR 编号和任务执行结果打标签
    if args.apply_label and args.pr_number:
        apply_label_by_jobs(args.owner, args.repo, args.pr_number, jobs, args.token)


if __name__ == "__main__":
    main()
