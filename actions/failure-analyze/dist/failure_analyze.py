#!/usr/bin/env python3
"""流水线失败时触发 Agent 分析失败原因。

设计(零 GitCode API 查询):
  - 流水线成败由 query_pipeline 步骤输出的 pipeline_failed 变量传递
      pipeline_failed == "false" → 流水线成功, 跳过失败分析;
                                    若 enable_success_review=true 且有 pr_number/git_token,
                                    则向 PR 写入 "/ai review force" 评论(成功态 AI 审查入口)
      pipeline_failed == "true"  → 存在失败 Job, 触发分析
      变量缺失                   → query_pipeline 自身异常(如限流), 兜底触发
  - 分析内容直接给 run 链接, 由 Agent 侧技能(gitcode-ci-api 等)自行拉取数据
  - 触发调用失败仅告警不阻断(业务上恒 exit 0, 除非参数缺失)
"""

import json
import os
import sys
import urllib.error
import urllib.request


def env(name, default=""):
    return os.environ.get(name, default).strip()


def post_trigger(url, token, payload, timeout=60):
    """POST trigger, 返回 (http_code, body)"""
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:
        return -1, str(e)


def post_pr_comment(owner, repo, pr_number, body, token, max_retries=2):
    """写 PR 评论(与 pre-pipeline 同端点); 返回 (http_code, resp)"""
    url = f"https://api.gitcode.com/api/v5/repos/{owner}/{repo}/pulls/{pr_number}/comments"
    data = json.dumps({"access_token": token, "body": body}).encode("utf-8")
    last = (-1, "")
    for _ in range(max_retries):
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status, resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            last = (e.code, e.read().decode("utf-8", errors="replace"))
            if e.code not in (429, 500, 502):
                break
        except Exception as e:
            last = (-1, str(e))
    return last


def main():
    enable = env("ENABLE", "false").lower() in ("true", "1", "yes")
    if not enable:
        print("失败分析未启用(enable=false, 建议配置 vars.FAILURE_ANALYZE_ENABLE=true 开启), 跳过")
        return 0
    owner = env("OWNER")
    repo = env("REPO")
    run_id = env("RUN_ID")
    pr_number = env("PR_NUMBER")
    pipeline_failed = env("PIPELINE_FAILED").lower()
    session_id = env("SESSION_ID")
    event_key = env("EVENT_KEY") or "gate_check"
    hub_token = env("AGENT_HUB_TOKEN")
    hub_url = env("AGENT_HUB_URL", "https://cannbot.hicann.cn/agent-hub")
    enable_pr_comment = env("ENABLE_PR_COMMENT", "false").lower() in ("true", "1", "yes")

    if not (owner and repo and run_id):
        print("未提供 owner/repo/run_id, 跳过失败分析")
        return 0
    if not session_id:
        print("未配置 session_id(建议配置 vars.AGENT_SESSION_ID), 跳过失败分析")
        return 0

    # ---- 1. 依据 query_pipeline 传递的变量判断 ----
    if pipeline_failed == "false":
        print("流水线成功(query_pipeline: pipeline_failed=false), 无需失败分析")
        enable_success_review = env("ENABLE_SUCCESS_REVIEW", "false").lower() in ("true", "1", "yes")
        if not enable_success_review:
            print("成功评论未启用(enable_success_review=false, 建议配置 vars.SUCCESS_AI_REVIEW_ENABLE=true 开启), 跳过")
            return 0
        git_token = env("GIT_TOKEN")
        if not (pr_number and git_token):
            print(f"成功评论缺少前置条件(pr_number={'有' if pr_number else '无'}, git_token={'有' if git_token else '无'}), 跳过")
            return 0
        print(f"流水线成功, 向 PR#{pr_number} 写入 /ai review force 评论")
        code, body = post_pr_comment(owner, repo, pr_number, "/ai review force", git_token)
        if 200 <= code < 300:
            print(f"✅ /ai review force 评论已写入 PR#{pr_number}(HTTP {code})")
        else:
            print(f"WARNING: /ai review force 评论写入失败(HTTP {code}): {body[:200]} —— 不阻断流水线")
        return 0
    if pipeline_failed == "true":
        reason = "query_pipeline 检测到失败 Job"
    else:
        reason = "query_pipeline 未输出结果(自身执行异常, 如 API 限流), 兜底触发分析"

    # ---- 2. 组装分析内容(简洁: 技能用法/输出格式/回写规则由 agent 定义约束, 不在指令里重复) ----
    run_url = f"https://gitcode.com/{owner}/{repo}/actions/runs/{run_id}"
    pr_part = f"(PR#{pr_number}) " if pr_number else ""
    content = f"分析流水线失败: {owner}/{repo} {pr_part}{run_url}"
    # PR 评论回写开关: 开启时追加一句; 关闭时不再提(agent 定义默认即不回写)
    if enable_pr_comment and pr_number:
        content += f"\n分析结果回写到 PR#{pr_number} 评论区。"

    print(f"触发 Agent 失败分析: session={session_id}, event_key={event_key}({reason})")
    print(f"分析内容: {content}")

    # ---- 3. 触发 Agent ----
    code, body = post_trigger(
        f"{hub_url.rstrip('/')}/agenthubs/api/agents/sessions/{session_id}/trigger",
        hub_token, {"content": content, "event_key": event_key})

    if 200 <= code < 300:
        print(f"✅ Agent 分析已触发(HTTP {code}): {body[:300]}")
        return 0

    print(f"WARNING: Agent 分析触发失败(HTTP {code}): {body[:200]} —— 不阻断流水线")
    return 0


if __name__ == "__main__":
    sys.exit(main())
