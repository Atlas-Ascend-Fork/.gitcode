import os
import sys
import yaml
import subprocess
import csv
import json
import logging
from datetime import datetime

current_dir = os.path.dirname(os.path.abspath(__file__))
print(f"Start to check: {current_dir}")
sys.path.append(os.path.dirname(current_dir))
import sc_public_module as git_diff

# 当前模块日志对象
logger = logging.getLogger(__name__)
# 拦截项
#LANJIE_TOOLS = ["StaticCheck_markdownlint", "StaticCheck_link_validity"]
LANJIE_TOOLS = ['StaticCheck_link_validity', 'StaticCheck_resource_existence', 'StaticCheck_tag_closed']
MAX_PRINT_NUM = 10
CHECK_TYPE_LST = ["StaticCheck_markdownlint", "StaticCheck_tag_closed", "StaticCheck_link_validity", "StaticCheck_resource_existence", "StaticCheck_codespell", "StaticCheck_compliance"]
CD = {
    "MD028": "一般",
    "MD005": "一般",
    "MD010": "一般",
    "MD022": "一般",
    "MD031": "一般",
    "MD039": "一般",
    "MD041": "一般",
    "MD058": "一般",
    "MD001": "严重",
    "MD011": "严重",
    "MD018": "严重",
    "MD023": "严重",
    "MD029": "严重",
    "MD037": "严重",
    "MD038": "严重",
    "MD042": "严重",
    "MD051": "严重",
    "MD052": "严重",
    "MD056": "严重",
    "MD002": "提示",
    "MD003": "提示",
    "MD006": "提示",
    "MD012": "提示",
    "MD019": "提示",
    "MD026": "提示",
    "MD035": "提示",
    "MD053": "提示",
    "MD054": "提示",
}


def run(code_dir, script_dir, targetOwnerRepo, targetBranch):
    # 开启扫描
    """
    * 工具网站： https://gitcode.com/openeuler/docs-website/tree/ci
    * 命令行参数说明：
    * --repoPath                     必需，文档仓库存储路径,最后不能带/
    * --targetOwnerRepo              必需，目标仓库信息，格式为 "owner/repo"
    * --targetBranch                 必需，目标分支名
    * --checkDirs="" \  ##可选，文档目录前缀，只有有该目录前缀的 md 文档才进行检查，多个用逗号分隔，默认为 'docs/zh,docs/en'
    * --checkAll                     可选，是否检查所有 .md 文件，默认为 false，只检查变更的 .md 文件，要检查所有请传递 true
    * v2 版本扫描前需要先修改ciconfig.json 配置文件
    """
    if code_dir.endswith("/"):
        code_dir = os.path.dirname(code_dir)  # 获取目录的父路径，也就是去掉末尾“/”
    cmd = [
        "node",
        f"{script_dir}/docs-ci-v2.js",
        f"--repoPath={code_dir}",
        "--checkAll=true",
        f"--targetOwnerRepo={targetOwnerRepo}",  # targetOwnerRepo 仓名，工具会用，不能乱写， 例子：cann/ops-nn
        f"--targetBranch={targetBranch}",
        "--detailUrl=Your Detail Url",
        "--outputCount=20000",  # targetBranch 目标分支名，工具会用，不能乱写
        f"--ciConfigUrl={script_dir}/.doctools/config.json",
    ]
    print("cmd:", cmd)
    start_time = datetime.now()
    output = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    end_time = datetime.now()
    elapsed_time = (end_time - start_time).total_seconds()
    print(f"running time: {elapsed_time}s")
    print(f"run {output.stderr}")

    if output.returncode != 0:
        print("ERROR", output)
        return False

    result_file = os.path.join(code_dir, "output.md")
    if os.path.exists(result_file):
        return True
    else:
        return False


