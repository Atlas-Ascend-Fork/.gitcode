#!/usr/bin/env python3
"""GitCode 流水线日志下载工具

通过 GitCode OpenAPI 下载指定流水线运行的所有 Job 日志：
  - 全部 Job 日志打包为 all_logs.zip
  - 失败 Job 日志打包为 failed_logs.zip

API 文档：
  - 获取流水线运行详情: GET /api/v8/repos/{owner}/{repo}/actions/runs/{run_id}
  - 获取 Job 列表:       GET /api/v8/repos/{owner}/{repo}/actions/runs/{run_id}/jobs
  - 下载 Job 日志:        GET /api/v8/repos/{owner}/{repo}/actions/runs/{run_id}/jobs/{job_id}/download_log

用法:
  python3 download_logs.py --owner cann --repo runtime \
      --run-id f833dac756e64ce3ab3d963fac641967 --token <TOKEN>

  # 从流水线页面 URL 直接提取参数
  python3 download_logs.py --url https://gitcode.com/cann/runtime/actions/runs/f833dac756e64ce3ab3d963fac641967 --token <TOKEN>
"""

import argparse
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import zipfile

API_BASE = "https://api.gitcode.com"

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
    "INIT": "⏸️",
}

FAILED_STATUSES = {"FAILED", "FAILURE"}


def api_get(url, token, raw=False):
    """发起 GET 请求，raw=True 时返回 bytes（用于下载日志）"""
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
            if raw:
                return data
            return json.loads(data.decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        if raw:
            return None
        return {"_error": True, "_code": e.code, "_body": body}
    except urllib.error.URLError as e:
        print(f"  网络请求失败: {e.reason}")
        sys.exit(1)


def get_run_detail(owner, repo, run_id, token):
    url = f"{API_BASE}/api/v8/repos/{owner}/{repo}/actions/runs/{run_id}"
    return api_get(url, token)


def get_jobs(owner, repo, run_id, token):
    url = f"{API_BASE}/api/v8/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"
    return api_get(url, token)


def download_job_log(owner, repo, run_id, job_id, token):
    """下载单个 Job 的日志，返回 bytes（zip 格式）或 None"""
    url = f"{API_BASE}/api/v8/repos/{owner}/{repo}/actions/runs/{run_id}/jobs/{job_id}/download_log"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    # download_log 返回 302 重定向到实际日志存储地址，需禁用自动重定向以手动处理
    # （重定向地址不带认证头，需用 opener 跟随）
    opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler)
    try:
        with opener.open(req, timeout=60) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        print(f"\n  HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:200]}")
        return None
    except urllib.error.URLError as e:
        print(f"\n  网络请求失败: {e.reason}")
        return None


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


def parse_url(url):
    """从流水线页面 URL 提取 owner/repo/run_id"""
    pattern = r"gitcode\.com/([^/]+)/([^/]+)/actions/runs/([a-f0-9]+)"
    m = re.search(pattern, url)
    if not m:
        print(f"无法从 URL 解析流水线参数: {url}")
        sys.exit(1)
    return m.group(1), m.group(2), m.group(3)


def extract_log_from_zip(zip_bytes, job_name):
    """从 API 返回的 zip 中提取日志文本，返回 (log_text, source_filename)"""
    if not zip_bytes:
        return None, None
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile:
        # 可能直接是文本日志
        text = zip_bytes.decode("utf-8", errors="replace")
        return text, f"{job_name}.log"
    log_parts = []
    source_name = None
    for name in sorted(zf.namelist()):
        if name.endswith("/"):
            continue
        content = zf.read(name)
        source_name = source_name or name
        try:
            log_parts.append(content.decode("utf-8", errors="replace"))
        except Exception:
            log_parts.append(f"[binary content: {name}]\n")
    return "\n".join(log_parts), source_name


