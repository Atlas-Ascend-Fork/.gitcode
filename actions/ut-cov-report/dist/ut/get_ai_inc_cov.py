#!/usr/bin/python
# -*- coding: utf-8 -*-
"""生成增量覆盖率"""

import os
import re
import shutil
import sys
import ci_log as CI_LOG
import create_change_xml as change_xml
import get_classify_rule_content as get_classify_rule

THIS_FILE_NAME = __file__
THIS_FILE_PATH = os.path.dirname(os.path.realpath(THIS_FILE_NAME))
sys.path.append(os.path.join(THIS_FILE_PATH, ".."))

DIFF_FILE_PREFIX = "diff_file@"
INFO_FILE = "add_ut.info"
# 定义异常指示值
NO_NEED_TOCOVER = 2
GENERATE_DIFF_SUCC = 0
GENERATE_DIFF_FAIL = 0
AP_COMPONENT_LIST = [
    "camera",
    "app",
    "perf",
    "audio",
    "audiohal",
    "vedio",
    "ai",
    "display",
]

# key
PARA_KEY_RC = "rc_config"
PARA_KEY_PROJECT = "project"
PARA_KEY_BRANCH = "master"
PARA_KEY_BLACKLIST = "blacklist"
PARA_KEY_INFO = "info_path"
PARA_KEY_CLASSIFY = "classify_rule_name"
PARA_KEY_CHANGEFILE = "change_file"
PARA_KEY_THRESHOLD = "threshold"
PARA_KEY_TEST_TYPE = "test_type"

def get_lcov_file_from_info(info_path, work_dir, classify_name):
    """
    功能描述：从info文件中解析出做覆盖率的源码文件
    参数：1.info_path：全量info文件
    返回值：保存覆盖率文件的列表
    异常描述：
    """
    lcov_file_list = []
    if not os.path.isfile(info_path):
        CI_LOG.cilog_error(
            THIS_FILE_NAME, "info_path: %s is not exist", info_path)
        return lcov_file_list
    with open(info_path, "r", encoding="UTF-8") as info_file:
        for each_line in info_file.readlines():
            if each_line.startswith("SF:"):
                # if classify_name in ["graphengine", "fe", "aicpu", "ffts", "dvpp", "ge_executor_c"]:
                #     classify_name = "air"
                # if classify_name in ["acl_c"]:
                #     classify_name = "acl"
                op_path = re.search(
                    "SF:" + work_dir + "/" + classify_name + "/", each_line
                )
                if op_path is not None:
                    # 针对特殊路径进行匹配、过滤处理
                    lcov_file_list.append(
                        each_line.replace(op_path.group(0), "").strip()
                    )
    lcov_file_list.sort()
    CI_LOG.cilog_info(
        THIS_FILE_NAME, "covered file list is %s", lcov_file_list)
    return lcov_file_list


def exit_code(rc_config):
    """
    功能描述：根据任务是否做判据，返回不同指示值
    参数：1.RC_config：任务是否做判据，false表示不作 2:code_value：返回值
    返回值：
    异常描述：
    """
    if rc_config == "false":
        sys.exit(0)
    else:
        sys.exit(-1)


def merge_info(info_path, out_path):
    """
    功能描述：合并info文件
    参数：1.info_path:存放各个info文件的地址 2.out_path：总info路径
    返回值：
    异常描述
    """
    CI_LOG.cilog_info(THIS_FILE_NAME, "info_path is %s", info_path)
    add_info_file_str_list = []
    for root, info_dirs, files in os.walk(info_path):
        for f in files:
            if f.endswith(".info"):
                if os.path.getsize(os.path.join(root, f)) == 0:
                    continue
                add_info_file_str_list.append("-a " + os.path.join(root, f))
    if len(add_info_file_str_list) == 0:
        CI_LOG.cilog_info(THIS_FILE_NAME, "code not change. exit")
        sys.exit(0)

    # 分布汇总所有info文件，生成temp0.info/temp1.info/temp2.info
    step = 100
    temp_info_str_list = []
    out_path_dir = os.path.dirname(out_path)
    add_info_file_count = len(add_info_file_str_list)
    for i in range(0, add_info_file_count, step):
        add_info_file_temp_list = list(add_info_file_str_list[i: i + step - 1])
        merge_temp_file_str = " ".join(add_info_file_temp_list)
        temp_info_str = os.path.abspath(
            os.path.join(out_path_dir, f"temp{i}.info")
        )
        merge_temp_info_cmd = f"lcov --ignore-errors mismatch,corrupt,empty,inconsistent {merge_temp_file_str} -o {temp_info_str}"
        CI_LOG.cilog_info(
            THIS_FILE_NAME, "merge_temp_file_cmd: %s", merge_temp_info_cmd
        )
        change_xml.execute(merge_temp_info_cmd)
        temp_info_str_list.append(" -a " + temp_info_str)

    # 汇总所有temp.info文件为coverage.info
    merge_all_info_file_str = " ".join(temp_info_str_list)
    merge_info_cmd = f"lcov --ignore-errors mismatch,corrupt,empty,inconsistent {merge_all_info_file_str} -o {out_path}"
    CI_LOG.cilog_info(THIS_FILE_NAME, "merge_info_cmd: %s", merge_info_cmd)
    change_xml.execute(merge_info_cmd)


