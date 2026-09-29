#!/usr/bin/python
# -*- coding: utf-8 -*-
"""创建提交修改的xml"""

import os
import platform
import subprocess
import sys
import time
import signal
import xml.dom.minidom as Dom

CURRENT_DIR = os.getcwd()


def read_cover_file(cover_file):
    """读取覆盖率文件"""
    if not os.path.isfile(cover_file):
        print(f"[ERROR]:the {cover_file} is not exitst")
        sys.exit(1)

    cover_list = []
    with open(cover_file, "rb", encoding="UTF-8") as file_handler:
        for each_line in file_handler:
            cover_list.append(each_line.strip())
    return cover_list


def _log_tail(s, head=10, tail=20):
    """日志限流：保留前 head 行与后 tail 行，中间省略（防撑爆步骤日志 ~1MB 上限）"""
    lines = s.splitlines()
    if len(lines) <= head + tail:
        return s
    return "\n".join(lines[:head] + ["...(中间省略)..."] + lines[-tail:])


def execute(cmd, timeout=3600, print_output_flag=False):
    """执行函数"""
    is_linux = platform.system() == "Linux"

    # 生成一个子进程，执行cmd命令
    p = subprocess.Popen(
        cmd,
        bufsize=32768,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=True,
        preexec_fn=os.setsid if is_linux else None,
    )

    # 判断子进程执行时间是否超时
    t_beginning = time.time()
    seconds_passed = 0

    # 计算循环次数
    time_gap = 0.01
    loop = timeout * 100 + 200

    str_std_output = ""
    for loop_index in range(0, loop):
        # 检查子进程是否结束
        str_std_output = str_std_output + p.stdout.read().decode(
            "utf-8", errors="ignore"
        )
        if p.poll() is not None:
            break
        seconds_passed = time.time() - t_beginning

        if timeout and seconds_passed > timeout:
            # 杀掉命令进程
            if is_linux:
                os.killpg(p.pid, signal.SIGTERM)
            else:
                p.terminate()
            return False, p.stdout.readlines()
        time.sleep(time_gap)

    std_output_lines_last = []
    std_output_lines = str_std_output.split("\n")
    for i in std_output_lines:
        std_output_lines_last.append(i)
    if print_output_flag is True:
        print(_log_tail(str_std_output))

    if "Traceback" in str_std_output:
        print(_log_tail(str_std_output))
        return False, std_output_lines_last

    if p.returncode != 0:
        print(_log_tail(str_std_output))
        return False, std_output_lines_last
    return True, std_output_lines_last


def main():
    """创建xml主函数"""
    if len(sys.argv) < 3:
        print("[ERROR]:need least 2 parameters")
        sys.exit(1)

    work_dir = sys.argv[1].replace("\\", "/")
    cover_config = sys.argv[2].replace("\\", "/")
    cover_config_path = os.path.dirname(cover_config)

    # 获取工程覆盖率文件列表
    if not os.path.isfile(cover_config):
        print(f"[ERROR]:the {cover_config} is not exist")
        sys.exit(1)

    cover_code_list = []
    with open(cover_config, "rb", encoding="UTF-8") as file_handler:
        for each_line in file_handler:
            each_line_split = each_line.split(":")
            # prj_name = each_line_split[0].strip()
            cover_file = work_dir + "/" + each_line_split[1].strip()
            cover_list = read_cover_file(cover_file)
            cover_code_list = list(set(cover_code_list + cover_list))
    # 获取本次修改待打桩文件列表
    code_path_list = []
    os.chdir(CURRENT_DIR)
    if not os.path.isfile("changed_files_list"):
        print(f"[ERROR]:the changed_files_list is not exist in {CURRENT_DIR}")
        sys.exit(1)
    with open("changed_files_list", encoding="UTF-8") as file_handler:
        for each_line in file_handler:
            each_line_split = each_line.split(":")
            changed_file = each_line.split(":", "/").strip()
            if changed_file in cover_code_list:
                if not each_line_split[0] in code_path_list:
                    code_path_list.append(each_line_split[0])

    if len(code_path_list) == 0:
        print("[INFO]:no cover remote change,no need  run hutaf")
        sys.exit(2)

    # 获取仓文件变更列表
    changed_file_dict = {}
    for code_path in code_path_list:
        code_dir = work_dir + "/" + code_path
        os.chdir(code_dir)
        status, output = execute("git difftool --extcmd=diff HEAD~1 HEAD --name-status")

        if not status:
            print("ERROR:", output)
            sys.exit(1)

        changed_file_list = output
        files_dict = {}
        for each_file in changed_file_list:
            if each_file != "":
                file_split = each_file.split("\t")
                files_dict[file_split[1]] = file_split[0]
        changed_file_dict[code_path] = files_dict

    print(changed_file_dict)

    os.chdir(cover_config_path)
    proj_name = cover_config_path.split("/")[-1]

    xml_name = proj_name + "_change.xml"
    if os.path.isfile(xml_name):
        os.remove(xml_name)
    nend_run_flag = False
    # 生成变更ml模板
    doc = Dom.Document()
    root_node = doc.createElement("Version")
    root_node.setAttribute("Name", "")
    root_node.setAttribute("Type", "")
    doc.appendChild(root_node)

    proj_node = doc.createElement("project")
    proj_node.setAttribute("Name", "Story-000")
    proj_node.setAttribute("Type", "")
    root_node.appendChild(proj_node)

    # 填写变更信息
    for code_path, files_dict in list(changed_file_dict.items()):
        code_dir = work_dir + "/" + code_path
        os.chdir(code_dir)

        for file, attribute in list(files_dict.items()):
            cover_file = code_path + "/" + file
            if cover_file in cover_code_list:
                nend_run_flag = True
                file_name = file.split("/")[-1]
                file_path = code_dir + "/" + file
                patch_name = file_name.split(".")[0] + ".patch"
                patch_path = code_dir + "/" + patch_name
                # 生成patch

                cmd = (
                    "git difftool --execmd=diff HEAD HEAD~1 --no-prompt "
                    + file
                    + " >"
                    + patch_name
                )
                status, output = execute(cmd)
                if not status:
                    print("[ERROR]:", output)
                    sys.exit(1)

                file_node = doc.createElement("file")
                file_node.setAttribute("Name", file_name)
                file_node.setAttribute("path", file_path)
                file_node.setAttribute("patch", patch_path)
                proj_node.appendChild(file_node)

    os.chdir(cover_config_path)
    with open(xml_name, "wb", encoding="UTF-8") as xml_file:
        xml_file.write(doc.toprettyxml(indent="\t", newl="\n"))
    if nend_run_flag:
        sys.exit(0)
    else:
        print("[INFO]:no changed file for cover,do not nend run hutaf")
        sys.exit(2)


if __name__ == "__main__":
    main()
