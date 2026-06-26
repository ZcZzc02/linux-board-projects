# 开发环境搭建

本文档记录本项目需要的电脑系统、开发板、SDK、内核、工具链和常用软件版本。后续每次环境变化都应补充到这里。

## 基本信息

| 项目 | 当前记录 |
| --- | --- |
| 电脑系统版本 | 待补充 |
| 开发板型号 | KICKPI K7，待确认 |
| 芯片型号 | RK3576，待确认 |
| SDK 版本 | 待补充 |
| 内核版本 | 待补充 |
| 交叉编译工具链版本 | 待补充 |
| GCC 版本 | 待补充 |
| CMake 版本 | 待补充 |
| Python 版本 | 待补充 |

## Windows 侧基础工具

建议安装：

- Git for Windows
- VS Code 或 Cursor
- Obsidian
- 7-Zip
- 串口工具，例如 MobaXterm、Tabby、PuTTY 或 Windows Terminal + 串口插件

安装 Git 后确认：

```powershell
& 'D:\tools\git\cmd\git.exe' --version
& 'D:\tools\git\cmd\git.exe' status --short --branch
```

当前 Git 安装路径：

```text
D:\tools\git
```

建议把下面路径加入系统 PATH，之后可以直接使用 `git`：

```text
D:\tools\git\cmd
```

## Linux / WSL 侧基础工具

建议在 Ubuntu 或 WSL Ubuntu 中安装：

```bash
sudo apt update
sudo apt install -y git make gcc g++ cmake python3 python3-pip unzip xz-utils bzip2 file tree
```

检查环境：

```bash
./scripts/check_env.sh
```

## 待确认事项

- SDK 的真实编译入口。
- 内核源码路径。
- U-Boot 源码路径。
- 根文件系统构建方式。
- 烧录工具和镜像文件命名规则。