def generate_info_by_file(code_path, tem_info_path, proj_path):
    """
    生成单个文件的info文件
    ：code_path：需要生成info的文件路径
    ：temp_info_path:临时info生成路径
    ：Proj_path:ut/st工程路径
    ：return：
    """
    # TODO:xxx.gcda  xxx.c.gcda
    file_name = os.path.split(code_path)[-1].split(".")[0]
    find_gcda_path_cmd = f'find {proj_path} -path "*/{file_name}.*gcda"'
    CI_LOG.cilog_info(
        THIS_FILE_NAME, "find_gcda_path_cmd: %s", find_gcda_path_cmd)
    # 查找相应文件的gcda文件目录，可能存在多个
    status, output = change_xml.execute(find_gcda_path_cmd)
    if not status:
        CI_LOG.cilog_warning(
            THIS_FILE_NAME,
            "find file (%s) .gcda file failed ,maybe this file has no testcase cover",
            file_name,
        )
        return
    CI_LOG.cilog_info(THIS_FILE_NAME, "file_gcda_path %s", output)
    path_list = list(filter((lambda x: x.strip()), output))
    i = 0
    temp_name = code_path.rsplit(".", 1)[0].replace("/", "_")
    # 对查找出的gcda文件分别生成info文件
    for gcda_path in path_list:
        temp_info_name = temp_name + str(i) + ".info"
        abs_code_path = proj_path + "/" + code_path
        generate_info_path = os.path.abspath(
            os.path.join(tem_info_path, temp_info_name)
        )
        CI_LOG.cilog_info(THIS_FILE_NAME, "%s gcda path is %s",
                          file_name, gcda_path)
        lcov_cmd = f"lcov --ignore-errors mismatch,corrupt,empty -c -d {gcda_path} -o {generate_info_path} --include {abs_code_path}"
        CI_LOG.cilog_info(THIS_FILE_NAME, "lcov_cmd %s", lcov_cmd)
        status, output = change_xml.execute(lcov_cmd)
        if not status:
            CI_LOG.cilog_warning(THIS_FILE_NAME, "generate info failed")
        i = i + 1