def build_log_header(job, run_detail):
    """为日志文件生成头部信息"""
    lines = [
        "=" * 70,
        f"Job: {job.get('name', 'N/A')}",
        f"Identifier: {job.get('identifier', 'N/A')}",
        f"Status: {job.get('status', 'N/A')}",
        f"耗时: {ms_to_str(job.get('execute_cost_time', 0))}",
        f"开始: {ts_to_str(job.get('start_time'))}",
        f"结束: {ts_to_str(job.get('end_time'))}",
    ]
    if run_detail:
        lines.append(f"Workflow: {run_detail.get('workflow_name', 'N/A')}")
        lines.append(f"分支: {run_detail.get('head_branch', 'N/A')}")
        lines.append(f"PR: #{run_detail.get('pull_request_id', 'N/A')}")
    msg = job.get("message")
    if msg:
        lines.append(f"消息: {msg}")
    steps = job.get("steps", [])
    if steps:
        lines.append("")
        lines.append("步骤明细:")
        for s in steps:
            s_status = s.get("status", "N/A")
            s_name = s.get("name", "N/A")
            s_cost = 0
            s_start = s.get("start_time", 0)
            s_end = s.get("end_time", 0)
            if s_start and s_end and s_start > 0 and s_end > 0:
                s_cost = s_end - s_start
            icon = STATUS_ICON.get(s_status, "⏳")
            lines.append(f"  {icon} {s_name:<35} {s_status:<12} {ms_to_str(s_cost)}")
    lines.append("=" * 70)
    lines.append("")
    return "\n".join(lines)


def sanitize_filename(name):
    """清理文件名中的非法字符"""
    return re.sub(r'[<>:"/\\|?*]', "_", name)


