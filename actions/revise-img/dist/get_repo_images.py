#!/usr/bin/env python3
import sys
import yaml

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 get_repo_images.py <config.yaml> <repo_name>", file=sys.stderr)
        sys.exit(1)

    config_file = sys.argv[1]
    target_repo = sys.argv[2]

    with open(config_file, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    global_os_mirror = data.get('global', {}).get('os_mirror', {})
    gray_global_os_mirror = data.get('gray_global', {}).get('os_mirror', {})
    repos = data.get('repos', {})

    if target_repo not in repos:
        print(f"ERROR: Repository '{target_repo}' not found.", file=sys.stderr)
        sys.exit(1)

    repo_config = repos[target_repo]
    stages = repo_config.get('stages', {})
    repo_os_mirror = repo_config.get('os_mirror', {})

    results = []

    for stage_name, ref in stages.items():
        parts = ref.split(':')
        if len(parts) != 3:
            continue
        os_ver, arch, tag = parts

        # 查找顺序：repo → global → gray_global
        image = (
            repo_os_mirror.get(os_ver, {}).get(arch, {}).get(tag) or
            global_os_mirror.get(os_ver, {}).get(arch, {}).get(tag) or
            gray_global_os_mirror.get(os_ver, {}).get(arch, {}).get(tag)
        )

        if image is not None:
            results.append(f"{stage_name}:{image}")
        else:
            print(f"WARNING: No image for {target_repo}.{stage_name} ({ref})", file=sys.stderr)

    # 输出：每行一个 "stage:image"
    for line in results:
        print(line)

if __name__ == '__main__':
    main()
