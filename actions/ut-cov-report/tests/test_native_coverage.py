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
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "dist/ut_cov.sh"


@unittest.skipUnless(os.name == "posix", "Bash integration tests run on Linux")
class NativeCoverageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        git = self.bin / "git"
        git.write_text(
            '#!/bin/bash\nif [[ "$1" == remote ]]; then echo https://example.invalid/repo.git; fi\nexit 0\n'
        )
        git.chmod(0o755)

    def run_script(self):
        env = {
            **os.environ,
            "WORKSPACE": str(self.root),
            "COV_MODE": "cov",
            "UT_PROCESS": "coverage",
            "UT_TYPE": "ophost",
            "TARGET_BRANCH": "master",
            "GIT_TOKEN": "",
            "UT_SOFT_FAIL_REPOS": "",
            "LANGUAGE": "cpp",
            "PATH": str(self.bin) + os.pathsep + os.environ["PATH"],
        }
        return subprocess.run(
            ["bash", str(SCRIPT)],
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


if __name__ == "__main__":
    unittest.main()
