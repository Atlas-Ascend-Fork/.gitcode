# -*- coding: utf-8 -*-
import time
import datetime
import hmac
import hashlib
import base64
import os
import sys
import requests
import json
import argparse
import logging
import subprocess

from apig_sdk import signer

logging.basicConfig(level=logging.INFO,format="%(asctime)s - %(levelname)s %(message)s" )


class CodeCheck(object):
    def __init__(
        self,
        access_key,
        secret_access_key,
        access_key_get,
        secret_access_key_get,
        org_name,
        repository_name,
        pr_id,
        commit_id,
        codecheck_ip="https://apig.openlibing.com",
        gitxx_api="https://api.gitcode.com/api/v5/repos",
        project_name="CANN",
        codecheck_prefix="/openlibing-codecheck/ci-portal/webhook/codecheck/v1/task"
    ):
        self.pr_url = None
        self.result = None
        self.report_url = None
        self.number = None
        self.timestamp = None
        self.sign = None
        self.access_key = access_key
        self.secret_access_key = secret_access_key
        self.access_key_get = access_key_get
        self.secret_access_key_get = secret_access_key_get
        self.org_name = org_name
        self.repository_name = repository_name
        self.pr_id = pr_id
        self.commit_id = commit_id
        self.codecheck_ip = codecheck_ip
        self.gitxx_api = gitxx_api
        self.codecheck_prefix = codecheck_prefix
        self.gitcode_domain = "https://gitcode.com"
        self.repo_type = self._determine_repo_type()
        self.project_name = project_name
        self.uuid = None
        self.taskid = None
        self.MESSAGE = None
        self.json_name="codecheck.json"
        self.env_dist = os.environ
        self.gitcode_output = self.env_dist.get("ATOMGIT_OUTPUT")

    def _determine_repo_type(self):
        repo_type = None
        if "gitee" in self.gitxx_api:
            repo_type = "gitee"
        elif "gitcode" in self.gitxx_api:
            repo_type = "gitcode"
        return repo_type

    def _get_pr_url(self):
        if self.repo_type == "gitee":
            self.pr_url = f"{self.gitcode_domain}/{self.org_name}/{self.repository_name}/pulls/{self.pr_id}"
        elif "gitcode" in self.gitxx_api:
            self.pr_url = f"{self.gitcode_domain}/{self.org_name}/{self.repository_name}/merge_requests/{self.pr_id}"

    def _get_create_task(self):
        try:
            task_url = f"{self.codecheck_ip}{self.codecheck_prefix}"
            if os.getenv("task_name") == "Code_Check_DT":
                logging.info(f"this is codestyle or dt task")
                params = {
                    "projectName": self.project_name,
                    "pr_url": self.pr_url,
                    "codecheck_parent_task_id": os.getenv("codecheck_parent_task_id"),
                    "remark": os.getenv("remark")
                }
            else:
                params = {
                    "projectName": self.project_name,
                    "pr_url": self.pr_url,
                }
            headers = {
                "Content-Type": "application/json",
            }
            method = 'POST'  # 根据实际API调整
            headers = {"Content-Type": "application/json"}
            request = signer.HttpRequest(method, task_url, headers, json.dumps(params))
            # 初始化签名器并设置密钥
            sig = signer.Signer()
            sig.Key = self.access_key
            sig.Secret = self.secret_access_key
            sig.Sign(request)
            responsetemp = requests.request(
                request.method,
                request.scheme + "://" + request.host + request.uri,
                headers=request.headers,
                data=request.body
            )
            logging.info(f"响应状态码: {responsetemp.status_code}")
            logging.info(f"响应内容: {responsetemp.text}")  # 查看实际返回的内容
            # 再尝试解析JSON
            try:
                response_json = responsetemp.json()
            except ValueError as e:
                logging.error(f"无法解析JSON响应: {e}")
                return
            if response_json.get("code") == "200":
                self.uuid = response_json.get("uuid")
                self.taskid = response_json.get("task_id")
                logging.info(
                    f"[codecheck {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Create task success"
                )
            else:
                logging.error(
                    f"[codecheck {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Create task failed, error code: {response_json.get('code')}, message: {response_json.get('error_msg')}."
                )
                self.MESSAGE = response_json.get('error_msg')
        except Exception as e:
            logging.error(
                f"[codecheck {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Create task failed, error: {e}."
            )

    # def _read_task_json(self):
    #     package_path = f"https://ascend-ci.obs.cn-north-4.myhuaweicloud.com/{self.repository_name}/package/{self.pr_id}/{self.json_name}"
    #     try:
    #         os.system(command=f"wget {package_path}")
    #     except Exception as e:
    #         logging.error(e)
    #     if os.path.exists(self.json_name):
    #         os.system(command=f"mv {self.json_name} result.json")
    #         with open("result.json", 'r', encoding='utf-8') as f:
    #             result=json.load(f)
    #             if "commit_id" not in result or "codecheck" not in result or "codecheck_dt" not in result or "codecheck_codestyle" not in result \
    #                 or result["codecheck"] is None or result["codecheck_dt"] is None or result["codecheck_codestyle"] is None:
    #                 return
    #             if "codecheck_result" not in result or result["codecheck_result"] != "pass":
    #                 return
    #             if self.commit_id == result["commit_id"]:
    #                 logging.info("no commit, no need to run")
    #                 sys.exit(0)

    # def _write_task_json(self):
    #     if self.MESSAGE:
    #        self.report_url = self.MESSAGE 
    #     if os.getenv("remark") == "dt":
    #         data = {
    #             "codecheck_dt":self.report_url,
    #             "commit_id":self.commit_id,
    #             "codecheck_dt_result":self.result
    #         }
    #         self._set_pipeline_output("codecheck_dt_link", self.report_url)
    #         logging.info(f"this is codestyle task")
    #         self.json_name="codecheck_dt.json"
    #     elif os.getenv("remark") == "codestyle":
    #         data = {
    #             "codecheck_style":self.report_url,
    #             "commit_id":self.commit_id,
    #             "codecheck_codestyle_result":self.result
    #         }
    #         self._set_pipeline_output("codecheck_codestyle_link", self.report_url)
    #         logging.info(f"this is codestyle task")
    #         self.json_name="codecheck_style.json"
    #     else:
    #         data = {
    #             "codecheck":self.report_url,
    #             "commit_id":self.commit_id,
    #             "codecheck_result":self.result
    #         }
    #         self._set_pipeline_output("codecheck_link", self.report_url)
    #         self.json_name="codecheck.json"
    #     package_path = f"https://ascend-ci.obs.cn-north-4.myhuaweicloud.com/{self.repository_name}/package/{self.pr_id}/{self.json_name}"

    #     try:
    #         result = subprocess.run(
    #             ["wget", "-q", package_path],
    #             check=True,
    #             timeout=60
    #         )
    #         logging.info("下载成功！")
    #     except Exception as e:
    #         logging.warning(f"发生未知错误: {e}.")
    #     if os.path.exists(self.json_name):
    #         with open(self.json_name, 'r', encoding='utf-8') as f:
    #             result=json.load(f)
    #             result.update(data)
    #         with open(self.json_name, "w", encoding="utf-8") as f:
    #             json.dump(result, f)
    #     else:
    #         with open(self.json_name, "w", encoding="utf-8") as f:
    #             json.dump(data, f)
    #     with open(self.json_name, "r", encoding="utf-8") as f:
    #         result=json.load(f)
    #         print(f"write {result} success")
  
    def _set_pipeline_output(self, key, value):
        raw_path = os.getenv('CODEARTS_OUTPUT')
        logging.info(f"raw path is : {raw_path}")
        path = os.path.expandvars(raw_path)
        logging.info(f"path is : {path}")
        if path:
            with open(path, 'a') as f:
                f.write(f"{key}={value}\n")

    def _get_task_result(self):
        expire_time = 0
        while expire_time < 1800:
            time.sleep(30)
            expire_time += 30  # 修复超时计数
            try:
                # 构造带查询参数的 URL
                status_url = f"{self.codecheck_ip}{self.codecheck_prefix}/status"
                # 创建请求对象
                method = "POST"
                headers = {"Content-Type": "application/json"}
                params = {
                    "uuid": self.uuid,
                    "task_id": self.taskid
                }
                request = signer.HttpRequest(method, status_url, headers, json.dumps(params))
                # 初始化签名器并设置密钥
                sig = signer.Signer()
                sig.Key = self.access_key_get
                sig.Secret = self.secret_access_key_get

                sig.Sign(request)
                responsetemp = requests.request(
                    request.method,
                    request.scheme + "://" + request.host + request.uri,
                    headers=request.headers,
                    data=request.body
                )
                # 

                logging.info(f"状态码: {responsetemp.status_code}")
                logging.info(f"响应: {responsetemp.text}")

                if responsetemp.status_code != 200:
                    logging.error(f"HTTP Error: {responsetemp.status_code}")
                    break

                response_json = responsetemp.json()

                if response_json.get("code") == "200":
                    state = response_json.get("state")
                    self.report_url = response_json.get("data")
                    self.result = state
                    if state == "pass":
                        logging.info(
                            f"[codecheck {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Task success"
                        )
                    elif state == "no pass":
                        logging.info(
                            f"[codecheck {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Task failed"
                        )
                    break

                elif response_json.get("code") == "100":
                    logging.info(
                        f"[codecheck {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Task still running, please wait...."
                    )
                elif response_json.get("code") == "500":
                    if response_json.get('msg'):
                        self.MESSAGE = response_json.get('msg')
                    elif response_json.get('error_msg'):
                        self.MESSAGE = response_json.get('error_msg')
                    logging.error(
                        f"[codecheck {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Get task status failed, error: {self.MESSAGE}."
                    )
                    break
            except Exception as e:
                logging.error(
                    f"[codecheck {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Task failed, error: {e}."
                )
                break
        else:
            # 超时（while 正常结束）
            logging.error("Task timeout after 30 minutes.")
            self.result = "no pass"

    def _write_summary(self, result):
        if result == "pass":
            return  # 成功不输出步骤摘要
        summary_path = os.getenv("ATOMGIT_STEP_SUMMARY")
        if not summary_path:
            return
        icon = "✅" if result == "pass" else "❌"
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(f"## {icon} 代码检查 (CodeCheck)\n\n")
            f.write(f"| 参数 | 值 |\n|------|------|\n")
            f.write(f"| 仓库 | {self.org_name}/{self.repository_name} |\n")
            f.write(f"| PR | #{self.pr_id} |\n")
            f.write(f"| 结果 | {icon} {result} |\n")
            if self.report_url:
                f.write(f"| 报告链接 | [查看报告]({self.report_url}) |\n")
            if self.MESSAGE:
                f.write(f"| 错误信息 | {self.MESSAGE} |\n")
            f.write(f"\n")

    def run(self):
        self._get_pr_url()

        if not self.pr_url:
            logging.error(
                f"[codecheck {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] pr is not exist."
            )
            sys.exit(-1)
        # self._read_task_json()
        self._get_create_task()

        if not self.taskid:
            logging.error(
                f"[codecheck {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] codecheck create task failed."
            )
            # self._write_task_json()
            self._write_summary("no pass")
            sys.exit(-1)
        self._get_task_result()
        # self._write_task_json()

        if not self.report_url or self.result is None:
            logging.error(
                f"[codecheck {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] codecheck get task result failed. timeout after multiple attempts."
            )

        lresult = "pass" if self.result == "pass" else "no pass"
        self._write_summary(lresult)
        logging.info(json.dumps({"result": lresult, "url": self.report_url}))
        os.system(
            command=f'echo "report_url={self.report_url}" >> {self.gitcode_output}'
        )
        if lresult == "no pass" and os.getenv("remark") != "codestyle":
            logging.info(
                f"[codecheck {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] codecheck result: no pass."
            )
            sys.exit(-1)


