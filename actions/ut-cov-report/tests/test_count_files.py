# Copyright (c) 2026 dhltat.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.
"""Regression tests for ops-nn job names versus ownership components."""

import importlib.util
from pathlib import Path
import tempfile
import unittest

import yaml


SOURCE = Path(__file__).resolve().parents[1] / "dist/ut/count_files.py"
SPEC = importlib.util.spec_from_file_location("count_files", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CountFilesTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.paths = [
            "index/example/op_kernel/kernel.cpp",
            "index/example/op_host/tiling.cpp",
            "index/example/op_api/api.cpp",
            "index/example/op_host/op_api/legacy_api.cpp",
            "index/example/op_graph/proto.cpp",
            "index/example/tests/ut/op_kernel/test_kernel.cpp",
            "common/src/framework/example_onnx_plugin.cpp",
            "experimental/index/new_op/op_kernel/kernel.cpp",
            "experimental/index/new_op/tests/ut/op_kernel/test_kernel.cpp",
        ]
        for name in self.paths:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
        self.rules = {
            "index@ops-nn": {
                "src": {
                    "release": {
                        "style": [
                            "ops/ops-nn/index/example/",
                            "ops/ops-nn/experimental/index/new_op/",
                        ],
                        "kernel_style": ["ops/ops-nn/common/src/framework/"],
                    },
                    "unrelease": {"test_code": ["ops/ops-nn/**/tests/"]},
                }
            },
        }

    def run_count(self, component):
        rule_file = self.root / "classify_rule.yaml"
        rule_file.write_text(yaml.safe_dump(self.rules), encoding="utf-8")
        MODULE.count_yaml(str(rule_file), component, str(self.root), str(self.root))
        lines = (
            (self.root / f"{component}_field.txt")
            .read_text(encoding="utf-8")
            .splitlines()
        )
        self.assertEqual(lines[0], f"[{component}]")
        return {name.replace("\\", "/") for name in lines[1:]}

    def test_kernel_alias_keeps_kernel_sources_and_excludes_tests(self):
        self.assertEqual(
            self.run_count("opkernel"),
            {
                "index/example/op_kernel/kernel.cpp",
                "experimental/index/new_op/op_kernel/kernel.cpp",
            },
        )

    def test_all_host_job_aliases(self):
        expected = {
            "opapi": {
                "index/example/op_api/api.cpp",
                "index/example/op_host/op_api/legacy_api.cpp",
            },
            "ophost": {
                "index/example/op_host/tiling.cpp",
                "common/src/framework/example_onnx_plugin.cpp",
            },
            "opgraph": {"index/example/op_graph/proto.cpp"},
        }
        for component, names in expected.items():
            with self.subTest(component=component):
                self.assertEqual(self.run_count(component), names)

    def test_repository_component_still_collects_all_source_modules(self):
        files = self.run_count("ops-nn")
        self.assertEqual(files, {name for name in self.paths if "/tests/" not in name})

    def test_unprefixed_and_windows_style_rule_paths(self):
        paths = self.rules["index@ops-nn"]["src"]["release"]["style"]
        paths[:] = ["index/example/", "ops\\ops-nn\\experimental\\index\\new_op/"]
        self.assertIn(
            "experimental/index/new_op/op_kernel/kernel.cpp", self.run_count("opkernel")
        )

    def test_unknown_component_is_not_silently_accepted(self):
        with self.assertRaises(KeyError):
            self.run_count("unknown")

    def test_explicit_job_rule_takes_precedence_over_alias(self):
        self.rules["opkernel"] = {
            "src": {"release": ["index/example/op_kernel/kernel.cpp"], "unrelease": []}
        }
        self.assertEqual(
            self.run_count("opkernel"), {"index/example/op_kernel/kernel.cpp"}
        )

    def test_non_ops_nn_schema_is_not_reinterpreted(self):
        self.rules = {"other@other": {"src": {"release": [], "unrelease": []}}}
        with self.assertRaises(KeyError):
            self.run_count("opkernel")

    def test_explicit_non_ops_nn_component_keeps_original_behavior(self):
        self.rules = {
            "other@other": {
                "src": {"release": ["index/example/op_kernel/"], "unrelease": []}
            }
        }
        self.assertEqual(
            self.run_count("other"), {"index/example/op_kernel/kernel.cpp"}
        )


if __name__ == "__main__":
    unittest.main()
