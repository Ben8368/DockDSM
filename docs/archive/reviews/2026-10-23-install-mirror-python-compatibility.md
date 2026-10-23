# ARM 默认镜像选择与 Python 3.11 准入兼容性修复

## 范围与环境

- 基线：本地 master `7c563a2`，修复前工作区干净；修复验证后依维护者明确授权本地提交，未推送、合并或发布。
- 宿主：macOS / arm64 / zsh；验证使用 Homebrew Bash 5.3.20、Python 3.11.15 与 3.14.6、ShellCheck 0.11.0。
- Linux 合成验证：已有 `virtual-dsm:phase4b-arm64` 镜像，镜像 ID `590d41d17634`；容器内 Linux / aarch64 / Python 3.13.5。仓库只读挂载、`--network none`、根文件系统只读，仅 `/tmp` 夹具可写。不启动 DSM，不挂载用户存储，不用已有镜像冒充本轮新构建。
- 全部测试均使用非专有夹具；不修改 QEMU 补丁、访客 watchdog、收据/清单、准入状态或依赖锁。

## 问题与修复

1. ARM 默认首次安装在 `URL`、`COUNTRY` 为空时调用共享 `selectDsmMirror`，但其依赖的 `getCountry` / `setCountry` 原来只在 x86 `install.sh` 中定义。函数现移入共同加载的 `src/pat.sh`；时区检测允许 `TZ` 未设置，检测失败仍退回 global 镜像。x86 的镜像优先级、下载/安装和保盘契约保留。
2. Git 存储边界检查原来无条件调用 Python 3.12 新增的 `Path.is_junction()`，使 Python 3.11 的正常检查失败。现在逐条验证 `entry.resolve()` 是否在工作区内，不再依赖链接类型识别；外部 symlink、解析后越界的路径、gitdir/commondir、alternates 和 config include 仍在 Git 对象读取前拒绝。

`tests/fixtures/x86-scripts.sha256` 仅因共享 PAT 模块接收迁移函数而更新该文件摘要；config/serial 摘要和两个平台 argv 快照未改。未通过删除断言或改变预期命令使测试通过。

## 回归设计与红灯

- 新增 `tests/arm-mirror-regression.sh`，经既有 `tests/pat-acquisition.sh` 进入 CI。直接走 `platformRunStage install`，不 stub 国家检测或镜像选择；只隔离锁、缓存、磁盘空间和外部传输边界。八个场景覆盖缺省离线、CN 时区、显式 CN、成功探测、无效国家响应、显式 URL、cache hit 和无效缓存。检查实际传给下载器的 URL、探测次数、未进入 x86 安装器、原有哨兵内容和临时工作区清理。
- ARM 红灯：将 HEAD 的 common/rtd1619b/arm-install/pat 四个文件复制到可丢弃目录，执行新增脚本；旧实现出现 `setCountry: command not found`，预期下载边界 69 实际为 127，回归失败。未修改真实源码来生成红灯。
- 准入新增三项：不调用 3.12 API、真实外部存储链接在 Git reader 前拒绝、解析后越界但不报告 symlink 的路径仍拒绝。最后一项是 junction 行为模型，不冒充 Windows 原生验收。
- 在 Python 3.14 中以内存模块加载 `git show HEAD:scripts/check-bootloader-admission.py`，执行新 API / 解析越界两项用例，两项均拒绝旧实现；修复版完整 55 项通过。

## 实际验证