def init_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--access_key", type=str, required=True, help="Account ID for CodeScan API"
    )
    parser.add_argument(
        "--secret_access_key", type=str, required=True, help="Secret Key for CodeScan API"
    )
    parser.add_argument(
        "--access_key_get", type=str, required=True, help="Access Key for CodeScan API Get"
    )
    parser.add_argument(
        "--secret_access_key_get", type=str, required=True, help="Secret Key for CodeScan API Get"
    )
    parser.add_argument("--org_name", type=str, required=True, help="Organization name")
    parser.add_argument(
        "--repo", type=str, required=True, help="Repository name"
    )
    parser.add_argument(
        "--codecheck_ip",
        type=str,
        default="https://apig.openlibing.com",
        help="CodeCheck API endpoint",
    )
    parser.add_argument(
        "--gitxx_api",
        type=str,
        default="https://api.gitcode.com/api/v5/repos",
        help="Gitxx API endpoint",
    )
    parser.add_argument("--pr_id", type=int, required=True, help="Pull Request ID")
    parser.add_argument(
        "--project_name",
        type=str,
        default="CANN",
        help="Project name in Codecheck",
    )
    parser.add_argument("--commit_id", type=str, required=True, help="Commit ID")
    parser.add_argument(
        "--online",
        type=lambda x: x.lower() in ("true", "1", "yes"),
        default=False,
        help="Whether to run online scan (default: false)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = init_args()
    if not args.online:
        logging.info("online is false, skip codecheck scan")
        sys.exit(0)
    codecheck = CodeCheck(
        args.access_key,
        args.secret_access_key,
        args.access_key_get,
        args.secret_access_key_get,
        args.org_name,
        args.repo,
        args.pr_id,
        args.commit_id,
        args.codecheck_ip,
        args.gitxx_api,
        args.project_name
    )
    codecheck.run()

