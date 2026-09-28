# -*- coding: utf-8 -*-
"""检查 PR 中的修改文件是否缺少对应的中英文双语版本"""
from __future__ import annotations
import logging
import sys
from pathlib import Path

import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(message)s",
    stream=sys.stderr, 
)
logger = logging.getLogger(__name__)

ALL_ENGLISH_SKIP_EXCLUDED_REPOS = {"pypto"}


def is_english_md(file_path: str) -> bool:
    """英文文档判定：路径含 en 目录段（en/*.md），或文件名以 _en.md 结尾"""
    parts = file_path.replace("\\", "/").split("/")
    if "en" in parts[:-1]:
        return True
    return file_path.endswith("_en.md")


def read_pr_file(pr_file: str) -> list[str]:
    """读取 PR 文件列表（git diff --name-status 格式），仅保留 .md 文件"""
    p = Path(pr_file)
    if not p.is_file():
        logger.error("PR 文件不存在: %s", pr_file)
        return []

    md_list = []
    with open(p, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line[0] not in ("A", "M", "U", "C", "R"):
                continue
            parts = line.split("\t")
            if line.startswith("D"):
                continue
            elif line.startswith("R"):
                if len(parts) >= 3:
                    file_path = parts[2].strip()
                else:
                    continue
            else:
                if len(parts) >= 2:
                    file_path = parts[1].strip()
                else:
                    continue
            if file_path.endswith(".md"):
                md_list.append(file_path)

    logger.info("从 PR 文件中读取到 %d 个 .md 文件", len(md_list))
    return md_list


def _pick_branch(cfg, branch: str) -> list[str]:
    """按分支提取屏蔽路径：配置了具体分支（非 master）时仅取该分支名单；
    分支未配置或传入 master 时回退到 '*'；list 视为旧格式（全分支生效）"""
    if isinstance(cfg, dict):
        if branch != "master" and branch in cfg:
            return list(cfg[branch])
        return list(cfg.get("*", []))
    if isinstance(cfg, list):
        return list(cfg)
    return []


def read_yaml(md_yaml: str, repo: str, branch: str) -> list[str]:
    """读取 YAML 配置，合并 common 和指定 repo+branch 的屏蔽路径"""
    p = Path(md_yaml)
    if not p.is_file():
        logger.error("YAML 配置不存在: %s", md_yaml)
        return []

    with open(p, "r", encoding="utf-8") as f:
        content = yaml.safe_load(f) or {}

    common_paths = _pick_branch(content.get("common"), branch)
    repo_paths = _pick_branch(content.get(repo), branch)
    all_paths = common_paths + repo_paths

    logger.info("加载屏蔽路径 %d 条 (common=%d, %s@%s=%d)",
                len(all_paths),
                len(common_paths),
                repo,
                branch,
                len(repo_paths))
    return all_paths


def is_in_paths(file_path: str, ref_paths: list[str], workspace: Path) -> bool:
    """判断 file_path 是否在 ref_paths 中某个路径下（含自身）"""
    p = (workspace / file_path).resolve()
    for ref in ref_paths:
        r = (workspace / ref).resolve()
        if p == r or r in p.parents:
            return True
    return False


def _get_pair_path(original: Path) -> Path | None:
    """根据原始路径生成对应的双语配对路径"""
    parts = list(original.parts)

    # 1. 目录级双语：zh/ ↔ en/
    if "zh" in parts:
        new_parts = ["en" if part == "zh" else part for part in parts]
        return Path(*new_parts)
    if "en" in parts:
        new_parts = ["zh" if part == "en" else part for part in parts]
        return Path(*new_parts)

    # 2. 文件名后缀级双语：xxx.md ↔ xxx_en.md
    stem = original.stem
    suffix = original.suffix  # e.g., ".md"

    if stem.endswith("_en"):
        # xxx_en.md → xxx.md
        return original.with_stem(stem[:-3])  # 去掉 "_en"
    elif stem.endswith("_zh"):
        # xxx_zh.md → xxx.md (如果你们也有 _zh 后缀的约定)
        return original.with_stem(stem[:-3])
    else:
        # xxx.md → xxx_en.md
        return original.with_stem(f"{stem}_en")


def check_md_files(
    mdlist: list[str],
    repo_md: list[str],
    workspace: Path,
    skip_english: bool = False,
) -> list[str]:
    """检查 MD 文件的双语配对完整性，返回缺失配对的文件列表"""
    illegal: list[str] = []
    skipped_english = 0

    md_set = set(mdlist)
    for md in mdlist:
        if skip_english and is_english_md(md):
            skipped_english += 1
            logger.debug("英文文档，跳过检测: %s", md)
            continue

        if is_in_paths(md, repo_md, workspace):
            logger.debug("白名单跳过: %s", md)
            continue

        full_path = workspace / md
        try:
            pair_full_path = _get_pair_path(full_path)
        except Exception as e:
            logger.error("生成配对路径时发生异常: %s | 错误: %s", md, e)
            continue

        if pair_full_path is None:
            logger.warning("无法生成配对路径: %s", md)
            continue

        try:
            pair_rel_str = str(pair_full_path.relative_to(workspace)).replace("\\", "/")
        except ValueError:
            logger.warning("配对路径超出工作区范围: %s", pair_full_path)
            continue

        logger.info("%s 对应的另一版本为 %s", md, pair_rel_str)

        if pair_rel_str not in md_set:
            logger.error("%s 被修改了，但 %s 未在本次 PR 中同步修改", md, pair_rel_str)
            illegal.append(md)

        if not pair_full_path.is_file():
            logger.warning("缺少双语配对文件: %s → %s", md, pair_rel_str)
            if md not in illegal:  # 避免重复添加
                illegal.append(md)
        else:
            logger.debug("配对检查通过: %s", md)

    if skipped_english:
        logger.info("按策略跳过 %d 个英文文档（en/ 或 *_en.md）", skipped_english)
    return illegal


def main(repo: str, branch: str, md_yaml: str, pr_file: str, workspace: str) -> int:
    """主入口函数，返回退出码"""
    ws = Path(workspace)
    if not ws.is_dir():
        logger.error("WORKSPACE 目录不存在: %s", workspace)
        return 1

    md_list = read_pr_file(pr_file)
    if not md_list:
        logger.info("PR 中没有 .md 文件，跳过检查")
        return 0

    # 英文文档逐个跳过检测（pypto 例外：其英文文档同样要求与中文同步）
    skip_english = repo not in ALL_ENGLISH_SKIP_EXCLUDED_REPOS

    repo_md_paths = read_yaml(md_yaml, repo, branch)

    illegal_list = check_md_files(md_list, repo_md_paths, ws, skip_english)

    if illegal_list:
        logger.error("双语配对修改检查失败，共 %d 个文件缺失对应版本", len(illegal_list))
        return 1

    logger.info("✅ 所有 %d 个 MD 文件双语配对检查通过", len(md_list))
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 6:
        logger.error("Usage: %s <repo> <branch> <md_yaml> <pr_file> <workspace>", sys.argv[0])
        sys.exit(2)

    sys.exit(main(*sys.argv[1:]))