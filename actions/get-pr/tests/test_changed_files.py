#!/usr/bin/env python3
# Copyright (c) 2026 dhltat.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""Exercise the real get-pr shell against isolated local Git histories."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


def find_bash():
    if os.name == "nt":
        candidate = Path(os.environ.get("ProgramFiles", "C:/Program Files"))
        candidate /= "Git/bin/bash.exe"
        return str(candidate) if candidate.is_file() else None
    return shutil.which("bash")


BASH = find_bash()
GIT = shutil.which("git")
SCRIPT = Path(__file__).resolve().parents[1] / "dist/get_pr.sh"


@unittest.skipUnless(BASH and GIT, "Git and Bash are required")
class ChangedFilesTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="get-pr-history-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.author = self.root / "author"
        self.remote = self.root / "remote.git"
        self.checkout = self.root / "checkout"
        self.author.mkdir()
        self.git(self.root, "init", "--bare", str(self.remote))
        self.git(self.author, "init")
        self.git(self.author, "config", "user.name", "CI regression")
        self.git(self.author, "config", "user.email", "ci-test@example.invalid")
        self.git(self.author, "config", "core.autocrlf", "false")
        self.git(self.author, "checkout", "-b", "master")
        self.write("README.md", "base\n")
        self.write("gone.cpp", "remove in the PR\n")
        self.commit("base")
        self.git(self.author, "checkout", "-b", "feature")
        self.write("build.sh", "PR build change\n")
        self.write("docs/change.md", "PR documentation\n")
        self.git(self.author, "rm", "gone.cpp")
        self.commit("feature")
        self.git(self.author, "checkout", "master")
        self.write("target-before.cpp", "already in the target\n")
        self.commit("target before merge snapshot")
        self.git(self.author, "checkout", "-b", "snapshot")
        self.git(self.author, "merge", "--no-ff", "feature", "-m", "PR snapshot")
        self.git(self.author, "checkout", "master")
        self.write("pooling/avg_pool_grad/op_host/unrelated.cpp", "target-only\n")
        self.write("README.md", "target-only change after PR snapshot\n")
        self.commit("target advanced after snapshot")
        self.git(self.author, "remote", "add", "origin", self.remote.as_uri())
        self.git(self.author, "push", "origin", "master", "feature", "snapshot")
        self.script = self.root / "get_pr.sh"
        self.script.write_bytes(SCRIPT.read_bytes().replace(b"\r\n", b"\n"))

    def git(self, cwd, *arguments):
        result = subprocess.run(
            [GIT, "-C", str(cwd), *arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        return result.stdout.strip()

    def write(self, relative, content):
        path = self.author / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def commit(self, message):
        self.git(self.author, "add", ".")
        self.git(self.author, "commit", "-m", message)

    def clone(self, branch="snapshot", shallow=True):
        arguments = ["clone", "--branch", branch]
        if shallow:
            arguments += ["--depth", "1"]
        self.git(self.root, *arguments, self.remote.as_uri(), str(self.checkout))

    def run_script(self, target="master"):
        environment = os.environ.copy()
        environment.update(
            WORKSPACE=self.checkout.as_posix(),
            TARGET_BRANCH=target,
            GIT_TOKEN="",
            GIT_TERMINAL_PROMPT="0",
        )
        return subprocess.run(
            [BASH, self.script.as_posix()],
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )

    def assert_pr_files(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        paths = (self.checkout / "pr_filelist.txt").read_text().splitlines()
        self.assertEqual(set(paths), {"build.sh", "docs/change.md", "gone.cpp"})
        self.assertEqual(len(paths), 3)
        detail = (self.checkout / "update_file_detail.txt").read_text()
        self.assertNotIn("avg_pool_grad", detail)
        self.assertNotIn("target-before.cpp", detail)
        self.assertNotIn("target-only", (self.checkout / "gitdiff.txt").read_text())

    def test_merge_snapshot_ignores_later_target_commits(self):
        self.clone()
        self.assert_pr_files(self.run_script())

    def test_source_checkout_uses_common_ancestor(self):
        self.clone(branch="feature")
        self.assert_pr_files(self.run_script())

    def test_full_history_checkout_does_not_unshallow_again(self):
        self.clone(shallow=False)
        self.assert_pr_files(self.run_script())

    def test_deletions_still_reach_the_changed_file_gate(self):
        self.clone()
        self.assert_pr_files(self.run_script())
        status = (self.checkout / "pr_filelist_mod.txt").read_text().splitlines()
        self.assertIn("D\tgone.cpp", status)
        precommit = (self.checkout / "pr_filelist_precommit.txt").read_text()
        self.assertNotIn("gone.cpp", precommit)
        self.assertIn("build.sh", precommit)

    def test_missing_target_fails_before_writing_file_lists(self):
        self.clone()
        result = self.run_script(target="missing-branch")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.checkout / "pr_filelist.txt").exists())

    def test_failed_fetch_is_not_replaced_with_stale_remote_data(self):
        self.clone(shallow=False)
        self.git(
            self.checkout, "remote", "set-url", "origin", str(self.root / "missing")
        )
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.checkout / "pr_filelist.txt").exists())

    def test_unrelated_histories_fail_before_writing_file_lists(self):
        self.git(self.author, "checkout", "--orphan", "unrelated")
        self.write("orphan.cpp", "no common ancestor\n")
        self.commit("unrelated history")
        self.git(self.author, "push", "origin", "unrelated")
        self.clone(branch="unrelated")
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.checkout / "pr_filelist.txt").exists())


if __name__ == "__main__":
    unittest.main()