def filter_need_cover_code(
        work_dir, classify_rule_path, classify_rule_name, blacklist_path, change_file_list,
        component_name,classify_name_list, test_type=None):
    """
    功能描述：得到需要做增量的代码，1）过滤源文件类型(c,cpp,cce,cc) 2）排除黑名单 3）过滤classify_rule 4）排除软连接
    参数：1.classify_rule_name:责任田中组件名称列表
          2.classify_rule_path:责任田文件路径
          3.blacklist_path:存放工程无需覆盖的文件
          4.change_file_list:修改文件列表
    返回值：需要做增量的代码列表
    异常描述：
    """
    need_cover_path_list = []
    classify_rule_list = []
    classify_rule_list_3rd = []
    # 过滤非源码文件
    filtered_c_list = list(
        filter((lambda x: x.endswith(".c")), change_file_list))
    filtered_cpp_list = list(
        filter((lambda x: x.endswith(".cpp")), change_file_list))
    filtered_cc_list = list(
        filter((lambda x: x.endswith(".cc")), change_file_list))
    filtered_cce_list = list(
        filter((lambda x: x.endswith(".cce")), change_file_list))
    filtered_h_list = [] 
    if classify_name_list[0] in ["atcos", "atcos-dev","ops-nn-dev","ops-transformer-dev","asc-devkit","acl"]:
        filtered_h_list = list(
            filter((lambda x: x.endswith(".h")), change_file_list))
    # 通过工程黑名单过滤修改代码
    if os.path.exists(blacklist_path):
        proj_black_list = read_file_content_to_list(blacklist_path,test_type)
        CI_LOG.cilog_info(THIS_FILE_NAME, "black_list is %s", proj_black_list)
    else:
        proj_black_list = []
        CI_LOG.cilog_info(
            THIS_FILE_NAME,
            "read project blacklist failed ,maybe blacklist file is not exitst",
        )
    filtered_black_file_list = list(
        (set(filtered_c_list)
        | set(filtered_cpp_list)
        | set(filtered_cce_list)
        | set(filtered_cc_list) 
        | set(filtered_h_list)) - set(proj_black_list)
    )
    CI_LOG.cilog_info(
        THIS_FILE_NAME, "filter by blacklist is %s ", filtered_black_file_list
    )

    # 通过classify_rule来过滤修改代码
    classify_rule_name_list = classify_rule_name
    for classify_name in classify_rule_name_list:
        classify_rule_name_3rd = classify_name + "_3RD"
        component_name_list = classify_name.split("@")
        component_name_list_3rd = classify_rule_name_3rd.split("@")
        CI_LOG.cilog_info(
            THIS_FILE_NAME,
            "classify_rule_path is %s ,classify_name: %s , classify_3RD_name: %s",
            classify_rule_path,
            classify_rule_name,
            classify_rule_name_3rd,
        )
        if classify_rule_path.endswith(".txt"):
            ret, temp_classify_rule_list = get_classify_rule.get_classify_rule(
                component_name_list, classify_rule_path
            )
            ret, temp_classify_rule_list_3rd = get_classify_rule.get_classify_rule(
                component_name_list_3rd, classify_rule_path
            )
        else:
            ret, temp_classify_rule_list = get_classify_rule.get_yaml_classify_rule(
                component_name_list, classify_rule_path
            )
            ret, temp_classify_rule_list_3rd = get_classify_rule.get_yaml_classify_rule(
                component_name_list_3rd, classify_rule_path
            )
        classify_rule_list += temp_classify_rule_list
        classify_rule_list_3rd += temp_classify_rule_list_3rd
    CI_LOG.cilog_info(
        THIS_FILE_NAME,
        "classify_rule_list is %s ,classify_rule_list_3rd is %s",
        classify_rule_list,
        classify_rule_path,
    )

    if not classify_rule_list:
        CI_LOG.cilog_error(THIS_FILE_NAME, "classify_rule_list is empty")
        return False, None
    for code_path in filtered_black_file_list:
        if os.path.islink(os.path.join(work_dir, code_path)):
            CI_LOG.cilog_info(THIS_FILE_NAME, "file is link: %s", code_path)
            continue
        for classify_rule in classify_rule_list:
            if classify_rule_path.endswith("classify_rule.txt"):
                if not code_path.startswith(classify_rule) or \
                        not os.path.exists(os.path.join(work_dir, component_name, code_path)):
                    continue
            else:
                if not code_path.endswith(classify_rule) or \
                        not os.path.exists(os.path.join(work_dir, component_name, code_path)):
                    continue
            need_cover_path_list.append(code_path)
            for classify_rule_3rd in classify_rule_list_3rd:
                if code_path.startswith(classify_rule_3rd) and (
                    len(classify_rule_3rd) > len(classify_rule)
                ):
                    need_cover_path_list.remove(code_path)
                    break
            break
    CI_LOG.cilog_info(
        THIS_FILE_NAME, "finally need_cover_path_list is %s ", need_cover_path_list
    )
    return True, need_cover_path_list


def generate_modify_file_info(filter_path_list, proj_path):
    """
    功能描述：生成所有修改文件代码的总info文件
    参数：1.filter_path_list:存放工程需覆盖文件的列表
          2.proj_path:ut/st工程路径
    返回值：返回info文件路径
    """
    coverage_info_path = os.path.abspath(
        os.path.join(proj_path, "coverage_add.info"))
    create_info_cmd = f"touch {coverage_info_path}"
    change_xml.execute(create_info_cmd)

    temp_info_path = os.path.abspath(
        os.path.join(proj_path, "temp_add_info"))
    if os.path.exists(temp_info_path):
        shutil.rmtree(temp_info_path)
    os.mkdir(temp_info_path)
    for code_path in filter_path_list:
        generate_info_by_file(code_path, temp_info_path, proj_path)
    if os.listdir(temp_info_path):
        merge_info(temp_info_path, coverage_info_path)
    return coverage_info_path


