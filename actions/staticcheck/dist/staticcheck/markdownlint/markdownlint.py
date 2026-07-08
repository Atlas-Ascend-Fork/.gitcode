import os
import yaml
import sys
import re
import csv
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(current_dir))
import sc_public_module as git_diff

CD = {
    "MD028": "一般","MD005": "一般","MD010": "一般","MD022": "一般","MD031": "一般","MD039": "一般","MD041": "一般","MD058": "一般",
    "MD001": "严重","MD011": "严重","MD018": "严重","MD023": "严重","MD029": "严重","MD037": "严重","MD038": "严重","MD042": "严重","MD051": "严重","MD052": "严重","MD056": "严重",
    "MD002": "提示","MD003": "提示","MD006": "提示","MD019": "提示","MD026": "提示","MD035": "提示","MD053": "提示","MD054": "提示"
}

def read_yaml(files):
    with open(files) as file:
        data = yaml.load(file, Loader=yaml.FullLoader)
        return data

def parse_file(file_path):
    '''
    分析gitdiff.txt文件内容
    {
    '-------file1': 'text1',
    '-------file2': 'text2',
    }
    return: {}
    '''
    result = {}
    current_key = None
    current_value = []
    with open(file_path, 'r', encoding='utf-8') as file:
        for line in file:
            line = line.rstrip()
            if line.startswith('------'):
                if current_key is not None:
                    result[current_key] = '\n'.join(current_value)
                current_key = line.replace("------", "")
                current_value = []
            else:
                current_value.append(line)
    if current_key is not None:
        result[current_key] = '\n'.join(current_value)
    return result

if __name__ == "__main__":
    workspace = sys.argv[1]
    tool_dir = sys.argv[2]
    branch = sys.argv[3]
    pr_filelist_file = sys.argv[4]
    repo_name = sys.argv[5]  # 仓名 例如 ops-nn
    tool_name = sys.argv[6]
    commit_id = sys.argv[7]
    print_summary_lst = []
    # 获取工具-仓-屏蔽数据
    filter_file = os.path.join(os.path.dirname(tool_dir), "StaticCheck_filter.yaml")
    ss = read_yaml(filter_file)
    filter_dic = ss.get(f"StaticCheck_{tool_name}", {})
    if filter_dic:
        filter_lst = filter_dic.get(repo_name, [])
    else:
        filter_lst = []
    print("markdownlint filter:", filter_lst)
    # 获取修改行号
    with open(pr_filelist_file, "r") as fr:
        pr_filelist = fr.readlines()
        pr_filelist = [i.strip() for i in pr_filelist if i.strip().endswith(".md")]  # 去掉换行符,筛.md结尾的

    # 获取gitdiff.txt
    gitdiff_dic = {}
    gitdiff_file = os.path.join(workspace, "gitdiff.txt")
    if os.path.exists(gitdiff_file) and os.path.getsize(gitdiff_file):
        gitdiff_dic = parse_file(gitdiff_file)
        print(f"[INFO] GET DIFF FILE SUCC! {gitdiff_file}")
    else:
        print(f"[WARING] GET DIFF FILE FAILED! {gitdiff_file}")

    changefile_dic = {}
    for check_md in pr_filelist:
        md_output = gitdiff_dic.get(check_md, "") # 该文件git diff的内容
        line_lst = git_diff.get_git_diff_lines(workspace, check_md, branch, md_output)
        changefile_dic[check_md] = git_diff.convert_to_ranges(line_lst)
    print("changefile_dic:", changefile_dic)    #{"文件1": [{1,3},{10},{54,66}], "文件2": []}
    # 获取result结果文件
    markdownlint_result_file = os.path.join(workspace, "markdown_result.txt")
    with open(markdownlint_result_file, "r") as fr:
        warning_lst = fr.readlines()
    # 过滤黑名单和行号，输出结果
    hei_lst = [x for x in warning_lst if not any(x.startswith(prefix) for prefix in filter_lst)]
    pattern = r'^(?P<file_name>.*):(?P<line_number>\d+).*'
    result_lst = []
    for warn in hei_lst:
        if not warn or ".md:" not in warn:
            continue
        match = re.match(pattern, warn)
        if match:
            file_name = match.group("file_name")
            line_number = match.group("line_number")
        else:
            print("re ERROR:",warn)
            continue
        for key, value in changefile_dic.items():
            if file_name == key: #key是变更文件名
                if git_diff.is_number_in_ranges(int(line_number), value):
                    result_lst.append(warn)
                    break

    data_lst = [["文件路径","行号","列","规则","程度","内容",r"参考https://github.com/markdownlint/markdownlint/blob/main/docs/RULES.md"]]
    # docs/QUICKSTART.md:40 MD031/blanks-around-fences Fenced code blocks should be surrounded by blank lines [Context: "```bash"]
    pattern = r'^(?P<file_path>[\w./-]+):(?P<line_number>\d+)(:(?P<column_number>\d+))? (?P<rule_id>.*)/(?P<content>.*)$'
    for i in result_lst:
        tmp_lst = []
        if not i:
            continue
        match = re.match(pattern, i)
        if match:
            file_path = match.group("file_path")
            line_number = match.group("line_number")
            column_number = match.group("column_number") or "N/A"
            rule_id = match.group("rule_id")
            chengdu = CD.get(rule_id, "N/A")
            content = match.group("content")
            data_lst.append([file_path, line_number, column_number, rule_id, chengdu, content])
        else:
            continue
    result_csv_file = os.path.join(workspace, "markdownlint.csv")
    with open(result_csv_file, "w", encoding="utf-8-sig", newline="") as fw:
        writer = csv.writer(fw)
        writer.writerows(data_lst)
    if os.path.exists(result_csv_file):
        print(f"[INFO] Gen {result_csv_file} SUCC!!!")
    result_file = os.path.join(workspace, "markdownlint.md")
    with open(result_file, "w") as fw:
        fw.write("".join(result_lst))
    print_summary_lst.append(f"###\t{tool_name}\t###\n")
    for ret_info in result_lst:
        print_summary_lst.append(ret_info)
    git_diff.gen_summary_file(print_summary_lst)
    print("\n".join(print_summary_lst))
    git_diff.write_task_json(len(result_lst), tool_name, commit_id, workspace)




