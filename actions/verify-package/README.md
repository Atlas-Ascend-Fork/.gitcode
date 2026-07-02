# verify-package

校验编译产物包能否正常安装与卸载：

1. 在 `package_path` 下查找首个 `*.${package_type}` 包并执行 `--full` 安装。
2. 检查安装日志是否包含 `ERROR`。
3. 执行 `--uninstall` 卸载并校验安装目录是否清空。

## 输入参数

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `workspace` | 是 | - | 代码检出根目录 |
| `package_path` | 否 | `build_out` | 包所在目录 |
| `package_type` | 否 | `run` | 包扩展名类型 |

## 使用示例

```yaml
- name: verify_package
  uses: cann/.gitcode/actions/verify-package@master
  with:
    workspace: ${{ steps.process_checkout.outputs.path }}
```
