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
        codecheck_ip='https://apig.openlibing.com',
        gitxx_api='https://api.gitcode.com/api/v5/repos',
        codecheck_prefix='/openlibing-sca'
    ):
        self.pr_url = None
        self.scanId = None
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
        self.project_name = "CANN"
        self.MESSAGE = None 

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
            self.pr_url = f"{self.gitcode_domain}/{self.org_name}/{self.repository_name}/pull/{self.pr_id}"


    def _get_create_task(self):
        try:
            task_url = f"{self.codecheck_ip}{self.codecheck_prefix}/scan/pr"
            params = {
                "projectName": self.project_name,
                "prUrl": self.pr_url,
            }
            # 创建请求对象
            method = 'POST'  # 根据实际API调整
            headers = {"Content-Type": "application/json"}
            request = signer.HttpRequest(method, task_url, headers, json.dumps(params))
            # 初始化签名器并设置密钥
            sig = signer.Signer()
            sig.Key = self.access_key
            sig.Secret = self.secret_access_key
            sig.Sign(request)
            # 发送请求
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
                response = responsetemp.json()
            except ValueError as e:
                logging.error(f"无法解析JSON响应: {e}")
                logging.error(f'[sca check {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 无法解析JSON响应 '
                  f'\n[{e}]')
            if response.get('code') == 200:
                self.scanId = response.get('data')
                logging.info(f"self.scanId: {self.scanId}")
                logging.info(f'[sca check {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] create task success')
            else:
                logging.error(f'[sca check {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] create task failed '
                      f'\n[{response.get("error_msg")}]')
                self.MESSAGE=response.get("error_msg")
        except Exception as e:
                 logging.error(f'[sca check {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] create task error '
                  f'\n[{e}]')
                 self.MESSAG = e

    # def _read_task_json(self):
    #     package_path = f"https://ascend-ci.obs.cn-north-4.myhuaweicloud.com/{self.repository_name}/package/{self.pr_id}/SCA.json"
    #     try:
    #         os.system(command=f"wget {package_path}")
    #     except Exception as e:
    #         logging.error(e)
    #     if os.path.exists("SCA.json"):
    #         os.system(command="mv SCA.json result.json")
    #         with open("result.json", 'r', encoding='utf-8') as f:
    #             result=json.load(f)
    #             if "commit_id" not in result or "SCA" not in result or result["SCA"] is None:
    #                 return
    #             if "SCA_result" not in result or result["SCA_result"] != "pass":
    #                 return
    #             if self.commit_id == result["commit_id"]:
    #                 logging.info("no commit, no need to run")
    #                 sys.exit(0)

    # def _write_task_json(self):
    #     if self.MESSAGE :
    #         self.report_url = self.MESSAGE
    #     data = {
    #         "SCA":self.report_url,
    #         "commit_id": self.commit_id,
    #         "SCA_result":self.result
    #     }
    #     self._set_pipeline_output("sca_link", self.report_url)
    #     package_path = f"https://ascend-ci.obs.cn-north-4.myhuaweicloud.com/{self.repository_name}/package/{self.pr_id}/SCA.json"
    #     time.sleep(30)
    #     print(f"data:{data}")
    #     try:
    #         os.system(command=f"wget {package_path}")
    #     except Exception as e:
    #         logging.error(e)
    #     if os.path.exists("SCA.json"):
    #         with open("SCA.json", 'r', encoding='utf-8') as f:
    #             result=json.load(f)
    #             result.update(data)
    #         with open("SCA.json", "w", encoding="utf-8") as f:
    #             json.dump(result, f)
    #     else:
    #         with open("SCA.json", "w", encoding="utf-8") as f:
    #             json.dump(data, f)
    #     with open("SCA.json", "r", encoding="utf-8") as f:
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
            time.sleep(10)
            expire_time = expire_time + 15
            try:
                status_url = f'{self.codecheck_ip}{self.codecheck_prefix}/scan/result?scanId=' + self.scanId;
                logging.info(f"self.scanId: {self.scanId}")
                # 初始化签名器并设置密钥
                sig = signer.Signer()
                sig.Key = self.access_key_get
                sig.Secret = self.secret_access_key_get
                method = "GET"
                headers = {"host": "apig.openlibing.com"}
                # sign
                r = signer.HttpRequest(method, status_url, headers)
                sig.Sign(r)
                responsetemp = requests.request(method, status_url, headers=r.headers)
                # 输出结果
                logging.info(f"响应状态码: {responsetemp.status_code}")
                logging.info(f"响应内容: {responsetemp.text}")  # 查看实际返回的内容   
                response_json = responsetemp.json()

                logging.info(
                    f"[code sca {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] response: {response_json}"
                )
                if response_json.get("code") == 200:
                    data = response_json.get("data")
                    state = data.get("state")
                    self.report_url = data.get("prResult")
                    if state == "success":
                        if data.get("unconfirmedFileNum") == 0:
                            self.result = "pass"
                        elif data.get("unconfirmedFileNum") > 0:
                            self.result = "no pass"
                        logging.info(
                            f"[code sca {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Task success"
                        )
                        break
                    elif state == "scanning":
                        expire_time = expire_time + 20
                        logging.info(
                            f"[code sca {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Task is still running"
                        )
                        continue
                    elif state == "failure":
                        logging.error(
                            f"[code sca {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Task failure, state: {state}, data: {data}"
                        )
                        self.MESSAGE = data
                else:
                    logging.error(
                        f"[code sca {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Interface failure, error code: {response_json.get('code')}, message: {response_json.get('error_msg')}."
                    )
                    self.MESSAGE = response_json.get('error_msg')
                    break
            except Exception as e:
                logging.error(
                    f"[code sca {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Task failed, error: {e}."
                )
                break
        else:
            logging.error("Task timeout after 600 seconds.")
            self.result = "no pass"
    def run(self):
        self._get_pr_url()

        if not self.pr_url:
            logging.error(
                f"[code sca {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] pr is not exist."
            )
            sys.exit(-1)
        # self._read_task_json()
        self._get_create_task()
        if not self.scanId:
            self.result = "failed"
            logging.error(
                f"[code sca {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] sca create task failed."
            )
            logging.info(f"majun_url: {self.report_url},\n")
            # self._write_task_json()
            sys.exit(-1)
        self._get_task_result()
        # self._write_task_json()
        if not self.report_url or self.result is None:
            self.result = "failed"
            logging.error(
                f"[code sca {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] sca get task result failed. timeout after multiple attempts."
            )
            # self._write_task_json()
            sys.exit(-1)
        lresult = "pass" if self.result == "pass" else "no pass"
        logging.info(json.dumps({"result": lresult, "url": self.report_url}))
        print(self.report_url)
        if lresult == "no pass":
            logging.error(
                f"[code sca {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] code scan result: no pass."
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
    parser.add_argument("--commit_id", type=str, required=True, help="Commit ID")
    return parser.parse_args()


if __name__ == "__main__":
    args = init_args()
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
    )
    codecheck.run()