| 命令 | 结果 |
| --- | --- |
| `python3 tests/bootloader-component-admission.py` | macOS / Python 3.11.15，55 tests，OK |
| `/opt/homebrew/bin/python3.14 tests/bootloader-component-admission.py` | macOS / Python 3.14.6，55 tests，OK |
| `python3 tests/bootloader-source-audit.py` | 11 tests，OK |
| `/opt/homebrew/bin/bash tests/arm-mirror-regression.sh` | 八个安装分发场景通过；无效缓存的保盘错误是预期分支 |
| `bash tests/pat-acquisition.sh` | Linux，原获取回归及新增 ARM 分发回归通过 |
| `bash research/arm64/tests/smoke.sh` | Linux，通过，包含双平台 argv / 源码摘要 / 错误参数回归 |
| `python3 tests/x86-installer-regression.py` | Linux，8 tests，OK，包含完整盘复用和不完整盘保护 |
| `bash tests/healthcheck.sh`、`bash tests/guest-clock.sh` | Linux，通过；host date 未修改 |
| `python3 tests/production-x86-command.py` | Linux，通过，fake QEMU rc=37、argv 不变、无 PAT/网络访问 |
| `python3 tests/image-validation.py`、`python3 tests/arm-runtime.py`、`python3 tests/guest-integrations.py` | Linux，通过，磁盘只读检查、扩容/拒绝缩容、QMP 收据和集成边界回归 |
| `shellcheck -x src/*.sh src/platform/*.sh research/arm64/*.sh research/arm64/tests/*.sh tests/pat-acquisition.sh tests/arm-mirror-regression.sh tests/platform.sh` | ShellCheck 0.11.0，通过；上述范围及其余 `tests/*.sh` 的逐文件 Bash syntax 检查通过 |
| `/tmp/dockdsm-fix-validation-venv/bin/python tests/bot-dispatch.py` | 临时 venv 仅安装 PyYAML 6.0.3，12 tests，OK |
| `/tmp/dockdsm-fix-validation-venv/bin/python tests/ci-policy.py` | 21 tests，OK；故意不可解析的基线诊断是预期分支 |
| `/tmp/dockdsm-fix-validation-venv/bin/python scripts/check-config.py` | 跟踪 JSON/YAML 检查通过 |
| `python3 scripts/governance-docs-check.py`、`python3 tests/governance-docs.py`、`python3 scripts/check-tree.py`、`git diff --check` | 通过 |

### 环境限制与未覆盖项

- 已有运行镜像不含 Git；其中尝试准入夹具得到 `FileNotFoundError: git`，不计通过。准入的 55 项已在有 Git 的两个宿主 Python 版本完成。
- `git submodule status` 显示固定 `vendor/arc` 未初始化；`python3 scripts/check-bootloader-admission.py --check` 返回 1 / `invalid or unavailable evidence`，符合缺失对象时拒绝。未联网补齐 submodule，未宣称实库 `--check` 或 `--strict` 通过。
- 对所有 `tests/*.sh` 做额外 ShellCheck 扫描时，未改动的 `tests/healthcheck.sh:48` 在本机 0.11.0 报 SC2329（导出后间接调用的 curl 函数）；未修改该测试或调整扫描配置。变更涉及范围和规范要求范围的 ShellCheck 已通过。
- 未运行新的原生双架构镜像构建、完整 PAT 构建、真实 DSM 冷启动、Windows junction 原生验证或 KVM L3。现有运行证据与硬件风险边界不由本轮 L0/L1 替代。

## 派单与所有权

依用户本轮明确授权及既有表单，创建 [Jules 小任务 #22](https://github.com/Ben8368/DockDSM/issues/22)，仅允许 `docs/bootloader-source-audit.md` 补充本地 Python/Git 前置说明。创建者 Ben8368 的实时权限为 admin；`bot-dispatch` 已加 `jules` 标签。截至本轮复核，尚无回复或产出 PR，不能把标签当成 Jules App 接单或完成证据。

Codex 负责源码、回归与本记录，不编辑机器人独占文档。未给机器人生产/安全脚本、CI 权限或用户磁盘操作；不修改其计费、标签门禁，不自动合并。

## 🚦 Audit Report

**总体评价：🟡 可通行（本轮 L0/L1 修复）。**

- **🔴 阻断项：** 本轮修复范围未发现新增安全越界、自动重建磁盘或准入放宽；缺失源码对象保持拒绝。
- **🟡 跟进项：** 目标宿主/真实运行边界仍见 [RISK-002/007](../../RISK_REGISTER.md)，源码准入仍见 [RISK-006](../../RISK_REGISTER.md#risk-006p1arc-集成尚无运行与许可边界证据)；现有共享 Shell 状态债务见 [TD-003](../../TECH_DEBT.md#td-003启动编排依赖基础镜像脚本与共享-shell-状态)。
- **验证结论：** 上表实际命令通过；未覆盖项单列，不把合成下载边界或模型测试写成官方 PAT、Windows 或硬件验收。
