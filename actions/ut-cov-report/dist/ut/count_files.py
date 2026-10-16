# -*- coding: utf-8 -*-
"""根据classify_fule统计责任田文件"""

import os
import sys
from pathlib import Path
import yaml


def op_txt(cpt, op_path):
    """
    功能描述：操作责任田文件，以“【”为标志位来确定组件
    参数：cpt:组件名
         op_path:责任田文件
    返回值：index_list：组件索引列表
          op_list：包含组件名的内容
          context：去掉空格和空行的结果
          cpt_index：想要获取的组件索引
    """
    index_list = []
    op_list = []
    context = []
    cpt_index = 0
    with open(op_path, encoding="utf-8") as op_file:
        tmp_op_lines = op_file.readlines()
        op_lines = [i.replace("\n", "") for i in tmp_op_lines if i != "\n"]
        for op_line in op_lines:
            tmp_op_line = op_line.strip()
            if not tmp_op_line.endswith(".py"):
                context.append(tmp_op_line)
        for line in op_lines:
            if line.startswith("["):
                index_list.append(op_lines.index(line))
            else:
                op_list.append(line.strip())
    # 在组件索引列表中获取组件的索引
    for i in context:
        if cpt in i:
            cpt_index = context.index(i)
        else:
            continue

    return index_list, cpt_index, context


def index_component(component, op_path):
    """
    功能描述：获取所需组件在责任田文件中的对应内容
    参数：component:不包含[]的组件名
         op_path：责任田文件路径
    返回值：op_content：组件在责任田文件中的对应内容
    """
    op_content = []
    cpt = "[" + component + "]"  # 组件名+[],方便在文件中查找
    index_list, cpt_num, op_content = op_txt(cpt, op_path)
    # 根据返回的组件索引，获取对应的组件内容
    if cpt_num == 0 and len(index_list) != 1:
        return op_content[index_list[0] + 1 : index_list[index_list.index(cpt_num) + 1]]
    if cpt_num == 0 and len(index_list) == 1:
        return op_content[index_list[0] + 1 :]
    if index_list[-1] != cpt_num:
        return op_content[cpt_num + 1 : index_list[index_list.index(cpt_num) + 1]]
    if index_list[-1] == cpt_num:
        return op_content[cpt_num + 1 :]
    return op_content[cpt_num : index_list[index_list.index(cpt_num) + 1]]


def count_file(class_rule_path, component, component_path, field_path):
    """根据classfy_rule.txt生成责任田文件"""
    op_content = index_component(component, class_rule_path)
    print(op_content)
    field = os.path.join(field_path, component + "_field.txt")
    with open(field, "a", encoding="UTF-8") as field_file:
        field_file.writelines("[" + component + "]" + "\n")
        for paths in op_content:
            f_path = os.path.join(component_path, paths)
            # with open(field, "a") as f:
            # f.writelines("["+component+"]"+"\n")
            for root, dirs, files in os.walk(f_path):
                for file in files:
                    if component != "acl":
                        if file.endswith(".cc"):
                            full_path = os.path.join(root, file)
                            temp_path = full_path.split(component_path + "/", 1)
                            field_file.writelines(temp_path[1] + "\n")
                        else:
                            continue
                    else:
                        if (
                            file.endswith(".cc")
                            or file.endswith(".h")
                            or file.endswith(".cpp")
                        ):
                            full_path = os.path.join(root, file)
                            temp_path = full_path.split(component_path + "/", 1)
                            field_file.writelines(temp_path[1] + "\n")


def get_unrelease_files(root_path, pattern):
    root = Path(root_path)
    file_paths = []
    for matched_dir in root.glob(pattern):
        if matched_dir.is_dir():
            # 递归遍历该目录下所有文件
            for file in matched_dir.rglob("*"):
                if file.is_file():
                    # 去掉根路径，转为相对路径字符串
                    relative_path = file.relative_to(root)
                    file_paths.append(str(relative_path) + "\n")
    return file_paths


