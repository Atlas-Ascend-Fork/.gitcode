# 安全声明

## 运行用户建议

本仓库为 CANN 社区的 CI 共享仓，包含 GitCode Actions 工作流（pre/post/codecheck）、自定义 Action（revise-img、get-pr、check-pr、api-check 等）、Issue 模板、镜像配置与冒烟配置。CI 工作流中使用的 token/secrets（AK/SK、TESTTOKEN、GIT_TOKEN 等）由各使用仓库通过平台 Secrets 机制配置，本仓不持有任何凭证。

## 文件权限控制

基于安全性角度考虑，建议用户在主机（包括宿主机）及容器中设置运行系统 umask 值为 0027 及以上，保障新增文件夹默认最高权限为 750，新增文件默认最高权限为 640。

建议用户对个人隐私数据、商业资产、源文件和开发过程中保存的各类文件等敏感内容做好权限控制等安全措施。

## 构建安全声明

【必改】在源码编译安装本项目时，需要您自行编译，编译过程中会生成一些中间文件，建议您在编译完成后，对中间文件做好权限控制，以保证文件安全。（纯文档仓可写：本仓库不涉及编译构建。）

## 运行安全声明

【必改】在运行异常时会退出进程并打印报错信息，建议根据报错提示定位具体错误原因。（按实际运行行为描述。）

## 公网地址声明

本项目代码中包含的公网地址声明如下所示：

| 类型 | 开源代码地址 | 文件名 | 公网IP地址/公网URL地址/域名/邮箱地址/压缩文件地址 | 用途说明 |
| :---: | :---: | :---: | :--- | :--- |
| CI服务 | 不涉及 | .gitcode/workflows/*.yml | https://obs.cn-north-4.myhuaweicloud.com | OBS 制品上传下载端点 |
| CI服务 | 不涉及 | actions/pre-pipeline/dist/*.py | https://api.gitcode.com | GitCode API 调用 |
| 【不涉及则整行写"不涉及"】 | | | | |

## 密码/密钥/敏感信息声明

本仓库不涉及密码、密钥、证书等敏感信息的存储与分发。CI 所需 secrets（AK/SK、TESTTOKEN 等）通过平台 Secrets 机制在各使用仓库配置，本仓代码仅通过 ${{ secrets.* }} 引用。

---

# 漏洞机制说明

[漏洞管理](https://gitcode.com/cann/community/blob/master/security/security.md)

如需上报 CANN 社区相关安全漏洞，请通过 [security SIG 邮箱](mailto:security@cann.osinfra.cn) 上报，建议使用[安全团队邮箱 PGP 公钥](https://gitcode.com/cann/community/blob/master/security/PGP/CANN_public_key.asc)加密邮件内容。上报内容要求与处理流程详见上述漏洞管理文档。

---
