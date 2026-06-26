# rk3576开发

这是一个面向 KICKPI K7 / RK3576 学习和开发的项目工作区。当前阶段先建立工程规范，后续再逐步补齐 SDK 编译、烧录、驱动调试和应用开发内容。

## 当前状态

- 本项目已经初始化为 Git 仓库，当前主分支为 `main`。
- GitHub 远端仓库：`https://github.com/ZcZzc02/linux-board-projects.git`
- 本地 `main` 已同步到 `origin/main`。
- Git 已安装在 `D:\tools\git`。如果 PowerShell 找不到裸 `git` 命令，可以使用 `D:\tools\git\cmd\git.exe`，或把 `D:\tools\git\cmd` 加入系统 PATH。
- 根目录包含 SDK、文档和备份压缩包等大文件来源，提交前必须确认 `.gitignore` 生效，避免把 SDK、镜像、压缩包和 build 输出提交进仓库。

## 目录结构

```text
.
├── AGENTS.md
├── README.md
├── docs/
│   ├── setup.md
│   ├── build.md
│   ├── flash.md
│   ├── debug.md
│   └── reproduce.md
├── scripts/
│   ├── check_env.sh
│   ├── build.sh
│   ├── flash.sh
│   └── run_test.sh
├── .gitattributes
└── .gitignore
```

## 快速开始

先确认 Git 可用：

```powershell
& 'D:\tools\git\cmd\git.exe' --version
& 'D:\tools\git\cmd\git.exe' status --short --branch
```

如果希望直接使用 `git` 命令，请把 `D:\tools\git\cmd` 加入系统 PATH，然后重新打开 PowerShell。

在 Linux 或 WSL 环境中检查开发工具：

```bash
./scripts/check_env.sh
```

当前脚本只提供基础检查和统一入口。真实 SDK 编译、烧录、测试命令需要在确认板卡、SDK、工具链和镜像布局后补齐。

## 文档入口

- 环境搭建：[`docs/setup.md`](docs/setup.md)
- 编译流程：[`docs/build.md`](docs/build.md)
- 烧录流程：[`docs/flash.md`](docs/flash.md)
- 调试方法：[`docs/debug.md`](docs/debug.md)
- 跨电脑复现：[`docs/reproduce.md`](docs/reproduce.md)
- K7 网关接口约定：[`docs/INTERFACE_SPEC.md`](docs/INTERFACE_SPEC.md)

## K7 Linux 网关

K7 Linux 网关工程位于：

```text
2.1.Linux网关/k7-gateway
```

当前第一阶段提供 UART3/E22/4G-5G 基线自检、E22 配置读取、LoRa 帧解析和离线测试工具。进入工程后可查看 [`2.1.Linux网关/k7-gateway/README.md`](2.1.Linux网关/k7-gateway/README.md)。

## Git 工作流

每次开始任务：

```bash
git status --short --branch
```

涉及多个文件或环境配置时，先建分支：

```bash
git switch -c chore/short-task-name
```

完成一个可验证小目标后：

```bash
git diff
git add <files>
git commit -m "docs: describe the change"
```

不要提交密码、token、私钥、WiFi 密码、API key、SDK、大型镜像、build 输出或压缩包。
