# 2026-10-22 x86 安装恢复保护

## 范围与职责

维护者要求将简单修复交给机器人，其余由 Codex 完成。健康检查由 Jules 独立承接 [Issue #7](https://github.com/Ben8368/DockDSM/issues/7)，并交付 [PR #8](https://github.com/Ben8368/DockDSM/pull/8) 待审查。该项未修复的影响登记于 [TD-004](../../TECH_DEBT.md#td-004启动未就绪时健康检查误报成功)。Codex 负责 x86 安装器；维护者随后授权提交 PR，本分支基于远端 `922cf94`，不合并或发布。

## 触发条件与修复

基线 `6f37a92`：已有 `DSM_VirtualDSM_72806.system.img`、缺失启动盘时，安装器会先删除系统盘，再下载 PAT。合成下载失败返回 69 后，原系统盘已经不存在。

`checkDsmInstallState` 在初始选定 base 和默认 URL 再次选定 base 后分别保护磁盘；不完整、空文件、断链或异常目录停止启动并保留文件。完整镜像对继续复用，空 storage 继续安装。用户恢复流程的权威定义见 [平台契约](../../platforms.md#virtualdsm-installation-recovery)。

原 x86 安装器字节哈希校验替换为执行实际 `installDSM` 分支的合成测试；未改动的 config/serial/PAT helper 仍保留历史哈希。既有 CI 已调用相同测试文件，无需修改 workflow。

## Audit Report

- 本地系统盘保护修复在 L0/L1 范围通过；健康检查缺口按 TD-004 单独跟进。
- 不修改 ARM 状态、QEMU、真实磁盘、DSM watchdog 或发布策略；不把合成结果当作真实 DSM/硬件验收。

## 客观验证

Linux 命令均在 WSL Ubuntu-24.04 的 `/mnt/c/DockDSM` 执行：

- `python3 tests/x86-installer-regression.py`：8 个测试方法通过；覆盖 14 个来源/缺盘组合，以及空文件、断链、目录、完整镜像复用和全新安装下载失败。
- 红灯验证：临时目录中用 `git show 6f37a92:src/install.sh` 加载修改前安装器，执行同一 `test_partial_selected_installations_are_preserved`；14 个子场景全部失败、夹具异常为 0。生产文件未回滚。
- `shellcheck -x src/install.sh tests/platform.sh`：通过。
- `bash research/arm64/tests/smoke.sh`：通过，包含平台参数与剩余历史哈希回归。
- `bash tests/pat-acquisition.sh`：通过。
- `python3 scripts/governance-docs-check.py`、`python3 tests/governance-docs.py`：通过。
- `bash tests/production-x86-command.sh`：通过 host snapshot/fake QEMU 回归，未提供镜像参数，不计入镜像验收。
- `python3 scripts/check-tree.py`、`git diff --check`：通过。

未运行生产镜像构建、官方 PAT 安装、真实 DSM 冷启动或硬件/KVM；本轮为本地源码修复与合成回归，不代表远端 CI result 已通过。
