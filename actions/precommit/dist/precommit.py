#!/usr/bin/env python
# -*- coding: utf-8 -*-
# pre-commit CI script
import os
import sys
import argparse
import logging
import json
import yaml
from urllib.parse import unquote
from CodeCheckerBase import CodeCheckerBaseClass

logging.basicConfig(level=logging.INFO,format="%(asctime)s - %(levelname)s %(message)s" )

class PreCommitChecker(CodeCheckerBaseClass):
    def __init__(self, repository_name, pr_id, block=False):
        self.repository_name = repository_name
        self.pr_id = pr_id
        self.block = block
        self.env_dist = os.environ
        self.target_branch = self.env_dist.get("TARGET_BRANCH")
        self.org = self.env_dist.get("ATOMGIT_REPOSITORY_OWNER","cann")

    def run(self):
        logging.info("pre-commit begin!!!")

        # 1. check if pre-commit config exists
        logging.info(
            "------------------------------------1. 检查是否存在 .pre-commit-config.yaml-----------------------------------")
        if not os.path.exists('.pre-commit-config.yaml'):
            logging.info("✅ 未找到 .pre-commit-config.yaml，跳过代码检查，直接成功")
            sys.exit(0)
        logging.info("✅ 找到 pre-commit 配置文件，开始执行检查")
        self.modify_pre_commit_config()

        logging.info("📄 最终生成的 .pre-commit-config.yaml 内容如下：")
        logging.info("=" * 60)
        with open(".pre-commit-config.yaml", "r", encoding="utf-8") as f:
            logging.info(f.read())
        logging.info("=" * 60)

        # 2. install lintrunner
        logging.info("------------------------------------2. install lintrunner-----------------------------------")
        self.run_cmd('pip3 config set global.index-url https://mirrors.huaweicloud.com/repository/pypi/simple', os.getcwd(), shell=True)
        self.run_cmd('pip3 install --upgrade pip', os.getcwd(), shell=True)
        self.run_cmd('pip3 install -q pre-commit>=4.0.0', os.getcwd(), shell=True)

        # 3. pre-commit检测changes files
        logging.info(
            "------------------------------------3. pre-commit检测changes files-----------------------------------")
        logging.info(
            "本地执行pre-commit可参考 https://gitcode.com/cann/infrastructure/blob/main/docs/SC/pre-commit/pre-commit%E9%85%8D%E7%BD%AE%E6%8C%87%E5%AF%BC%E4%B9%A6.md#3-%E7%A4%BE%E5%8C%BA%E8%B4%A1%E7%8C%AE%E8%80%85%E4%BD%BF%E7%94%A8pre-commit%E8%83%BD%E5%8A%9B,谢谢!")

        # get changed files
        with open('pr_filelist_precommit.txt', 'r', encoding='utf-8') as f:
            file_lines = [line.strip() for line in f if line.strip()]

        if not file_lines:
            logging.info("✅ 没有需要检查的文件")
            return
        cmd = (
            "cat pr_filelist_precommit.txt "
            "| awk '$0 != \".pre-commit-config.yaml\"' "
            "| xargs pre-commit run --show-diff-on-failure --files"
        )
        check_result = self.run_cmd(cmd, os.getcwd(), shell=True, capture_output=True)

        full_output = unquote(check_result.stdout)
        normal_output = ""
        for line in full_output.splitlines(keepends=True):
            if line.startswith("All changes"):
                break
            normal_output += line

        logging.info(
            "------------------------------------4. pre-commit检测结果-----------------------------------")
        logging.info(normal_output)

        oat_context = ""
        oat_result = "oat_reports/result.txt"
        if os.path.exists(oat_result):
            with open(oat_result, "r", encoding="utf-8") as fr:
                oat_context = fr.read()
            logging.info(
                "------------------------------------5. pre-commit - OAT 检测结果-----------------------------------")
            logging.info(oat_context)

        diff_log_path = "pre-commit.txt"
        with open(diff_log_path, "w", encoding="utf-8") as f:
            f.write(full_output)

        with open(diff_log_path, "a", encoding="utf-8") as fa:
            fa.write(oat_context)

        # 写入步骤摘要到 ATOMGIT_STEP_SUMMARY
        summary_path = os.environ.get("ATOMGIT_STEP_SUMMARY", "")
        if summary_path:
            passed = check_result.returncode == 0
            status_icon = "✅" if passed else "❌"
            summary_lines = [
                f"## {status_icon} Pre-commit 检查结果\n",
                f"**状态**: {'通过' if passed else '失败'}\n",
                f"**参考链接**: [本地执行 pre-commit 指导](https://gitcode.com/cann/infrastructure/blob/main/docs/SC/pre-commit/pre-commit%E9%85%8D%E7%BD%AE%E6%8C%87%E5%AF%BC%E4%B9%A6.md#3-%E7%A4%BE%E5%8C%BA%E8%B4%A1%E7%8C%AE%E8%80%85%E4%BD%BF%E7%94%A8pre-commit%E8%83%BD%E5%8A%9B)\n",
            ]

            # 从 .pre-commit-config.yaml 读取 hook 列表，
            # 结合 pre-commit 日志输出（格式：hook_name...Passed/Failed/Skipped）生成摘要。
            # pre-commit 日志输出的是 hook 的 name（内置 hook 的 name 与 id 不同），
            # 因此以日志解析的结果为准，config 中定义了 name 的 local hook 用 config 的 name。
            import re
            hook_results = []

            # 从 config 收集所有 hook 的 id->name 映射（local hook 可能自定义 name）
            config_id_to_name = {}
            try:
                with open(".pre-commit-config.yaml", "r", encoding="utf-8") as f:
                    config_data = yaml.safe_load(f)
                if config_data and "repos" in config_data:
                    for repo_entry in config_data["repos"]:
                        for hook in repo_entry.get("hooks", []):
                            hook_id = hook.get("id", "")
                            hook_name = hook.get("name", hook_id)
                            if hook_id:
                                config_id_to_name[hook_id] = hook_name
            except Exception as e:
                logging.info(f"读取 .pre-commit-config.yaml 失败: {e}")

            # 从日志解析所有结果行
            for line in normal_output.splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                m = re.match(r'^(.+?)\.{2,}(?:\(.*?\))?(Passed|Failed|Skipped)\s*$', stripped)
                if not m:
                    continue
                hook_name = m.group(1).strip()
                status = m.group(2)
                if status == "Passed":
                    hook_results.append((hook_name, "✅ Passed"))
                elif status == "Failed":
                    hook_results.append((hook_name, "❌ Failed"))
                elif status == "Skipped":
                    hook_results.append((hook_name, "⏭️ Skipped"))

            # 提取失败 hook 的具体 diff 信息
            failed_diffs = {}
            if not passed:
                current_hook = None
                current_lines = []
                for line in full_output.splitlines():
                    stripped = line.strip()
                    m = re.match(r'^(.+?)\.{2,}(?:\(.*?\))?(Passed|Failed|Skipped)\s*$', stripped)
                    if m:
                        if current_hook is not None:
                            failed_diffs[current_hook] = "\n".join(current_lines)
                            current_hook = None
                            current_lines = []
                        if m.group(2) == "Failed":
                            current_hook = m.group(1).strip()
                        continue
                    if current_hook is not None:
                        current_lines.append(line)
                if current_hook is not None:
                    failed_diffs[current_hook] = "\n".join(current_lines)

            if hook_results:
                summary_lines.append("\n| 检查项 | 结果 |")
                summary_lines.append("|--------|------|")
                for hook_name, hook_status in hook_results:
                    summary_lines.append(f"| {hook_name} | {hook_status} |")

            if not passed:
                MAX_DETAIL_CHARS = 3000
                for hook_name, _ in hook_results:
                    if hook_name not in failed_diffs:
                        continue
                    raw = failed_diffs[hook_name].strip()
                    if not raw:
                        continue
                    if len(raw) > MAX_DETAIL_CHARS:
                        raw = raw[:MAX_DETAIL_CHARS] + "\n... (已截断，完整内容请查看 pre-commit.txt)"
                    summary_lines.append(f"\n<details>")
                    summary_lines.append(f"<summary>❌ {hook_name} 失败详情</summary>")
                    summary_lines.append("")
                    summary_lines.append("```")
                    summary_lines.append(raw)
                    summary_lines.append("```")
                    summary_lines.append("</details>")
                download_report_url = f"https://ascend-ci.obs.cn-north-4.myhuaweicloud.com/{self.org}/{self.repository_name}/ci/package/{self.pr_id}/pre-commit.txt"
                summary_lines.append(f"\n> ⚠️ 完整 diff 信息请查看日志或 <a href={download_report_url}> pre-commit.txt </a> 产物")
            with open(summary_path, "a", encoding="utf-8") as f:
                f.write("\n".join(summary_lines) + "\n")

        data = {"precommit_result": "pass" if check_result.returncode == 0 else "fail"}
        if os.path.exists("codecheck.json"):
            with open("codecheck.json", 'r', encoding='utf-8') as f:
                result=json.load(f)
                result.update(data)
            with open("codecheck.json", "w", encoding="utf-8") as f:
                json.dump(result, f)
        else:
            with open("codecheck.json", "w", encoding="utf-8") as f:
                json.dump(data, f)
        with open("codecheck.json", "r", encoding="utf-8") as f:
            result=json.load(f)
            print(f"write {result} success")

        if check_result.returncode != 0:
            logging.info("❌ 存在部分文件格式错误")
            if self.block:
                sys.exit(1)
        else:
            logging.info("✅ 所有文件格式检查通过！")


    def modify_pre_commit_config(self):
        # 替换映射
        replace_map = {
            "https://github.com/pre-commit/pre-commit-hooks":
                "https://gitcode.com/pre-commit/pre-commit-hooks",
            "https://github.com/pre-commit/mirrors-clang-format":
                "https://gitcode.com/pre-commit-clang/mirrors-clang-format",
        }

        def replace_repo_urls(config_data, replace_dict):
            count = 0
            for repo_entry in config_data.get("repos", []):
                current_repo = repo_entry.get("repo")
                if current_repo in replace_dict:
                    repo_entry["repo"] = replace_dict[current_repo]
                    count += 1
            return count

        # 直接删除整个 oat-check
        def remove_oat_check(config_data):
            modified = False
            repos = config_data.get("repos", [])
            new_repos = []

            for repo in repos:
                hooks = repo.get("hooks", [])
                # 过滤掉 id 为 oat-check 的 hook
                new_hooks = [h for h in hooks if h.get("id") != "oat-check"]

                if len(new_hooks) != len(hooks):
                    modified = True

                # 如果还有其他 hook 保留，没有就删掉整个 repo
                if new_hooks:
                    repo["hooks"] = new_hooks
                    new_repos.append(repo)

            config_data["repos"] = new_repos
            return modified

        # 读取 YAML
        with open(".pre-commit-config.yaml", "r", encoding="utf-8") as f:
            content = f.read()

        content = content.replace("\t", "  ")
        data = yaml.safe_load(content)

        # 执行仓库地址替换
        replaced_count = replace_repo_urls(data, replace_map)
        if replaced_count > 0:
            logging.info(f"✅ 替换完成！共替换 {replaced_count} 个仓库地址")
        else:
            logging.info("ℹ️ 没有需要替换的仓库地址")

        if self.target_branch != 'master' and self.target_branch != 'develop':
            # 直接删除 oat-check 配置
            oat_removed = remove_oat_check(data)
            if oat_removed:
                logging.info("✅ 已成功删除整个 oat-check 配置")
            else:
                logging.info("ℹ️ 未找到 oat-check，无需删除")

        # 写回文件
        with open(".pre-commit-config.yaml", "w", encoding="utf-8") as f:
            yaml.dump(
                data, f,
                sort_keys=False,
                default_flow_style=False,
                indent=2
            )

        # 忽略.pre-commit-config.yaml文件
        self.run_cmd("git add .pre-commit-config.yaml", os.getcwd(), shell=True)
        self.run_cmd("git checkout -- .pre-commit-config.yaml", os.getcwd(), shell=True)

def init_args():
    parser = argparse.ArgumentParser()

    parser.add_argument('--repository_name', help='repository_name', required=True, type=str)
    parser.add_argument('--pr_id', help='gitcode pr id', required=True, type=str)
    parser.add_argument('--block', type=lambda x: x.lower() in ("true", "1", "yes"),
                        default=False, help='为 true 时格式检查失败将中断流水线')

    return parser.parse_args()


if __name__ == '__main__':
    args = init_args()

    precommit = PreCommitChecker(args.repository_name, args.pr_id, args.block)
    precommit.run()