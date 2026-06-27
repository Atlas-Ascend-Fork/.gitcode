import os
import sys
import subprocess
from abc import ABC, abstractmethod

CURRENT_DIR_PATH = os.path.dirname(os.path.abspath(__file__))

class CodeCheckerBaseClass(ABC):
    # 工程路径相关参数
    # 当前CI仓路径
    CI_ROOT_PATH = os.path.abspath(os.path.join(CURRENT_DIR_PATH, '..', '..'))
    WORKSPACE_PATH = os.path.abspath(os.path.join(CI_ROOT_PATH, '..'))

    @staticmethod
    def run_cmd(cmd, cwd:str=WORKSPACE_PATH, shell:bool=False, env:dict=None, capture_output:bool=False):
        try:
            if capture_output:
                if env is None:
                    env = os.environ.copy()
                env['LANG'] = 'C.UTF-8'
                env['LC_ALL'] = 'C.UTF-8'
                env['PYTHONIOENCODING'] = 'utf-8'
                
                # 使用二进制模式捕获输出，避免自动解码问题
                result = subprocess.run(cmd, cwd=cwd, shell=shell, env=env, 
                                       capture_output=True, text=False)
                
                encoding = 'utf-8'
                try:
                    stdout = result.stdout.decode(encoding)
                except UnicodeDecodeError:
                    # 如果 UTF-8 解码失败，尝试 GBK
                    stdout = result.stdout.decode('gbk', errors='replace')
                
                try:
                    stderr = result.stderr.decode(encoding)
                except UnicodeDecodeError:
                    stderr = result.stderr.decode('gbk', errors='replace')
                
                result.stdout = stdout
                result.stderr = stderr
                
                print(f"cmd执行成功：+ {cmd}")
                return result
            else:
                # 如果命令成功（返回码为0），不返回任何内容
                subprocess.check_call(cmd, cwd=cwd, shell=shell, env=env)
                print(f"cmd执行成功：+ {cmd}")
        except subprocess.CalledProcessError as e:
            print(f"在{cwd}目录cmd命令失败: {e}")
        except Exception as e:
            print(f"执行命令时发生未知错误: {e}")

    @abstractmethod
    def run(self):
        pass