def main():
    parser = argparse.ArgumentParser(
        description="下载 GitCode 流水线运行日志并打包",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 download_logs.py --owner cann --repo runtime \\
      --run-id f833dac756e64ce3ab3d963fac641967 --token <TOKEN>

  python3 download_logs.py \\
      --url https://gitcode.com/cann/runtime/actions/runs/f833dac756e64ce3ab3d963fac641967 \\
      --token <TOKEN>
        """,
    )
    parser.add_argument("--owner", help="仓库所属组织/用户")
    parser.add_argument("--repo", help="仓库名称")
    parser.add_argument("--run-id", help="流水线运行 ID")
    parser.add_argument("--url", help="流水线页面 URL（与 owner/repo/run-id 二选一）")
    parser.add_argument("--token", required=True, help="GitCode 个人访问令牌")
    parser.add_argument(
        "-o", "--output-dir", default=os.path.dirname(os.path.abspath(__file__)),
        help="输出目录（默认脚本所在目录）",
    )
    args = parser.parse_args()

    if args.url:
        args.owner, args.repo, args.run_id = parse_url(args.url)
    elif not all([args.owner, args.repo, args.run_id]):
        parser.error("请提供 --url 或同时提供 --owner --repo --run-id")

    owner, repo, run_id, token = args.owner, args.repo, args.run_id, args.token

    print(f"{'=' * 60}")
    print(f"  流水线日志下载: {owner}/{repo}")
    print(f"  Run ID: {run_id}")
    print(f"{'=' * 60}")

    # 1. 获取流水线运行详情
    print("\n[1/4] 获取流水线运行详情...")
    run_detail = get_run_detail(owner, repo, run_id, token)
    if run_detail.get("_error"):
        print(f"  ❌ 获取运行详情失败: HTTP {run_detail['_code']}")
        print(f"  {run_detail.get('_body', '')}")
        sys.exit(1)
    wf_name = run_detail.get("workflow_name", "N/A")
    run_status = run_detail.get("status", "N/A")
    print(f"  Workflow: {wf_name}")
    print(f"  状态:     {run_status}")
    print(f"  分支:     {run_detail.get('head_branch', 'N/A')}")
    print(f"  PR:       #{run_detail.get('pull_request_id', 'N/A')}")
    print(f"  开始:     {ts_to_str(run_detail.get('start_time'))}")
    print(f"  结束:     {ts_to_str(run_detail.get('end_time'))}")

    # 2. 获取 Job 列表
    print("\n[2/4] 获取 Job 列表...")
    jobs_data = get_jobs(owner, repo, run_id, token)
    if jobs_data.get("_error"):
        print(f"  ❌ 获取 Job 列表失败: HTTP {jobs_data['_code']}")
        print(f"  {jobs_data.get('_body', '')}")
        sys.exit(1)
    all_jobs = jobs_data.get("jobs", [])
    print(f"  共 {len(all_jobs)} 个 Job")

    # 过滤：跳过 workflow_call 父 Job（无实际日志），保留 normal 类型
    # 同时跳过 post 阶段的 Job
    post_ids = set()
    for stage in run_detail.get("stages", []):
        if stage.get("identifier") == "post_pipeline_stage" or stage.get("category") == "post":
            for j in stage.get("jobs", []):
                post_ids.add(j.get("identifier"))

    jobs = []
    for j in all_jobs:
        if j.get("identifier") in post_ids or j.get("identifier") == "job_post":
            continue
        if j.get("job_type") == "workflow_call":
            continue
        jobs.append(j)

    success = failed = other = 0
    for j in jobs:
        s = j.get("status", "")
        if s in ("COMPLETED", "SUCCEEDED", "SUCCESS"):
            success += 1
        elif s in FAILED_STATUSES:
            failed += 1
        else:
            other += 1

    print(f"  有效 Job: {len(jobs)} 个（已过滤 workflow_call 父 Job 和 post 阶段）")
    print(f"  ✅ 完成: {success}  ❌ 失败: {failed}  其他: {other}")
    print(f"\n  {'Job 名称':<45} {'状态':<12} {'耗时'}")
    print(f"  {'-' * 45} {'-' * 12} {'-' * 12}")
    for j in jobs:
        name = j.get("name", "N/A")
        status = j.get("status", "N/A")
        cost = j.get("execute_cost_time", 0)
        icon = STATUS_ICON.get(status, "⏳")
        print(f"  {icon} {name:<42} {status:<12} {ms_to_str(cost)}")

    # 3. 下载每个 Job 的日志
    print(f"\n[3/4] 下载 Job 日志...")
    all_logs = {}
    failed_logs = {}
    for j in jobs:
        job_id = j.get("id")
        job_name = j.get("name", "unknown")
        job_ident = j.get("identifier", "unknown")
        status = j.get("status", "N/A")
        icon = STATUS_ICON.get(status, "⏳")
        display_name = f"{job_ident}__{job_name}"
        safe_name = sanitize_filename(display_name)

        print(f"  {icon} 下载: {display_name} ...", end=" ", flush=True)
        log_bytes = download_job_log(owner, repo, run_id, job_id, token)
        if log_bytes is None:
            print("跳过（日志不可用或已过期）")
            header = build_log_header(j, run_detail)
            log_content = header + "[日志不可用]\n"
        else:
            log_text, _ = extract_log_from_zip(log_bytes, job_name)
            header = build_log_header(j, run_detail)
            if log_text:
                log_content = header + log_text
            else:
                log_content = header + "[日志内容为空]\n"
            print(f"✅ ({len(log_content)} 字符)")

        all_logs[safe_name] = log_content
        if status in FAILED_STATUSES:
            failed_logs[safe_name] = log_content

    # 4. 打包
    print(f"\n[4/4] 打包日志...")
    os.makedirs(args.output_dir, exist_ok=True)

    all_zip_path = os.path.join(args.output_dir, "all_logs.zip")
    with zipfile.ZipFile(all_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in sorted(all_logs.items()):
            zf.writestr(f"{name}.log", content)
    print(f"  📦 全部日志: {all_zip_path} ({len(all_logs)} 个 Job)")

    if failed_logs:
        failed_zip_path = os.path.join(args.output_dir, "failed_logs.zip")
        with zipfile.ZipFile(failed_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, content in sorted(failed_logs.items()):
                zf.writestr(f"{name}.log", content)
        print(f"  📦 失败日志: {failed_zip_path} ({len(failed_logs)} 个 Job)")
    else:
        print(f"  📦 失败日志: 无失败 Job，跳过")

    print(f"\n{'=' * 60}")
    print(f"  完成!")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