def read_file_content_to_list(file_path, test_type=None):
    """
    将文件内容转化为列表
    ：file_path:文件路径
    ：test_type:测试类型 (ut/st)，用于过滤黑名单
    ：return：文件内容列表
    """
    code_path_list = []
    if not os.path.isfile(file_path):
        CI_LOG.cilog_error(THIS_FILE_NAME, "file : %s is not file", file_path)
        return code_path_list
    with open(file_path, "r", encoding="UTF-8") as op_file:
        for line in op_file.readlines():
            if line[0] in ["A","M","D","U","C", "R"]:
                if line.startswith("R100") or line.startswith("D"):
                    continue
                elif line.startswith("R"):
                    code_path_list.append(line.split()[2].strip())
                else:
                    code_path_list.append(line.split()[1].strip())
            elif file_path.endswith("blacklist.txt"):
                # 解析黑名单行，根据测试类型过滤
                line_content = line.strip()
                if not line_content:
                    continue
                parts = line_content.split()
                if len(parts) == 1:
                    # 没有标记，默认所有类型都屏蔽
                    code_path_list.append(parts[0])
                elif len(parts) >= 2:
                    # 有标记，只在匹配时屏蔽
                    file_path_item = parts[0]
                    line_test_type = parts[1].strip().lower()
                    if test_type and line_test_type == test_type.lower():
                        code_path_list.append(file_path_item)
                    # 不匹配则不添加

    # 去重
    code_path_list = list(set(code_path_list))
    return code_path_list

def read_change_file(change_file):
    """
    读取本次提交修改的文件列表
    chang_file：本次修改文件列表路径，文件中包含本次修改的文件列表
    return：修改文件列表
    """
    file_list = read_file_content_to_list(change_file)
    change_file_list = list(
        map((lambda x: x.replace(":", "/").strip()), file_list))
    return change_file_list


def change_addinfo_data_from(output, code_dir):
    """
    功能描述：将列表中的增量信息内容格式成和diff命令获得的内容相似的格式，并检查本次修改是否全为删除操作
    参数：output:该列表保存执行git diff命令生成的文件差异信息内容 2.code_dir:变更代码仓路径
    返回值：保存文件差异信息内容列表
    """
    add_info_list = []
    all_delete_flag = True

    for each_line in output:
        if each_line.find("--- ") != -1:
            each_line = "--- " + code_dir
        elif each_line.find("+++ ") != -1:
            each_line = "+++ " + code_dir
        elif each_line.find("@@") != -1:
            op_path = re.search("@@.+@@", each_line)
            if op_path is not None:
                CI_LOG.cilog_info(
                    THIS_FILE_NAME, "match content is %s", op_path.group(0)
                )
                each_line = op_path.group(0)
            else:
                CI_LOG.cilog_error(
                    THIS_FILE_NAME,
                    "make add_ut.info error! match op_path content is %s",
                    op_path,
                )
        elif each_line.startswith("+"):
            all_delete_flag = False
        add_info_list.append(each_line)

    if all_delete_flag:
        CI_LOG.cilog_info(
            THIS_FILE_NAME,
            "%s modify is all delete no need  to incremental cover",
            code_dir,
        )
        return []
    return add_info_list


