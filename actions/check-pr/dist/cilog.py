"""ci通用LOG"""

import time
import inspect

THIS_FILE_NAME = __file__


def get_timestamp():
    """获取时间"""
    return time.strftime("%Y%m%d_%H%M%S", time.localtime())


def print_element(cilog_element):
    """打印元素"""
    print("[" + cilog_element + "]", end=" ")


def logmsg(log_level, filename, line_no, log_msg, *log_paras):
    """log信息"""
    log_timestamp = get_timestamp()
    print_element(log_timestamp)
    print_element(log_level)
    print_element(filename)
    print_element(str(line_no))
    print(log_msg % log_paras[0])


def logerror(filename, log_msg, *log_paras):
    """错误log"""
    line_no = inspect.currentframe().f_back.f_lineno
    logmsg("ERROR", filename, line_no, log_msg, log_paras)


def logwarning(filename, log_msg, *log_paras):
    """警告log"""
    line_no = inspect.currentframe().f_back.f_lineno
    logmsg("WARNING", filename, line_no, log_msg, log_paras)


def loginfo(filename, log_msg, *log_paras):
    """信息log"""
    line_no = inspect.currentframe().f_back.f_lineno
    logmsg("INFO", filename, line_no, log_msg, log_paras)


if __name__ == "__main__":
    i = 0
    while i < 3:
        logerror(THIS_FILE_NAME, "%s say %s %d times", "I", "Hello world", i)
        i += 1
