#!/usr/bin/env python
# -*- coding: utf-8 -*-
# pre-commit CI script
import os
import sys
import argparse
import logging
import json
import yaml
from CodeCheckerBase import CodeCheckerBaseClass

logging.basicConfig(level=logging.INFO,format="%(asctime)s - %(levelname)s %(message)s" )

class PreCommitChecker(CodeCheckerBaseClass):
    def __init__(self, repository_name, pr_id):
        self.repository_name = repository_name
        self.pr_id = pr_id

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
            "本地执行pre-commit可参考 https://gitcode.com/cann/infrastructure/tree/main/docs/SC/pre-commit/pre-commit配置指导书.md,谢谢!")

        # get changed files
        with open('pr_filelist_precommit.txt', 'r', encoding='utf-8') as f:
            file_lines = [line.strip() for line in f if line.strip()]

        if not file_lines:
            logging.info("✅ 没有需要检查的文件")
            return

        check_result = self.run_cmd(f"cat pr_filelist_precommit.txt | xargs pre-commit run --show-diff-on-failure --file", os.getcwd(), shell=True, capture_output=True)
        
        full_output = check_result.stdout
        normal_output = ""
        for line in full_output.splitlines(keepends=True):
            if line.startswith("All changes"):
                break
            normal_output += line

        logging.info(
            "------------------------------------4. pre-commit检测结果-----------------------------------")
        logging.info(normal_output)
        diff_log_path = "pre-commit.txt"
        with open(diff_log_path, "w", encoding="utf-8") as f:
            f.write(full_output)

        data = {"precommit_result": "pass" if check_result.returncode == 0 else "fail"}
        if check_result.returncode != 0:
            logging.info("❌ 存在部分文件格式错误")
        else:
            logging.info("✅ 所有文件格式检查通过！")

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

    def generate_pre_commit_config(self):
        # 1. 基础配置
        base_config = """repos:
  # pre-commit 基础检查
  - repo: https://gitcode.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
        exclude: ^\.pre-commit-config\.yaml$
      - id: end-of-file-fixer
        exclude: ^\.pre-commit-config\.yaml$
      - id: check-yaml
        args: ["--allow-multiple-documents"]
      - id: check-added-large-files
      - id: check-merge-conflict
      - id: detect-private-key
      - id: check-json
"""

        # 2. OAT 合规检查配置
#         oat_config = """
#   # OAT 合规性检查 (Open Source Audit Tool)
#   - repo: local
#     hooks:
#       - id: oat-check
#         name: OAT Compliance Check
#         entry: bash scripts/oat_check.sh
#         language: system
#         pass_filenames: true
#         types: [file]
#         stages: [commit]
#         verbose: true
# """

        # 最终内容
        final_content = base_config

        # 判断 scripts/oat_check.sh 是否存在
        # if os.path.exists("scripts/oat_check.sh"):
        #     final_content += oat_config
        #     logging.info("✅ 检测到 scripts/oat_check.sh，已自动追加 OAT 检查配置")

        # 覆写写入文件
        with open(".pre-commit-config.yaml", "w", encoding="utf-8") as f:
            f.write(final_content)

        logging.info("✅ .pre-commit-config.yaml 已生成完成！")
        # 忽略.pre-commit-config.yaml文件
        self.run_cmd("git add .pre-commit-config.yaml", os.getcwd(), shell=True)
        self.run_cmd("git checkout -- .pre-commit-config.yaml", os.getcwd(), shell=True)


def init_args():
    parser = argparse.ArgumentParser()

    parser.add_argument('--repository_name', help='repository_name', required=True, type=str)
    parser.add_argument('--pr_id', help='gitcode pr id', required=True, type=str)

    return parser.parse_args()


if __name__ == '__main__':
    args = init_args()

    precommit = PreCommitChecker(args.repository_name, args.pr_id)
    precommit.run()