import os
import sys
import yaml
import subprocess
import csv
from datetime import datetime
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(current_dir))
import sc_public_module as git_diff



def get_check_paths(profilelst, tool_name):
    # 变更文件列表
    path_lst = []
    # 通过变更文件得到变更目录列表
    for profile in profilelst:
        if "link_validity_check" == tool_name:
            path_lst.append(profile)
        else:
            # 如果是1级文件，则拷贝到tmp目录进行扫描，展示结果时去掉tmp,不能改变结构否则有wubao
            if not os.path.dirname(profile):
                # target_file = os.path.join(tmp_path, os.path.basename(profile))
                # shutil.copy2(profile, target_file)
                path_lst.append(profile)
            else:
                path_lst.append(os.path.dirname(profile))
    return list(set(path_lst))

def run(code_dir, paths_lst, remotec_ci_config_name, script_dir):
    # 开启扫描
    '''
    * 工具网站： https://gitcode.com/openeuler/docs-website/tree/ci
    * 命令行参数说明：
    * --repoPath                     必需，文档仓库存储路径,最后不能带/
    * --targetOwnerRepo              必需，目标仓库信息，格式为 "owner/repo"
    * --targetBranch                 必需，目标分支名
    * --checkDirs="" \  ##可选，文档目录前缀，只有有该目录前缀的 md 文档才进行检查，多个用逗号分隔，默认为 'docs/zh,docs/en'
    * --checkAll                     可选，是否检查所有 .md 文件，默认为 false，只检查变更的 .md 文件，要检查所有请传递 true
    '''
    if code_dir.endswith("/"):
        code_dir = os.path.dirname(code_dir) # 获取目录的父路径，也就是去掉末尾“/”
    paths = ",".join(paths_lst)
    #paths = "QUICKSTART.md"  # 测试全仓time
    cmd = ['node', f'{script_dir}/docs-ci.js', f'--repoPath={code_dir}', 
           f'--checkDirs={paths}', '--checkAll=true', f'--targetOwnerRepo={remotec_ci_config_name}',
             '-targetBranch=master', '--detailUrl=Your Detail Url', '--outputCount=20000',
               f'--remoteCiConfigUrl={script_dir}/repo_ci.json',
                 f'--remoteCodespellConfigUrl={script_dir}/whitelist_words.txt',
                   f'--remoteWhiteListUrlsConfigUrl={script_dir}/whitelist_urls.txt']
    print("cmd:", cmd)
    start_time = datetime.now()
    output = subprocess.run(cmd,  capture_output=True, text=True, encoding="utf-8")
    end_time = datetime.now()
    elapsed_time = (end_time -start_time).total_seconds()
    print(f"running time: {elapsed_time}s")
    print(f"run {output.stderr}")
    # print(1111111111111111111111111, output.stdout)
    if output.returncode != 0:
        print("ERROR",  output)
        return False

    result_file = os.path.join(code_dir, "output.md")
    if os.path.exists(result_file):
        #print("success output.md ", output.encode("utf-8").decode("utf-8"))
        return True
    else:
        #print("error output.md not found ", output.encode("utf-8").decode("utf-8"))
        return False

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


def get_change_file_dic(code_dir, branch, check_md_lst):
    # 获取gitdiff.txt
    gitdiff_dic = {}
    gitdiff_file = os.path.join(code_dir, "gitdiff.txt")
    if os.path.exists(gitdiff_file) and os.path.getsize(gitdiff_file):
       gitdiff_dic = parse_file(gitdiff_file)
    # 变更文件行号
    change_file_dic = {}
    for check_md in check_md_lst:
        md_output = gitdiff_dic.get(check_md, "") # 该文件git diff的内容
        line_lst = git_diff.get_git_diff_lines(code_dir, check_md, branch, md_output)
        change_file_dic[check_md] = git_diff.convert_to_ranges(line_lst)
    print("change_file_dic:", change_file_dic)  
    return change_file_dic


