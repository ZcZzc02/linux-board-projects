# AGENTS.md

本文件用于约束 Codex 或其他 AI 助手在本项目中的工作方式。项目目标不是临时跑通一次，而是保证代码可回溯、环境可复现、知识可沉淀。

## 当前项目

- 项目目录：`D:\rk3576开发`
- 暂定项目名：`rk3576开发`
- 目标平台：KICKPI K7 / RK3576 相关开发资料与工程
- 当前 Git 路径：`D:\tools\git\cmd\git.exe`
- 说明：具体 SDK 版本、内核版本、工具链版本需要在后续实际编译时补齐到 `docs/reproduce.md`。

## 每次开始任务必须先做

1. 执行 `git status --short --branch`，检查当前工作区状态。
2. 如果 `git` 命令不可用，优先尝试 `D:\tools\git\cmd\git.exe`，并提醒用户把 `D:\tools\git\cmd` 加入 PATH。
3. 如果目录没有完整可用的 Git 仓库，提醒用户初始化。仅存在空的 `.git` 目录不算完整仓库。

   ```bash
   git init
   git status --short --branch
   git add AGENTS.md README.md docs scripts .gitignore
   git commit -m "chore: initialize project structure"
   ```

4. 如果任务会修改多个文件、环境配置、驱动、脚本或文档，先创建独立分支：

   ```bash
   git switch -c chore/project-structure
   ```

## 修改原则

- 每次只完成一个明确的小目标。
- 优先阅读现有代码、文档和脚本，再做修改。
- 不做无关重构，不大范围移动文件。
- 不提交密码、token、私钥、WiFi 密码、API key。
- 不提交 SDK、大型镜像、build 输出、大压缩包。
- 对危险命令必须先解释风险，再征得确认后执行，例如：
  - `rm -rf`
  - `dd`
  - 格式化磁盘
  - 覆盖烧录设备
  - 修改系统关键目录

## 每个可验证小阶段的流程

1. 说明本次改了什么。
2. 说明为什么这么改。
3. 运行可用的编译、测试或检查命令。
4. 使用 `git diff` 检查改动。
5. 验证通过后再提交。
6. commit message 使用以下格式：
   - `feat: xxx`
   - `fix: xxx`
   - `docs: xxx`
   - `refactor: xxx`
   - `chore: xxx`
7. 更新 README 或 `docs/` 文档。
8. 只有用户明确要求时，才生成或写入适合放入 Obsidian 的中文阶段总结。

## 项目文档约定

- `README.md`：项目入口、目录说明、快速开始。
- `docs/setup.md`：开发环境安装和版本记录。
- `docs/build.md`：编译方法。
- `docs/flash.md`：烧录方法和风险提示。
- `docs/debug.md`：串口、日志、网络、常见调试方法。
- `docs/reproduce.md`：换电脑复现项目的完整步骤。
- `scripts/check_env.sh`：环境检查入口。
- `scripts/build.sh`：编译入口。
- `scripts/flash.sh`：烧录入口。
- `scripts/run_test.sh`：测试或验证入口。

## Obsidian 沉淀约定

默认不自动生成 Obsidian 总结。只有用户明确要求“写 Obsidian 总结”“生成阶段总结”“整理问题库”等类似任务时，才执行本节。

阶段总结建议放入：

- 项目总结：`D:\Zzc_Notes\01-项目\当前项目名\`
- 通用知识：`D:\Zzc_Notes\02-知识点\`
- 踩坑问题：`D:\Zzc_Notes\03-问题库\`
- 三天总结或周总结：`D:\Zzc_Notes\04-周总结\`

如果当前环境不能写入 `D:\Zzc_Notes`，直接输出完整 Markdown 内容，供用户复制。
