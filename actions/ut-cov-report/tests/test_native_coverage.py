# Copyright (c) 2026 dhltat.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.
"""Coverage collection must prefer merged scopes and fail without data."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "dist/ut_cov.sh"


def find_bash():
    if os.name == "nt":
        candidate = Path(os.environ.get("ProgramFiles", "C:/Program Files"))
        candidate /= "Git/bin/bash.exe"
        return str(candidate) if candidate.is_file() else None
    return shutil.which("bash")


BASH = find_bash()


@unittest.skipUnless(BASH, "Bash is required for integration tests")
class NativeCoverageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.script = self.root / "ut_cov.sh"
        self.script.write_bytes(SCRIPT.read_bytes().replace(b"\r\n", b"\n"))
        git = self.bin / "git"
        git.write_bytes(
            b'#!/bin/bash\nif [[ "$1" == remote ]]; then echo https://example.invalid/repo.git; fi\nexit 0\n'
        )
        git.chmod(0o755)

    def run_script(self, overrides=None):
        env = {
            **os.environ,
            "WORKSPACE": self.root.as_posix(),
            "COV_MODE": "cov",
            "UT_PROCESS": "coverage",
            "UT_TYPE": "ophost",
            "TARGET_BRANCH": "master",
            "GIT_TOKEN": "",
            "UT_SOFT_FAIL_REPOS": "",
            "LANGUAGE": "cpp",
            "PATH": self.bin.as_posix() + os.pathsep + os.environ["PATH"],
        }
        env.update(overrides or {})
        return subprocess.run(
            [BASH, self.script.as_posix()],
            cwd=self.root,
            env=env,
            text=True,
            capture_output=True,
            timeout=20,
        )

    def test_merged_scopes_take_precedence_over_last_build(self):
        (self.root / "ut_ophost_scopes.info").write_text(
            "merged builtin and experimental\n"
        )
        build = self.root / "build"
        build.mkdir()
        (build / "ops.info").write_text("last scope only\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(
            (self.root / "coverage_ophost.info").read_text(),
            "merged builtin and experimental\n",
        )

    def test_legacy_single_scope_coverage_is_still_collected(self):
        build = self.root / "build"
        build.mkdir()
        (build / "ops.info").write_text("legacy data\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(
            (self.root / "coverage_ophost.info").read_text(), "legacy data\n"
        )

    def test_missing_coverage_still_fails(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.root / "coverage_ophost.info").exists())

    def test_missing_native_coverage_cannot_be_soft_passed(self):
        result = self.run_script({"UT_SOFT_FAIL_REPOS": "true"})
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("command not found", result.stderr)
        self.assertFalse((self.root / "coverage_ophost.info").exists())


if __name__ == "__main__":
    unittest.main()
