"""ci log调用脚本"""

import time
import inspect

THIS_FILE_NAME = __file__


def cilog_get_timestamp():
    """log时间戳"""
    return time.strftime("%Y%m%d_%H%M%S", time.localtime())


def cilog_print_element(cilog_element):
    """ci log元素"""
    print("[" + cilog_element + "]", end=" ")


def cilog_logmsg(log_level, filename, line_no, log_msg, *log_paras):
    """log信息"""
    log_timestamp = cilog_get_timestamp()
    cilog_print_element(log_timestamp)
    cilog_print_element(log_level)
    cilog_print_element(filename)
    cilog_print_element(str(line_no))
    print(log_msg % log_paras[0])


def cilog_error(filename, log_msg, *log_paras):
    """错误log"""
    line_no = inspect.currentframe().f_back.f_lineno
    cilog_logmsg("ERROR", filename, line_no, log_msg, log_paras)


def cilog_warning(filename, log_msg, *log_paras):
    """警告log"""
    line_no = inspect.currentframe().f_back.f_lineno
    cilog_logmsg("WARNING", filename, line_no, log_msg, log_paras)


def cilog_info(filename, log_msg, *log_paras):
    """信息log"""
    line_no = inspect.currentframe().f_back.f_lineno
    cilog_logmsg("INFO", filename, line_no, log_msg, log_paras)


if __name__ == "__main__":
    i = 0
    while i < 3:
        cilog_error(THIS_FILE_NAME, "%s say %s %d times", "I", "Hello world", i)
        i += 1