def parse_file(file_path):
    """
    分析gitdiff.txt文件内容
    {
    '-------file1': 'text1',
    '-------file2': 'text2',
    }
    return: {}
    """
    result = {}
    current_key = None
    current_value = []
    with open(file_path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.rstrip()
            if line.startswith("------"):
                if current_key is not None:
                    result[current_key] = "\n".join(current_value)
                current_key = line.replace("------", "")
                current_value = []
            else:
                current_value.append(line)
    if current_key is not None:
        result[current_key] = "\n".join(current_value)
    return result


def output_to_result(code_dir, filter_lst, check_md_lst, branch, summary_info_dic):
    """对output.md文件，进行如下操作，然后输出result.md
    1. 变更文件列表过滤
    2. 工具过滤
    3. 行号过滤
    4. 屏蔽过滤
    # 非拦截和拦截都无告警，返回0
    # 有拦截告警返回 1
    # 无拦截告警，但有非拦截告警返回 99
    """
    MSG_FILE_PATH = "文件路径"
    MSG_ERR_POS = "错误位置"
    output_file = os.path.join(code_dir, "output.md")
    result_csv_file = os.path.join(code_dir, "StaticCheck.csv")
    # 解析output, #[{'文件路径': 'SECURITY.md', '错误位置': '62 ',
    #  '错误信息': 'MD047：文档末尾需要一个换行结束',
    # '错误内容': '', '检查类型': 'markdownlint'}]
    warning_lst = git_diff.analyse_output(output_file)
    #print("analyzed data: ", warning_lst)

    # 获取gitdiff.txt
    gitdiff_dic = {}
    gitdiff_file = os.path.join(code_dir, "gitdiff.txt")
    if os.path.exists(gitdiff_file) and os.path.getsize(gitdiff_file):
        gitdiff_dic = parse_file(gitdiff_file)

    # 变更文件行号
    tmp_dic = {}
    for check_md in check_md_lst:
        md_output = gitdiff_dic.get(check_md, "")  # 该文件git diff的内容
        line_lst = git_diff.get_git_diff_lines(code_dir, check_md, branch, md_output)
        tmp_dic[check_md] = git_diff.convert_to_ranges(line_lst)
    #print("change file lines:", tmp_dic)
    warn_lst = [
        x
        for x in warning_lst
        if not any(x[MSG_FILE_PATH].startswith(prefix) for prefix in filter_lst)
    ]
    result_lst = []
    for warn in warn_lst:
        if warn["检查类型"] == "MD编码格式检查":   # 特判。该工具不需要校验行号，直接当作告警
            result_lst.append(warn)
            continue
        for key, value in tmp_dic.items():  # value: [{1,3},{10},{54,66}]
            if warn[MSG_FILE_PATH] == key:  # key是变更文件名
                if git_diff.is_number_in_ranges(int(warn[MSG_ERR_POS]), value):
                    result_lst.append(warn)
                    break
    if not result_lst:  # 无告警，返回0
        return 0
    data_lst = [["检查类型", "严重程度", MSG_FILE_PATH, MSG_ERR_POS,"是否拦截",   "错误信息", "错误内容"]]
    lanjie_nums = 0
    no_lanjie_nums = 0
    for i in result_lst:
        #print("start: ", i)
        tmp_lst = []
        tool_name = i.get("检查类型", "无")
        tool_name_new = tool_name
        if "-" in tool_name:
            tool_name_new = "StaticCheck_" +  "_".join(tool_name.split("-"))
        if tool_name == "markdownlint" :
            tool_name_new = "StaticCheck_markdownlint"
        if tool_name == "MD编码格式检查":
            tool_name_new = "StaticCheck_compliance"
        tmp_lst.append(tool_name_new.replace("_check", ""))
        err_info = i.get("错误信息", "无")  # 获取规则，但不修改
        chendu = ""
        if "markdownlint" in tool_name:
            chendu = CD.get(err_info.split("：")[0], "")  # markdownlint程度
        else:
            chendu = i.get("严重程度", "无")
        tmp_lst.append(chendu)
        tmp_lst.append(i.get(MSG_FILE_PATH, "无"))
        tmp_lst.append(i.get(MSG_ERR_POS, "无"))
        if tool_name_new.replace("_check", "") in LANJIE_TOOLS:
            lanjie_is = "拦截"
            lanjie_nums += 1
        else:
            lanjie_is = ""
            no_lanjie_nums -= 1
        tmp_lst.append(lanjie_is)
        tmp_lst.append(err_info)
        tmp_lst.append(i.get("错误内容", "无"))
        print(tmp_lst)
        data_lst.append(tmp_lst)
        summary_info_dic[tool_name_new.replace("_check", "")].append(":".join([tmp_lst[2], tmp_lst[3], tmp_lst[5], tmp_lst[6].replace('```', '')]))
    with open(result_csv_file, "w", encoding="utf-8-sig", newline="") as fw:
        writer = csv.writer(fw)
        writer.writerows(data_lst)
    if lanjie_nums > 0:
        print("lanjie")
        return 1
    elif lanjie_nums == 0 and no_lanjie_nums < 0:
        print("no lanjie")
        return 99



def compliance(code_dir, script_dir, repo_name, check_md_lst):
    """芯片标签的合法性检查"""
    data_lst = []
    tag_check_js = os.path.join(script_dir, "js/tag_check.js")
    tag_check_result_json = os.path.join(code_dir, "tag_check_result.json")
    start_time = datetime.now()
    for mdfile in check_md_lst:
        if os.path.exists(tag_check_result_json):
            os.remove(tag_check_result_json)
        # node tag_checker.js <markdown文件/文件夹路径> <输出结果文件夹路径> <仓名>
        cmd = ["node", tag_check_js, os.path.join(code_dir, mdfile), code_dir, repo_name]
        subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if os.path.exists(tag_check_result_json):
            tmp_data = []
            with open(tag_check_result_json, "r", encoding="utf-8") as fr:
                tmp_data = json.load(fr)
            if not tmp_data:
                continue
            for info in tmp_data:
                localtion = info.get("location", "N/A")
                line_number = info.get("line_number", "N/A")
                rule_item = info.get("rule_item", "N/A")
                description = info.get("description", "N/A")
                snippet = info.get("snippet", "N/A")
                rule_level = info.get("rule_level", "N/A")
                mode_str = (
                    f"| 999 | [文件路径]：{localtion.replace(code_dir + '/', '')}<br>"
                    f"[错误位置]：第 {line_number} 行<br>"
                    f"[检查类型]：{rule_item}<br>"
                    f"[严重程度]：{rule_level}<br>"
                    f"[错误信息]：{description}<br>"
                    f"[错误内容]：{snippet}|"
                )
                data_lst.append(mode_str)
        else:
            print(f"compliance scan {mdfile} not resultfile")
            continue
    end_time = datetime.now()
    elapsed_time = (end_time - start_time).total_seconds()
    print(f"running compliance time: {elapsed_time}s")
    return data_lst


def md_utf8(check_md_lst):
    """芯片标签的合法性检查"""
    data_lst = []
    #tag_check_js = os.path.join(script_dir, "js/tag_check.js")
    #utf8_result_json = os.path.join(code_dir, "utf8_result.json")
    start_time = datetime.now()
    cmd = f"echo \"{' '.join(check_md_lst)}\" | xargs file -i"
    print("utf cmd:", cmd)
    cont = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8")
    #print("md_utf-8 output:", cont.stdout)
    if cont.returncode != 0:
        return data_lst
    for info in cont.stdout.split("\n"):
        if not info:
            continue
        file_name = info.split(":")[0].strip()  # 文件名
        geshi_info = info.split(":")[1].strip()  # 格式信息
        if geshi_info.endswith("utf-8"):
            continue
        mode_str = (
            f"| 888 | [文件路径]：{file_name}<br>"
            f"[错误位置]：第 0 行<br>"
            f"[检查类型]：MD编码格式检查<br>"
            f"[严重程度]：严重<br>"
            f"[错误信息]：请将文件编码转换为纯UTF-8（无BOM）格式<br>"
            f"[错误内容]：{geshi_info}|"
        )
        data_lst.append(mode_str)
    end_time = datetime.now()
    elapsed_time = (end_time - start_time).total_seconds()
    print(f"running utf-8 check time: {elapsed_time}s")
    return data_lst

if __name__ == "__main__":
    # tool_name = sys.argv[1]  # 工具名称
    """
    "link-validity-check",
    "resource-existence-check",
    "markdownlint",
    "tag-closed-check",
    "codespell-check"
    """
    code_dir = sys.argv[1]  # 代码所在一级目录
    profile = sys.argv[2]  # 变更列表文件
    script_dir = sys.argv[3]  # docs-ci目录
    branch = sys.argv[4]  # 分支 master
    repo_name = sys.argv[5]  # 仓名
    org = sys.argv[6]  # cann
    tool_name = sys.argv[7]
    if tool_name != 'md_check':
        print(f'[Waring] skip check {tool_name}')
        sys.exit(0)
    targetOwnerRepo = f"{org}/{repo_name}"
    # check_tool_name = tool_name.replace("_","-")  # 配置文件里的工具名称-链接
    with open(profile, "r", encoding="utf-8") as fr:
        lines = fr.readlines()
    profilelst = [line.strip() for line in lines]
    if not profilelst:
        sys.exit(0)  # 变更列表为空
    # md文件列表
    check_md_lst = git_diff.load_modified_files(profile)
    if not check_md_lst:
        sys.exit(0)  # 变更md列表为空
    print(f'check_md_lst account: ', {len(check_md_lst)})
    check_re_lst = []
    for md_info in check_md_lst:
        if '/' in md_info:
            check_re_lst.append(md_info.split('/')[-1])
    check_re_lst = list(set(check_re_lst))
    # 修改配置文件
    config_json = os.path.join(script_dir, ".doctools/config.json")
    with open(config_json, "r", encoding="utf-8") as fr:
        context = json.load(fr)
    context["config"]["base"][
        "docPath"
    ] = f"^({'|'.join([os.path.splitext(file)[0] for file in check_re_lst])}).md"
    context["config"]["base"][
        "markdownlintRemoteConfigUrl"
    ] = f"{script_dir}/.doctools/markdownlint.config.json"
    context["config"]["base"][
        "codespellCheckRemoteWhitelistUrl"
    ] = f"{script_dir}/.doctools/whitelist_words.txt"
    context["config"]["base"][
        "linkValidityCheckRemoteWhitelistUrl"
    ] = f"{script_dir}/.doctools/url.whitelist.json"
    context["config"]["base"][
        "resourceExistenceCheckRemoteWhitelistUrl"
    ] = f"{script_dir}/.doctools/url.whitelist.json"
    context["repo"] = {
        targetOwnerRepo: {
            "extendConfig": "base",
            "branches": {
                branch: {
                    "ci": [
                        "markdownlint",
                        # "codespell-check",
                        "link-validity-check",
                        "resource-existence-check",
                        "tag-closed-check",
                    ]
                }
            },
        }
    }

    #print("config.json:", context)
    with open(config_json, "w", encoding="utf-8") as fw:
        json.dump(context, fw, ensure_ascii=False)

    # run check
    status = run(code_dir, script_dir, targetOwnerRepo, branch)
    output_file = os.path.join(code_dir, "output.md")
    if not status:
        print("running ERROR status: False")
        sys.exit(0)  # 运行错误，返回0
    # cann\pipeline\bin\common\docs-ci/StaticCheck_filter.yaml
    filter_file = os.path.join(os.path.dirname(script_dir), "StaticCheck_filter.yaml")
    with open(filter_file) as file:
        filter_data = yaml.safe_load(file)
    filter_dic = filter_data.get(f"StaticCheck", {})
    if filter_dic:
        filter_lst = filter_dic.get(repo_name, [])
    else:
        filter_lst = []
    # compliance tag检测和utf-8检测，md文件
    compliance_lst = compliance(code_dir, script_dir, repo_name, check_md_lst)  # md标签检测
    no_utf8_lst = md_utf8(check_md_lst)  # utf-8检测
    #print("compliance_lst:", compliance_lst)
    #print("no_utf8_lst:", no_utf8_lst)
    # 追加到output.md
    output_file = os.path.join(code_dir, "output.md")
    if compliance_lst:
        with open(output_file, "a", encoding="utf-8") as fa:
            for item in compliance_lst:
                fa.write("\n" + item )
    if no_utf8_lst:
        with open(output_file, "a", encoding="utf-8") as fa:
            for item in no_utf8_lst:
                fa.write("\n" + item )
    # output.md生成最终的结果文件result.csv
    summary_info_dic = {}
    mr_intercept_dic = {}
    for check_type in CHECK_TYPE_LST:
        summary_info_dic.setdefault(check_type, [])
        mr_intercept_dic.setdefault(check_type, {
            "intercept_status": "Passed",
            "summary_detail_lst": []
        })
    result_num = output_to_result(code_dir, filter_lst, check_md_lst, branch, summary_info_dic)
    git_diff.write_task_json(result_num, tool_name, code_dir)
    # 生成summary文件
    passed = result_num != 1
    status_icon = "✅" if passed else "❌"
    summary_lines = [
        f"## {status_icon} MD-CHECK 检查结果\n",
        f"**状态**: {'通过' if passed else '失败'}\n",
    ]
    summary_lines.append("\n| 检查项 | 结果 |")
    summary_lines.append("|--------|------|")
    for check_tool, check_info in summary_info_dic.items():
        if check_info:
            if check_tool in LANJIE_TOOLS:
                hook_status = "❌ Failed"
                intercept_status = 'Failed'
            else:
                hook_status = "⏭️ Waring"
                intercept_status = 'Waring'
            mr_intercept_dic[check_tool]['intercept_status'] = intercept_status
            mr_intercept_dic[check_tool]['summary_detail_lst'].extend(check_info)
        else:
            hook_status = "✅ Passed"
        summary_lines.append(f"| {check_tool} | {hook_status} |")
    for check_tool, check_info in mr_intercept_dic.items():
        if check_info['intercept_status'] == "Passed":
            continue
        if check_info['intercept_status'] == "Failed":
            check_status = "❌"
        if check_info['intercept_status'] == "Waring":
            check_status = "⏭️"
        if len(check_info["summary_detail_lst"]) > MAX_PRINT_NUM:
            raw = check_info["summary_detail_lst"][:MAX_PRINT_NUM]
            raw.append(f'...(该检查项告警数量超过{MAX_PRINT_NUM},已截断，完整内容请查看日志或 StaticCheck.csv)')
        else:
            raw = check_info["summary_detail_lst"]
        summary_lines.append(f"\n<details>")
        summary_lines.append(f"<summary> {check_status} {check_tool} 失败详情</summary>")
        summary_lines.append("")
        summary_lines.append("```")
        summary_lines.append("\n".join(raw))
        summary_lines.append("```")
        summary_lines.append("</details>")
    summary_lines.append('⚠️ 详细告警信息请查看日志或 StaticCheck.csv 产物')
    git_diff.gen_summary_file(summary_lines)
    sys.exit(result_num)  # 输出告警个数