def count_yaml(class_rule_path, component, component_path, field_path):
    """
    读取yaml，生成责任田文件
    """
    file_path = []
    unrelease_path = []
    with open(class_rule_path, "r", encoding="utf-8") as tmp_class_rule_path:
        # 读取yaml中的release和unrelease的内容，以便进一步处理
        file = tmp_class_rule_path.read()
        content = yaml.load(file, Loader=yaml.SafeLoader)
        component_origin = component
        if component == "ops-nn":
            for comp_key, comp_val in content.items():
                if not isinstance(comp_val, dict) or "src" not in comp_val:
                    continue
                src = comp_val["src"]
                release = src.get("release", {})
                if isinstance(release, dict):
                    for style in ["huawei_style", "style", "opensource_style", "kernel_style"]:
                        if style in release and release[style]:
                            file_path.extend(release[style])
                elif isinstance(release, list):
                    file_path.extend(release)
                unrelease = src.get("unrelease", {})
                if isinstance(unrelease, dict):
                    for section in ["test_code", "non_delivery", "open_source"]:
                        if section in unrelease and unrelease[section]:
                            unrelease_path.extend(unrelease[section])
                elif isinstance(unrelease, list):
                    unrelease_path.extend(unrelease)
        else:
            if component not in content:
                component = component + f"@{component}"
            file_path = content[component]["src"]["release"]
            if component == "ops_math":
                unrelease_path = ["*/*/test", "*/*/docs", "*/*/examples", "examples/*", "random/sim_thread_exponential/op_host/sim_thread_exponential_def.cpp"]
            else:
                unrelease_path = content[component]["src"]["unrelease"]
    # 将读取yaml中release的内容写进责任田，如果是文件夹需要遍历文件夹再写入
    # auto_schedule的需要单独处理
    if component_origin == "ops-nn":
        processed_file_path = []
        for p in file_path:
            parts = p.split(os.sep)
            new_path = os.sep.join(parts[2:]) if len(parts) > 2 else ""
            if new_path:
                processed_file_path.append(new_path)
        file_path = processed_file_path

        processed_unrelease_path = []
        for p in unrelease_path:
            parts = p.split(os.sep)
            new_path = os.sep.join(parts[2:]) if len(parts) > 2 else ""
            if new_path:
                processed_unrelease_path.append(new_path)
        unrelease_path = processed_unrelease_path
    field = os.path.join(field_path, component_origin + "_field.txt")
    release_file = []
    unreleas_file = []
    for paths in file_path:
        if (
            paths.endswith(".py")
            or paths.endswith(".cc")
            or paths.endswith(".cpp")
            or paths.endswith(".h")
            or paths.endswith(".c")
        ):
            release_file.append(paths + "\n")
        else:
            dir_path = os.path.join(component_path, paths)
            if os.path.isdir(dir_path):
                for root, dirs, files in os.walk(dir_path):
                    for file in files:
                        if (
                            file.endswith(".py")
                            or file.endswith(".cc")
                            or file.endswith(".cpp")
                            or file.endswith(".h")
                            or file.endswith(".c")
                        ):
                            full_path = os.path.join(root, file)
                            temp_path = full_path.split(component_path + "/", 1)
                            release_file.append(temp_path[1] + "\n")
            else:
                continue

    if unrelease_path:
        for paths in unrelease_path:
            for path in Path(component_path).glob(paths):
                if os.path.isdir(path):
                    unreleas_file.extend(
                        get_unrelease_files(component_path, paths)
                    )
                else:
                    if path.is_file():
                        relative_path = path.relative_to(component_path)
                        unreleas_file.append(str(relative_path) + "\n")
        for tmp in release_file[:]:
            if tmp in unreleas_file:
                release_file.remove(tmp)
    with open(field, "a", encoding="utf-8") as tmp_class_rule_path:
        tmp_class_rule_path.writelines("[" + component_origin + "]" + "\n")
        tmp_class_rule_path.writelines(release_file)


