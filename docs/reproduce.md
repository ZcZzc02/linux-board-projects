# 项目复现文档

本文档用于保证项目能在另一台电脑上复现。每次跑通新的构建、烧录或调试流程，都应更新这里。

## 1. 电脑系统版本

待补充。

## 2. 开发板型号

KICKPI K7，待确认。

## 3. 芯片型号

RK3576，待确认。

## 4. SDK 版本

待补充。

## 5. 内核版本

待补充。

## 6. 交叉编译工具链版本

待补充。

## 7. gcc / cmake / python 等环境版本

记录命令：

```bash
gcc --version
cmake --version
python3 --version
make --version
git --version
```

## 8. 需要安装的软件

待补充。基础软件见 `docs/setup.md`。

## 9. 编译命令

待补充。统一入口：

```bash
./scripts/build.sh
```

## 10. 烧录命令

待补充。统一入口：

```bash
./scripts/flash.sh
```

## 11. 运行命令

待补充。

## 12. 成功现象

待补充。

## 13. 常见错误和解决方法

| 错误现象 | 原因 | 解决方法 |
| --- | --- | --- |
| Git 命令不可用 | Git 未安装或 PATH 未配置 | 安装 Git for Windows 并重开终端 |
| 脚本不能执行 | 没有执行权限或在 Windows PowerShell 直接运行 `.sh` | 在 Linux/WSL 中执行，必要时 `chmod +x scripts/*.sh` |
