import os
import subprocess
import sys
import re
import json


def write_task_json(warn_num, tool_name, commit_id, res_dir):
    data = {
        tool_name: warn_num,
        "commit_id": commit_id
    }
    static_file = f"{res_dir}/StaticCheck_{tool_name}.json"
    with open(static_file, "w", encoding="utf-8") as f:
        json.dump(data, f)
    if os.path.exists(static_file):
        print(f"[INFO] GEN {static_file} SUCC!!")



def gen_summary_file(print_summary_lst):
    summary_path = os.environ.get('ATOMGIT_STEP_SUMMARY')
    if summary_path:
        with open(summary_path, 'a') as f:
            f.write("\n".join(print_summary_lst))



def load_modified_files(pr_file):
    """
    返回修改文件.md列表
    """
    check_files = []
    with open(pr_file, 'r', encoding='utf-8') as f:
        files = [line.strip() for line in f if line.strip()]
        check_files = [f for f in files if  (f.lower().endswith('.md'))]
    return check_files

def any_diff_info(diff_output):
    # 正则表达式匹配 @@ 行
    hunk_re = re.compile(r'^@@ -(\d+),(\d+) \+(\d+),(\d+) @@')

    # 初始化行号列表
    added_lines = []
    deleted_lines = []

    # 当前块的起始行号
    old_start = 0
    new_start = 0

    # 逐行解析 diff 输出
    for line in diff_output.splitlines():
        if hunk_re.match(line):
            # 匹配到 @@ 行
            match = hunk_re.match(line)
            old_start = int(match.group(1))
            new_start = int(match.group(3))
        elif line.startswith('+') and not line.startswith('+++'):
            # 新增行
            #added_lines.append((new_start, new_start))
            added_lines.append(new_start)
            new_start += 1
        elif line.startswith('-') and not line.startswith('---'):
            # 删除行,必须存在
            #deleted_lines.append((old_start, old_start))
            deleted_lines.append(old_start)
            old_start += 1
        else:
            # 未修改行
            new_start += 1
            old_start += 1
    return added_lines

def get_git_diff_lines(repo_path, file_path, branch, md_output):
    '''
    获取文件在PR中修改的行内容
    返回修改的行列表
    模式：先从本地git diff 文件获取，获取不到，则从gitdiff.txt获取
    '''
    # 切换到仓库目录
    original_cwd = os.getcwd()
    if md_output:
        diff_output = md_output
    else:
        os.chdir(repo_path)
        # 本地diff
        cmd = ["git", "diff", f"origin/{branch}", file_path]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        print(cmd, 1111111111111111111111111, result.stdout)
        if result.returncode != 0:
            os.chdir(original_cwd)
            return []
        else:
            diff_output = result.stdout
    os.chdir(original_cwd)
    added_lines = any_diff_info(diff_output)
    return added_lines


def analyse_output(file_name,tool_name):
    '''
    分析output.md文件内容，将数据转换为字典和列表[{},{}]
    '''
    result = []
    style_pattern = re.compile(r'.*检查类型]：(.*?)<br>.*')
    file_path_pattern = re.compile(r'.*文件路径]：(.*?)<br>.*')
    line_num_pattern = re.compile(r'.*错误位置]：第 (.*?)行<br>.*')
    info_pattern = re.compile(r'.*错误信息]：(.*?)<br>.*')
    data_pattern = re.compile(r'.*错误内容]：(.*?)\|.*')
    with open(file_name, 'r', encoding="utf-8") as fr:
        lines = fr.readlines()
    for line in lines:
        #print(line)
        tmp_dic = {}
        if "文件路径" in line:
            # if "第 62" not in line:
            #     continue
            style_match = style_pattern.match(line)
            if not style_match: #过滤空
                continue
            if style_match.group(1) != tool_name.replace("_","-"): # 过滤工具,工具是-，不是_
                continue
            file_path_match = file_path_pattern.match(line)
            if file_path_match:
                file_path = file_path_match.group(1)
                if file_path.startswith("tmp/"):
                    file_path = file_path.replace("tmp/", "")
                tmp_dic["文件路径"] = file_path
            else:
                tmp_dic["文件路径"] = ""
            #
            line_num_match = line_num_pattern.match(line)
            if line_num_match:
                line_num = line_num_match.group(1)
                tmp_dic["错误位置"] = line_num
            else:
                tmp_dic["错误位置"] = ""
            #
            info_match = info_pattern.match(line)
            if info_match:
                info = info_match.group(1)
                tmp_dic["错误信息"] = info
            else:
                tmp_dic["错误信息"] = ""
            #
            data_match = data_pattern.match(line)
            if data_match:
                data = data_match.group(1)
                tmp_dic["错误内容"] = data
            else:
                tmp_dic["错误内容"] = ""
            tmp_dic["检查类型"] = style_match.group(1)
            result.append(tmp_dic)
    return result

def convert_to_ranges(lst):
    '''将行号列表转换为范围'''
    if not lst:
        return []

    result = []
    start = lst[0]
    end = lst[0]

    for i in range(1, len(lst)):
        if lst[i] == lst[i -1] + 1:
            end = lst[i]
        else:
            result.append({start,end})
            start = lst[i]
            end = lst[i]
    # 添加最后一个子序列
    result.append({start, end})
    return result

def is_number_in_ranges(number, ranges):
    '''判断任意数字在范围内'''
    for range_set in ranges:
        min_val = min(range_set)
        max_val = max(range_set)
        if min_val <= number <= max_val:
            return True
    return False