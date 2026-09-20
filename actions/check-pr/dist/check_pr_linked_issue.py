#!/usr/bin/env python3
"""Check whether a PR is linked to at least one open issue (ported from pre_commit.py check_pr_linked_issues)."""
import os
import sys

import requests

GITCODE_API = "https://api.gitcode.com/api/v5/repos"
TIMEOUT = 60


def log_error(msg):
    print(f"[ERROR] {msg}")


def main():
    repo = os.environ.get("REPOSITORY_NAME", "")
    pr_number = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("PR_NUMBER", "")
    owner = os.environ.get("ORG_NAME", "cann")
    token = (
        os.environ.get("ACCESS_TOKEN")
        or os.environ.get("gitcode_access_token")
        or os.environ.get("GIT_TOKEN")
        or ""
    )
    print(f"[INFO] check_pr_linked_issue: repo={repo!r}, merge_id={pr_number!r}")
    if not repo or not pr_number:
        print(f"skip check_pr_linked_issue: repo={repo!r}, merge_id={pr_number!r}")
        return 0

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json;charset=UTF-8",
    }

    url = f"{GITCODE_API}/opencann/{repo}/pulls/{pr_number}/issues"
    print("+++++++++++")
    print(url)
    response = requests.get(url, headers=headers, timeout=TIMEOUT)
    if response.status_code not in [200, 201, 204]:
        log_error(f"Query PR({pr_number}) linked issues failed.")
        log_error(response.text)
        return 1
    linked_issues = response.json()
    if not linked_issues:
        log_error(f"PR({pr_number}) is not linked to any issue. Please link to an open issue.")
        return 1

    open_issues_numbers = []
    close_issues_numbers = []
    for issue in linked_issues:
        issue_number = issue.get("number", "")
        if issue_number == "":
            continue
        url = f"{GITCODE_API}/{owner}/{repo}/issues/{issue_number}"
        response = requests.get(url, headers=headers, timeout=TIMEOUT)
        if response.status_code not in [200, 201, 204]:
            log_error(f"Query PR({pr_number}) linked issues({issue_number}) failed.")
            log_error(response.text)
            return 1
        state = str(response.json().get("state", ""))
        if state == "open":
            open_issues_numbers.append(str(issue_number))
        else:
            close_issues_numbers.append(str(issue_number))

    if len(open_issues_numbers) == 0:
        log_error(f"PR({pr_number}) is not linked to any open issue. Please link to an open issue.")
        return 1
    print(
        f"PR({pr_number}) linked {len(open_issues_numbers)} open issues[{', '.join(open_issues_numbers)}], "
        f"{len(close_issues_numbers)} closed issues[{', '.join(close_issues_numbers)}]."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
