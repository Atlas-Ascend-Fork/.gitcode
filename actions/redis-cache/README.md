# redis-cache

配置 ccache + Redis 二级缓存环境，用于加速 UT 编译。

执行以下操作：
- 设置 ccache 环境变量（Redis 二级存储、编译器检查模式等）
- 安装 redis-tools、libhiredis-dev 等依赖
- 验证 Redis 连接
- 重置 ccache 统计

## 输入参数

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `workspace` | 否 | 脚本目录 | 工作目录 |

## 使用示例

```yaml
- name: redis-cache
  uses: cann/.gitcode/actions/redis-cache@master
```