def make_diff_file(
    info_path, out_dir, work_dir, filter_path_list, branch, classify_name
):
    """
    功能描述：生成代码变更信息差异文件
    参数：1.info_path:全量覆盖率文件路径
          2.out_dir:保持diff文件的路径
          3.work_dir:工作目录
          4.filter_path_list:需要做增量覆盖率的代码列表
          5.主线分支名
    返回值：生成差异文件成功返回True，否则返回相应异常值
    异常描述：
    """
    # 获取有用例覆盖文件列表
    cover_file_list = get_lcov_file_from_info(
        info_path, work_dir, classify_name)

    # 获取有用例覆盖文件和需要做覆盖的文件交集
    code_path_list = list(set(cover_file_list) & set(filter_path_list))
    uncover_file = []
    if filter_path_list:
        for tmp in filter_path_list:
            if tmp not in code_path_list:
                uncover_file.append(tmp)
        if len(uncover_file) != 0:
            CI_LOG.cilog_error(
                THIS_FILE_NAME, "file not found in coverage.info %s", uncover_file)
            sys.exit(0)
    CI_LOG.cilog_info(THIS_FILE_NAME, "code_path_list is %s", code_path_list)
    delete_file_list = []
    if len(code_path_list) == 0:
        CI_LOG.cilog_info(
            THIS_FILE_NAME, "no need run addlcov .cover list is %s", code_path_list
        )
        return NO_NEED_TOCOVER, delete_file_list
    # 生成代码变更差异信息文件
    delete_count = 0
    for code_path in code_path_list:
        file_flag = code_path.replace(".", "_").replace("/", "_")
        # if classify_name in ["graphengine", "fe", "aicpu", "ffts", "dvpp", "ge_executor_c"]:
        #     classify_name = "air"
        # if classify_name in ["acl_c"]:
        #     classify_name = "acl"
        code_dir = work_dir + "/" + classify_name + "/" + code_path
        diff_file = os.path.join(out_dir, DIFF_FILE_PREFIX + file_flag)
        if not os.path.exists(code_dir):
            CI_LOG.cilog_info(THIS_FILE_NAME, "file not exist : %s", code_dir)
            delete_count += 1
            delete_file_list.append(code_path)
            continue
        # 通过git diff命令获取到相关差异信息
        os.chdir(os.path.split(code_dir)[0])
        cmd = f"git diff origin/{branch} HEAD -- {code_dir}"
        status, output = change_xml.execute(cmd)
        if not status:
            CI_LOG.cilog_error(
                THIS_FILE_NAME, "git diff execute error ,output is %s", output
            )
            return GENERATE_DIFF_FAIL, delete_file_list
        # 日志限流：完整 diff 全文回显会撑爆平台单步骤 ~1MB 日志上限（超限被 SIGTERM）
        CI_LOG.cilog_info(
            THIS_FILE_NAME, "get output succ, %d 行 diff, 首行: %s",
            len(output), output[0] if output else "")
        addinfo_data = change_addinfo_data_from(output, code_dir)
        if not addinfo_data:
            delete_count += 1
            delete_file_list.append(code_path)
            continue
        with open(diff_file, "w+", encoding="utf-8") as difffile:
            for head in addinfo_data:
                difffile.write(head)
                difffile.write("\n")
    # 本次修改全是删除操作，没必要生成diff文件做增量覆盖率
    if delete_count == len(code_path_list):
        CI_LOG.cilog_info(
            THIS_FILE_NAME, "all modify is delete, no need to generate diff file"
        )
        return NO_NEED_TOCOVER, delete_file_list
    return GENERATE_DIFF_SUCC, delete_file_list


def zip_path(fname_path):
    """
    功能描述：压缩目录
    参数：fname_path:要压缩的文件目录
    返回值：
    异常描述：
    """
    os.chdir(fname_path)
    zip_html_cmd = "zip -r result.zip ./result"
    CI_LOG.cilog_info(THIS_FILE_NAME, "zip cmd is %s", zip_html_cmd)
    change_xml.execute(zip_html_cmd)


def get_line_coverage(html_path, addinfo_html, threshold):
    """
    功能描述：获得line覆盖率数据
    参数：1.html_path:增量信息html页面路径
          2.addinfo_html:
          3.thredhold:覆盖率门限值
    返回值：modem侧100%覆盖，ap侧80%覆盖，返回True，ap侧否则返回不成功的指示值
    异常描述
    """
    CI_LOG.cilog_info(
        THIS_FILE_NAME, "the html path is %s:,the html is %s:", html_path, addinfo_html
    )

    # 先对生成的增量html进行压缩，通过工程xml文件中的reportfile上传
    add_html_path = os.path.abspath(os.path.join(html_path, ".."))
    CI_LOG.cilog_info(THIS_FILE_NAME, "html_path is %s", add_html_path)
    zip_path(add_html_path)
    add_info_html = os.path.join(html_path, addinfo_html)
    if not os.path.exists(os.path.join(html_path, addinfo_html)):
        CI_LOG.cilog_error(
            THIS_FILE_NAME, "add_coverrage html: index.html not exists")
        return False

    CI_LOG.cilog_info(THIS_FILE_NAME, "add_info_html is %s", add_info_html)
    # 读取增量HTML内容
    with open(add_info_html, "r", encoding="utf-8") as index_html:
        index_html_content = index_html.read()
    pattern = r'<td class="headerCovTableEntry.+">(.*?)</td>'
    coverage_data = re.findall(pattern, index_html_content)
    CI_LOG.cilog_info(
        THIS_FILE_NAME, "line coverage_data is %s", coverage_data)
    line_coverage = "0.00%"
    if len(coverage_data) > 0:
        line_coverage = coverage_data[0].replace(" ", "")
    CI_LOG.cilog_info(THIS_FILE_NAME, "line coverage is %s", line_coverage)
    coverage_number = int(line_coverage.split(".")[0])
    threshold_num = int(threshold)
    if coverage_number >= threshold_num:
        CI_LOG.cilog_info(
            THIS_FILE_NAME,
            "line coverage is over %d,add coverage result is succ!",
            threshold_num,
        )
        return True
    CI_LOG.cilog_info(
        THIS_FILE_NAME,
        "line coverage is blow %d, add coverage result is fail!",
        threshold_num,
    )
    return False


