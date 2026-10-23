# Jules 开发环境

本页定义可复用的轻量环境，不记录账户启用状态。派单范围见[操作约定](bot-automation.md)，实际状态见 [CONTEXT](../CONTEXT.md)。

## Initial Setup 与快照

官方为每个任务提供 Ubuntu VM；可使用 setup script 并执行 Run and Snapshot。预装版本是文档示例，必须在实际任务中核实；Docker CLI 存在不证明 daemon、特权能力或 KVM 可用。

在 Jules 仓库 Configuration → Initial Setup 中配置以下命令，并在所选分支包含该脚本后运行：

```bash
bash scripts/jules-setup.sh
```

[脚本](../scripts/jules-setup.sh)要求 Linux、Python ≥3.11、Node ≥20、Git 和 ShellCheck，打印实际 OS/架构/版本；只在忽略目录 `.venv/jules` 创建 venv，安装与仓库 CI 一致的 PyYAML 6.0.3，并执行治理与派单离线回归。不安装系统包、不修改 Git 配置、不拉取 submodule、不下载 PAT、不构建生产镜像。

缺少工具时先由维护者在 Jules VM 配置环境；例如 Ubuntu 中缺少 venv/ShellCheck 可安装 `python3-venv shellcheck`，再重跑。不得让每个功能任务顺手修改依赖锁或权限。Python/Node/系统包并未在此完整锁定，快照用于减少重复准备，不构成可重复构建证明。

初次验证成功后保存快照。每次任务开始仍执行：

```bash
bash scripts/jules-setup.sh --check
source .venv/jules/bin/activate
# 接着运行 Issue 指定的验收命令。
```

`--check` 不安装依赖，只核验现有环境和运行轻量回归；激活命令要在执行任务检查的同一个 Shell 中运行。setup 子进程的 PATH 不会自动保留到后续工具调用。依赖、解释器或基线改变时，重新运行 Initial Setup 并保存快照；不要复用已失效快照掩盖错误。

## 任务级验证

- 文档：治理检查、对应文档测试、`git diff --check`。
- Python 离线工具：上述检查加该工具测试，覆盖退出码、错误输入、确定性输出和无副作用；只用合成数据。
- Shell：按 [AI_RULES](AI_RULES.md)运行 ShellCheck 和 research smoke；不要在 macOS 上假设 GNU 工具行为。
- Docker 构建：只有原任务明确要求且环境已验证时执行。setup 不启动 daemon，不挂载宿主 socket，不授予 privileged。
- DSM L2、目标设备/KVM L3、私有 PAT、凭据、真实存储和长期稳定性验收不转移到此环境。setup 禁用长期 watch/server；按官方说明使用能结束的安装和测试命令。

交付时保留命令、退出结果、环境版本、未运行项及原因。不得仅凭“快照成功”声称工作包测试通过。

## 官方依据

- [Environment setup](https://jules.google/docs/environment/)：Ubuntu、依赖准备和快照。
- [FAQ](https://jules.google/docs/faq/)：云端环境及 setup 长驻进程限制。
- [Running tasks](https://jules.google/docs/running-tasks/)：任务反馈和暂停。
