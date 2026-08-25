"""检查pr中的修改文件是否在class_rule.yaml中"""

import os
import sys
import shutil
import cilog as CI_LOG
import multiprocessing

THIS_FILE_NAME = __file__
THIS_FILE_PATH = os.path.dirname(os.path.realpath(THIS_FILE_NAME))
sys.path.append(os.path.join(THIS_FILE_PATH, ".."))


def scanfile(file_name, empty_total_file_tmp, empty_total_file):
    """单个文件扫描"""
    cmd = f'file -i {file_name} | fgrep inode/x-empty > {empty_total_file_tmp}'
    os.system(command=cmd)
    os.system(command=f"cat {empty_total_file_tmp} >> {empty_total_file}")


def scandir(scan_dir, empty_total_file_tmp, empty_total_file):
    """目录级扫描"""
    scan_cmd = '''find %s -type f ! path "*/.git/*" ! -path "*/.mm/*" ! -path "*/.repo/*" ! -path "*/__init__.py" ! -path "./output/*"
 -exec file -i {} \; | fgrep inode/x-empty > %s''' % (scan_dir, empty_total_file_tmp)
    CI_LOG.loginfo(THIS_FILE_NAME, "emptydir cmd: %s", scan_cmd)
    os.system(command=scan_cmd)
    os.system(command=f"cat {empty_total_file_tmp} >> {empty_total_file}")


def set_emptyfile_cmd(res_path, root_dir):
    """
    全量的扫描，暂时用不着
    res_path:扫描结果存放路径;
    root_dir:代码存放路径.
    """
    empty_total_file = os.path.join(res_path, "emptyfile_Total.txt")
    if os.path.exists(empty_total_file):
        shutil.rmtree(empty_total_file)
    emptyfile_pool = multiprocessing.Pool(processes=5)
    for fd in os.listdir(root_dir):
        empty_total_file_tmp = os.path.join(
            res_path, f"emptyfile_Total-{fd}.txt")
        if (fd == ".repo" or fd == "open_source"
            or fd == "llt" or fd == "hlt"
            or fd == "output" or fd == "tests"
                or fd == "third_party" or fd == "tmp"):
            continue
        fd = os.path.join(root_dir, fd)
        if os.path.isfile(fd):
            emptyfile_pool.apply_async(
                scanfile, (fd, empty_total_file_tmp, empty_total_file))
        elif os.path.isdir(fd):
            emptyfile_pool.apply_async(
                scandir, (fd, empty_total_file_tmp, empty_total_file))
    emptyfile_pool.close()
    emptyfile_pool.join()

    return True


def main(workspace, pr_filelist):
    """门禁只需要针对修改的文件进行检查"""
    empty_total_file_tmp = os.path.join(workspace,"tmp.txt")
    empty_total_file = os.path.join(workspace, "emptyfile_Total.txt")
    with open(pr_filelist, "r", encoding="utf-8") as tmp_file:
        file_content = tmp_file.readlines()
        for file_name in file_content:
            file_name=file_name.strip()
            file_path=os.path.join(workspace,file_name)
            if os.path.exists(file_path):
                scanfile(file_path,empty_total_file_tmp,empty_total_file)
    if os.path.exists(empty_total_file):
        file_size = os.path.getsize(empty_total_file)
        if file_size == 0:
            CI_LOG.loginfo(THIS_FILE_NAME, "emptyfile_Total.txt is empty,check pass")
            sys.exit(0)
        else:
            results = []
            with open(empty_total_file, "r", encoding="utf-8") as tmp:
                contents = tmp.readlines()
                for content in contents:
                    results.append(content.split(":")[0].split(workspace+"/")[1])
            CI_LOG.loginfo(THIS_FILE_NAME,"list empty files: %s", results)
            sys.exit(1)


if __name__ == "__main__":
    #参数：
    # WORKSPACE:代码存放路径
    # PR_FILELIST:pr_file的存放地址
    WORKSPACE=sys.argv[1]
    PR_FILELIST=sys.argv[2]
    main(WORKSPACE,PR_FILELIST)