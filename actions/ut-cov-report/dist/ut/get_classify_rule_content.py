#!/usr/bin/python
# -*- coding: utf-8 -*-

"""获取classrule的内容"""
import os
import sys
import yaml

import ci_log as CI_LOG

THIS_FILE_NAME = __file__
THIS_FILE_PATH = os.path.dirname(os.path.realpath(THIS_FILE_NAME))


def get_classify_rule(component_list, classify_rule_path):
    """获取classrule"""
    if not os.path.isfile(classify_rule_path):
        CI_LOG.cilog_error(
            THIS_FILE_PATH, "classift_rule_path:%s is error", classify_rule_path
        )
        return False, []
    with open(classify_rule_path, "r", encoding="UTF-8") as fh:
        content = fh.readlines()
    classify_rule = []
    key = ""
    for component in component_list:
        for line in content:
            line = line.strip()
            if line.startswith("[") and line.endswith("]"):
                key = line.strip("[] ")
            elif key == component and key != "" and line != "":
                classify_rule.append(line)
    return True, classify_rule


def get_yaml_classify_rule(component_list, classify_rule_path):
    """获取yaml文件内容"""
    if not os.path.isfile(classify_rule_path):
        CI_LOG.cilog_error(
            THIS_FILE_PATH, "classift_rule_path:%s is error", classify_rule_path
        )
        return False, []
    classify_rule = []
    with open(classify_rule_path, "r", encoding="utf-8") as f:
        cpt = yaml.safe_load(f.read())
        for component in component_list:
            for k in cpt:
                if k == component:
                    classify_rule.extend(cpt[component]["src"]["release"])
        return True, classify_rule


def modify_classify_rule_list(classify_rule_list):
    """编辑class rule列表"""
    new_list = []
    for classify_rule in classify_rule_list:
        new_format = "*/" + classify_rule + "*"
        new_list.append(new_format)
    return new_list


def main():
    """获取classrule主函数"""
    if len(sys.argv) < 3:
        CI_LOG.cilog_error(
            THIS_FILE_PATH, "parameter error ! para list is %s", sys.argv
        )
        sys.exit(-1)

    component = sys.argv[1]
    component_list = component.split(":")
    classify_rule_path = os.path.abspath(sys.argv[2])
    CI_LOG.cilog_info(
        THIS_FILE_PATH,
        "component is %s, classify_rule_path is %s,",
        component,
        classify_rule_path,
    )

    ret, classify_rule = get_classify_rule(component_list, classify_rule_path)
    if not ret:
        CI_LOG.cilog_error(THIS_FILE_PATH, "get_classify_rule error")
        return ""
    if not classify_rule:
        CI_LOG.cilog_error(THIS_FILE_PATH, "classify_rule list is empty")
        return ""
    new_format_classify_rule = modify_classify_rule_list(classify_rule)
    filter_string = " ".join(new_format_classify_rule)
    CI_LOG.cilog_info(THIS_FILE_PATH, "filter string is %s", filter_string)
    return filter_string


if __name__ == "__main__":
    main()