def addlcov_generate_info(out_dir, all_info_path):
    """
    利用addlcov生成增量info文件
    ：outdir：diff文件路径
    ：all_info_path:全量info文件路径
    ：return：增量info文件路径
    """
    file_list = os.listdir(out_dir)
    pwd = os.path.abspath(os.path.curdir)
    CI_LOG.cilog_info(THIS_FILE_NAME, "--pwd is %s", pwd)
    os.chdir(THIS_FILE_PATH)
    for f in file_list:
        if f.startswith(DIFF_FILE_PREFIX):
            difffile = os.path.join(out_dir, f)
            CI_LOG.cilog_info(THIS_FILE_NAME, "difffile is %s", difffile)
            info_file = os.path.split(f)[1]
            out_put = os.path.join(
                out_dir, "add_ut_" + info_file.split("@")[1] + ".info"
            )
            make_infofile_cmd = f"./addlcov --diff {all_info_path} {difffile} -o {out_put}"
            CI_LOG.cilog_info(
                THIS_FILE_NAME, "addlcov cmd is %s", make_infofile_cmd)
            change_xml.execute(make_infofile_cmd)
    all_add_info = os.path.join(out_dir, INFO_FILE)
    merge_info(out_dir, all_add_info)
    os.chdir(pwd)
    return all_add_info


def generate_incremental_html(out_dir, all_add_info_path, work_dir):
    """
    功能描述：生成各自的增量覆盖率html页面
    参数：out_dir:git diff 生成的diff file存放目录
          all_add_info_path:增量info文件路径
          work_dir:workcode路径
    返回值：True 任务执行成功，False任务执行失败
    """
    CI_LOG.cilog_info(
        THIS_FILE_NAME,
        "out_dir is %s,all_add_info_path is %s,work_dir is %s",
        out_dir,
        all_add_info_path,
        work_dir,
    )
    output_use_genhtml = os.path.join(out_dir, "result")
    use_genhtml_make_html_cmd = (
        f"genhtml  --prefix {work_dir} -o {output_use_genhtml} {all_add_info_path} \
--legend -t CHG --no-branch-coverage --no-function-coverage --ignore-errors source"
    )
    status, output = change_xml.execute(use_genhtml_make_html_cmd)
    if not status:
        return False
    return True