def read_dict(yaml_dict):
    # 递归函数读取yaml中的src文件
    for key, value in yaml_dict.items():
        if key != "tests":
            if key == "src":
                ops_list.extend(value)
            elif isinstance(value, dict):
                for k, v in value.items():
                    if k == "src":
                        ops_list.extend(v)
                        break
                    else:
                        if isinstance(v, dict):
                            read_dict(v)


def count_ops_yaml(class_rule_path, component, component_path, field_path):
    # 读取ops仓yaml中的内容，以便进一步处理
    global ops_list
    ops_list = []
    release_file = []
    with open(class_rule_path, "r", encoding="utf-8") as tmp_class_rule_path:
        file = tmp_class_rule_path.read()
        content = yaml.load(file, Loader=yaml.SafeLoader)
        for key, value in content.items():
            if key in ["src", "utils"]:
                read_dict(value)
    for paths in ops_list:
        dir_path = os.path.join(component_path, paths)
        if os.path.isdir(dir_path):
            for root, dirs, files in os.walk(dir_path):
                for file in files:
                    if not file.endswith(".txt"):
                        full_path = os.path.join(root, file)
                        temp_path = full_path.split(component_path + "/", 1)
                        release_file.append(temp_path[1] + "\n")
    field = os.path.join(field_path, component + "_field.txt")
    tmp_set=set(release_file)
    release_file = list(tmp_set)
    with open(field, "a", encoding="utf-8") as tmp_class_rule_path:
        tmp_class_rule_path.writelines("[" + component + "]" + "\n")
        tmp_class_rule_path.writelines(release_file)

    if component in ["cann-ops-adv-dev"]:
        flash_attention_score_grad = []
        flash_attention_score = []
        flash_attention_score_grad_field = os.path.join(field_path, "flash_attention_score_grad" + "_field.txt")
        flash_attention_score_field = os.path.join(field_path, "flash_attention_score" + "_field.txt")
        for file in release_file:
            if "flash_attention_score" in file and "flash_attention_score_grad" not in file:
                # 去除kernel 分发.cpp
                if "flash_attention_score.cpp" not in file:
                    flash_attention_score.append(file)
            if "flash_attention_score_grad" in file:
                 # 去除kernel 分发.cpp
                if "flash_attention_score_grad.cpp" not in file:
                    flash_attention_score_grad.append(file)
        with open(flash_attention_score_grad_field, "a", encoding="utf-8") as tmp_f:
            tmp_f.writelines("[" + "flash_attention_score_grad" + "]" + "\n")
            tmp_f.writelines(flash_attention_score_grad)
        with open(flash_attention_score_field, "a", encoding="utf-8") as tmp_f1:
            tmp_f1.writelines("[" + "flash_attention_score" + "]" + "\n")
            tmp_f1.writelines(flash_attention_score)

def main(classify_rule_file, component, component_script, fields_path):
    """根据传入的文件类型生成组件责任田"""
    if classify_rule_file.endswith("txt"):
        count_file(classify_rule_file, component, component_script, fields_path)
    else:
        if component not in [
            "ops",
            "ops-dev",
            "cann-ops-adv-dev",
            "cann-ops-adv",
        ]:
            count_yaml(classify_rule_file, component, component_script, fields_path)
        else:
            count_ops_yaml(classify_rule_file, component, component_script, fields_path)
    print("count files success")


if __name__ == "__main__":
    """
    目的：根据classify_fule.txt统计责任田文件
    参数: classify_rule_file:classify_fule.txt
         component:组件名
         component_script:所需统计组件脚本的位置
         fields_path:责任田存放文件地址
    """
    CLASSIFY_RULE = sys.argv[1]
    COMPONENT_NAME = sys.argv[2]
    COMPONENT_SCRIPT_PATH = sys.argv[3]
    PARAM_FIELD = sys.argv[4]
    main(CLASSIFY_RULE, COMPONENT_NAME, COMPONENT_SCRIPT_PATH, PARAM_FIELD)