def output_to_result(code_dir, filter_lst, tool_name, change_file_dic):
    '''对output.md文件，进行如下操作，然后输出result.md
    1. 变更文件列表过滤
    2. 工具过滤
    3. 行号过滤
    4. 屏蔽过滤
    '''
    output_file= os.path.join(code_dir, "output.md")
    result_csv_file= os.path.join(code_dir, f"{tool_name}.csv")
    # 解析output, #[{'文件路径': 'SECURITY.md', '错误位置': '62 ',
    #  '错误信息': 'MD047：文档末尾需要一个换行结束',
    # '错误内容': '', '检查类型': 'markdownlint'}]
    warning_lst = git_diff.analyse_output(output_file, tool_name)

    warn_lst = [x for x in warning_lst if not any(x["文件路径"].startswith(prefix) for prefix in filter_lst)]
    result_lst = []
    for warn in warn_lst:
        for key, value in change_file_dic.items():  # value: [{1,3},{10},{54,66}]
            if warn["文件路径"] == key: #key是变更文件名
                if git_diff.is_number_in_ranges(int(warn["错误位置"]), value):
                    result_lst.append(warn)
                    break
    if not len(result_lst): # 无告警，返回0
        return 0
    data_lst = [["文件路径","错误位置","检查类型","错误信息","错误内容"]]
    print('*'*20)
    for i in result_lst:
        tmp_lst = []
        tmp_lst.append(i.get("文件路径", "无"))
        tmp_lst.append(i.get("错误位置", "无"))
        tmp_lst.append(i.get("检查类型", "无"))
        tmp_lst.append(i.get("错误信息", "无"))
        tmp_lst.append(i.get("错误内容", "无"))
        data_lst.append(tmp_lst)
        print(tmp_lst)
    print('*'*20)
    with open(result_csv_file, "w", encoding="utf-8-sig", newline="") as fw:
        writer = csv.writer(fw)
        writer.writerows(data_lst)
    return len(result_lst)


if __name__ == "__main__":
    tool_name = sys.argv[1]  # 工具名称
    code_dir = sys.argv[2]  # 代码所在一级目录
    profile = sys.argv[3] # 变更列表文件
    script_dir = sys.argv[4] # docs-ci目录
    branch = sys.argv[5] # 分支
    repo_name = sys.argv[6] # 分支
    commit_id = sys.argv[7]
    with open(profile, 'r', encoding="utf-8") as fr:
        lines = fr.readlines()
    profilelst = [line.strip() for line in lines]
    if not len(profilelst):
        sys.exit(0)   # 变更列表为空
    # 不同的工具使用的repo_ci配置文件不一样
    remotec_ci_config_name = ""
    if tool_name in ["link_validity_check", "codespell_check", "resource_existence_check", "tag_closed_check"]:
        remotec_ci_config_name = tool_name
    # if tool_name == "link_validity_check":
    #     remoteCiConfigUrl = f"{script_dir}/link-validity-check_repo_ci.json"
    # elif tool_name == "codespell_check":
    #     remoteCiConfigUrl = f"{script_dir}/codespell-check_repo_ci.json"
    # elif tool_name == "resource_existence_check":
    #     remoteCiConfigUrl = f"{script_dir}/resource-existence-check_repo_ci.json"
    # elif tool_name == "tag_closed_check":
    #     remoteCiConfigUrl = f"{script_dir}/tag-closed-check_repo_ci.json"
    # paths_lst = get_check_paths(profilelst, tool_name)
    # md文件列表
    check_md_lst = git_diff.load_modified_files(profile)
    if not len(check_md_lst):
        sys.exit(0)   # 变更md列表为空
    change_file_dic = get_change_file_dic(code_dir, branch, check_md_lst)
    status = run(code_dir, check_md_lst, remotec_ci_config_name, script_dir)
    output_file= os.path.join(code_dir, "output.md")
    if not status:
        print("running ERROR status: False")
        sys.exit(0)  # 运行错误，返回0
    # cann\pipeline\bin\common\StaticCheck_filter.yaml
    filter_file = os.path.join(os.path.dirname(script_dir), "StaticCheck_filter.yaml")
    with open(filter_file) as file:
        data = yaml.load(file, Loader=yaml.FullLoader)
    filter_dic = data.get(f"StaticCheck_{tool_name}", {})
    if filter_dic:
        filter_lst = filter_dic.get(repo_name, [])
    else:
        filter_lst = []

    print(f"{tool_name} filter:", filter_lst)
    # output.md生成最终的结果文件result.csv
    result_num = output_to_result(code_dir, filter_lst, tool_name, change_file_dic)
    git_diff.write_task_json(result_num, tool_name, commit_id, code_dir)
    sys.exit(result_num)  # 输出告警个数

