# 编译流程

本文档用于记录 RK3576 / KICKPI K7 项目的编译流程。当前阶段尚未确认真实 SDK 编译命令，因此只建立统一入口。

## 编译前检查

```bash
./scripts/check_env.sh
```

## 统一编译入口

```bash
./scripts/build.sh
```

当前 `scripts/build.sh` 需要通过 `BUILD_CMD` 指定真实命令，例如：

```bash
BUILD_CMD="make" ./scripts/build.sh
```

实际 SDK 编译命令确认后，应改为文档化的固定流程。

## 需要记录的信息

- SDK 路径：
- 编译入口脚本：
- defconfig：
- 目标板配置：
- 输出目录：
- 成功产物：
- 编译耗时：

## 成功现象

待补充。应记录成功日志关键字和生成的镜像文件路径。

## 常见错误

| 错误现象 | 可能原因 | 解决方法 |
| --- | --- | --- |
| 找不到交叉编译器 | 工具链未安装或 PATH 未配置 | 补充工具链路径并重新执行 |
| 权限不足 | 脚本没有执行权限 | `chmod +x scripts/*.sh` |
| 磁盘空间不足 | SDK/build 输出较大 | 清理 build 输出或换大磁盘 |