def main():
    """获取责任田文件,做增量覆盖率"""
    params_dict = {}
    if len(sys.argv) < 7:
        CI_LOG.cilog_error(THIS_FILE_NAME, "the number of parameters is wrong")
        sys.exit(-1)
    CI_LOG.cilog_info(
        THIS_FILE_NAME, "params , classify_rule: %s", sys.argv[1])

    params_dict[PARA_KEY_CLASSIFY] = list(
        set(sys.argv[1].split()) - set(["None"]))
    params_dict[PARA_KEY_BRANCH] = sys.argv[2]
    params_dict[PARA_KEY_BLACKLIST] = list(
        set(sys.argv[3].split()) - set(["None"]))
    params_dict[PARA_KEY_PROJECT] = sys.argv[4]
    params_dict[PARA_KEY_RC] = sys.argv[5]
    params_dict[PARA_KEY_THRESHOLD] = list(
        set(sys.argv[6].split()) - set(["None"]))
    params_dict[PARA_KEY_INFO] = sys.argv[7]
    if len(sys.argv) > 8:
        test_type_raw = sys.argv[8]
        # 处理 "None" 字符串的情况
        if test_type_raw and test_type_raw.lower() not in ["none", "null"]:
            params_dict[PARA_KEY_TEST_TYPE] = test_type_raw.lower()
        else:
            params_dict[PARA_KEY_TEST_TYPE] = None
    else:
        params_dict[PARA_KEY_TEST_TYPE] = None
    if PARA_KEY_CLASSIFY not in params_dict or PARA_KEY_PROJECT not in params_dict:
        CI_LOG.cilog_error(
            THIS_FILE_NAME, "less param calssify_rule_name or project ")
        sys.exit(-1)

    if len(params_dict[PARA_KEY_BLACKLIST]) > 1:
        CI_LOG.cilog_warning(
            THIS_FILE_NAME, "Have more then one LOCAL_INC_COV_BLACKLIST in one module"
        )

    if len(params_dict[PARA_KEY_BLACKLIST]) == 0:
        params_dict[PARA_KEY_BLACKLIST] = ""
    else:
        params_dict[PARA_KEY_BLACKLIST] = params_dict[PARA_KEY_BLACKLIST][0]
    if len(params_dict[PARA_KEY_THRESHOLD]) == 0:
        params_dict[PARA_KEY_THRESHOLD] = "100"
    else:
        params_dict[PARA_KEY_THRESHOLD] = min(params_dict[PARA_KEY_THRESHOLD])

    if PARA_KEY_RC not in params_dict:
        params_dict[PARA_KEY_RC] = "true"
    if PARA_KEY_CHANGEFILE not in params_dict:
        params_dict[PARA_KEY_CHANGEFILE] = os.path.abspath(
            os.path.join(params_dict[PARA_KEY_PROJECT],
                         "./pr_filelist_mod.txt")
        )

    classify_name_list = params_dict[PARA_KEY_CLASSIFY]
    CI_LOG.cilog_info(
                THIS_FILE_NAME, "classify_name_list: %s", classify_name_list
            )
    # 工程增量黑名单文件路径，黑名单中的文件不需要做增量覆盖率
    blacklist_path = params_dict[PARA_KEY_BLACKLIST]
    test_type = params_dict.get(PARA_KEY_TEST_TYPE)
    # 工程对应的责任田名称
    classify_rule_name = []
    params_dict[PARA_KEY_CLASSIFY].sort(reverse=False)
    for classify_rule in params_dict[PARA_KEY_CLASSIFY]:
        if params_dict[PARA_KEY_CLASSIFY][0] in classify_rule:
            classify_rule_name.append(classify_rule)
        else:
            CI_LOG.cilog_error(
                THIS_FILE_NAME, "Have different module: %s", classify_rule
            )
            sys.exit(-1)
    # 如果有全量的info路径，直接使用，否则生成修改文件全量info文件
    if (
        PARA_KEY_INFO in params_dict
        and params_dict[PARA_KEY_INFO]
        and os.path.exists(params_dict[PARA_KEY_INFO])
    ):
        info_path = params_dict[PARA_KEY_INFO]

    # else:
    #     info_path = generate_modify_file_info(filter_path_list, proj_path)
    CI_LOG.cilog_info(THIS_FILE_NAME, "***info_path is %s", info_path)
    # 工程路径
    proj_path = params_dict[PARA_KEY_PROJECT]
    # 覆盖率拦截标记
    rc_config_value = params_dict[PARA_KEY_RC]
    # 所有修改文件列表路径
    change_file = params_dict[PARA_KEY_CHANGEFILE]
    threshold = params_dict[PARA_KEY_THRESHOLD]
    addinfo_html = "index.html"
    if classify_name_list[0] in ["canndev", "ops"]:
        addinfo_dir = "build/test/ut/cov_report/ops/cpp_utest/inc_cov"
    elif classify_name_list[0] in ["cann-ops-adv-dev", "cann-ops-adv"]:
        addinfo_dir = "build/tests/ut/ops_test/cov_result/inc_cov"
    elif classify_name_list[0] in ["ascendc-api-adv-dev", "ascendc-api-adv"]:
        addinfo_dir = "build/cov_report/inc_cov"
    elif classify_name_list[0] in ["tensorflow", "torchair"]:
        addinfo_dir = "coverage/inc_cov"
    elif classify_name_list[0] == "ops_base":
        addinfo_dir = "build/cov/inc_cov"
    elif classify_name_list[0] == "att":   
        addinfo_dir = "att/cov/inc_cov"
    elif classify_name_list[0] in ["atvc", "atvc-dev", "atvoss-dev", "atvoss", "atcos-dev", "atcos", "asc-devkit-dev", "asc-tools"]:
        addinfo_dir = "build/cov_report/inc_cov"
    else:
        addinfo_dir = "cov/inc_cov"
    # *********这个路径?
    # component_name = os.path.abspath(proj_path).split("llt/")[-1].split("/")[0]

    out_dir = os.path.abspath(os.path.join(proj_path, addinfo_dir))
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    work_dir = os.path.dirname(os.path.abspath(proj_path))
    component_name = proj_path.split("/")[-1]
    if classify_name_list[0] == "canndev":
        classify_rule_path = os.path.join(
            work_dir, component_name + "/classify_rule.txt"
        )
    else:
        print(work_dir)
        print(component_name)
        print(classify_name_list[0])
        classify_rule_path = os.path.join(
            proj_path, classify_name_list[0] + "_field.txt"
        )
    blacklist_abspath = os.path.join(work_dir, component_name, blacklist_path)

    # 检查、输出参数
    if not os.path.exists(proj_path):
        CI_LOG.cilog_error(
            THIS_FILE_NAME, "proj_path: %s is not exitst", proj_path)
        exit_code(rc_config_value)

    CI_LOG.cilog_info(
        THIS_FILE_NAME,
        "classify_rule_name is :%s ,proj_path is :%s,blacklist_path is :%s,\
changed_files_list is :%s,out_dir is :%s,RC_config_value is :%s,threshold is :%s,test_type is :%s",
        classify_rule_name,
        proj_path,
        blacklist_abspath,
        change_file,
        out_dir,
        rc_config_value,
        threshold,
        test_type,
    )
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    # 建立存储增量信息目录
    os.mkdir(out_dir)
    # 获取修改代码列表
    change_file_list = read_change_file(change_file)
    if not change_file_list:
        CI_LOG.cilog_error(THIS_FILE_NAME, "changed_file_list is empty")
        sys.exit(0)
    CI_LOG.cilog_info(
        THIS_FILE_NAME, "changed_file list is %s", change_file_list)
    # 获取做增量覆盖率的代码列表，通过classify_rule和blacklist过滤，同时过滤头文件
    ret, filter_path_list = filter_need_cover_code(
        work_dir,
        classify_rule_path,
        classify_rule_name,
        blacklist_abspath,
        change_file_list,
        component_name,
        classify_name_list,
        test_type,
    )
    if not ret:
        CI_LOG.cilog_error(THIS_FILE_NAME, "filter need cover code failed")
        exit_code(rc_config_value)
    CI_LOG.cilog_info(
        THIS_FILE_NAME, "filter_path_list is %s", filter_path_list)
    if len(filter_path_list) == 0:
        CI_LOG.cilog_info(
            THIS_FILE_NAME, "no need run addlcov .cover list is %s", filter_path_list
        )
    # 生成代码变更信息文件
    make_result, del_file_list = make_diff_file(
        info_path,
        out_dir,
        work_dir,
        filter_path_list,
        params_dict[PARA_KEY_BRANCH],
        component_name,
    )
    CI_LOG.cilog_info(THIS_FILE_NAME, "del_file_list is %s", del_file_list)
    if make_result == GENERATE_DIFF_SUCC:
        CI_LOG.cilog_info(THIS_FILE_NAME, "generate diff file success")
    elif make_result == NO_NEED_TOCOVER:
        sys.exit(0)
    else:
        exit_code(rc_config_value)

    # 生成增量info文件
    all_add_info_path = addlcov_generate_info(out_dir, info_path)
    # 生成增量覆盖率
    result = generate_incremental_html(out_dir, all_add_info_path, work_dir)
    if result:
        CI_LOG.cilog_info(THIS_FILE_NAME, "gen html file succ")
    else:
        CI_LOG.cilog_error(THIS_FILE_NAME, "gen html file fail")

    # 分析增量网页信息，压缩增量html目录，获取，输出增量结果
    html_path = os.path.join(out_dir, "result")
    get_cov_result = get_line_coverage(html_path, addinfo_html, threshold)
    if get_cov_result:
        sys.exit(0)
    else:
        exit_code(rc_config_value)


if __name__ == "__main__":
    main()
