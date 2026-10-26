# 当前状态

> **最后确认：** 2026-10-25
> **阶段：** Phase 1 Provider 已实现（旧平台仅合成回归）；Linux x86 GRUB TCG 与 ARM64 GIC handoff 通过；DS124 官方 kernel/initrd 的 diskless TCG kexec 实验到达 login。
> **代码基线：** `codex/boot-provider-bootstrap` 基于 master `c2da0dc`。生产路径为 Virtual DSM x86/DS124 `rtd1619b` 实验。

## 当前决策

- DockDSM 独立维护，不自动同步上游；源码归属与历史边界见 [PROVENANCE](docs/PROVENANCE.md)。
- 自主源码接管 → DockDSM 品牌/接口 → x86 Bootloader → ARM64 backend；逐阶段验收，见 [ADR 0009](docs/ADR/0009-owned-bootloader-source.md) 与[实施计划](docs/implementation-plan.md)。
- 准入后优先 subtree squash，选择性 snapshot 为备选；临时研究 submodule 不等于最终维护架构，见[源码审计](docs/bootloader-source-audit.md)。
- `virtualdsm` / `rtd1619b` 与旧盘边界保持；`full-x86_64` / `full-arm64` 尚未实现，不加入生产白名单，见[平台契约](docs/platforms.md)。
- x86、MacBook Air M5、RK3588 分别取证；RK 仅 Docker 验证，Mac 后端需实测选型，见[测试矩阵](docs/test-matrix.md)。
- 生产 QEMU 补丁只经 [8.2.2 系列](patches/qemu/8.2.2/README.md)进入镜像；CI 和机器人规则见 [CI](docs/ci.md) 与 [ADR 0008](docs/ADR/0008-scoped-bot-autofix.md)。
- 后续 PR 不自动合并；正式镜像发布仍须另行授权。

## 近期优先级

1. 取得 Buildroot Essential/Evo、LKM/Custom 对应源码及权利范围确认；缺口见[组件清单](research/bootloader/component-manifest.json)。
2. 准入后在独立 PR 接管可构建源码，保留来源、许可、固定输入和回退路径。
3. 完成 ARC 准入、双架构 CI 和旧平台回归；在 DSM 验收前不开放新平台。

## 当前阻断与风险

- ARC 来源/许可范围未闭合；暂不整体导入或分发组合产物，见 [RISK-006](docs/RISK_REGISTER.md#risk-006p1arc-集成尚无运行与许可边界证据)。
- 自有 x86/ARM64 研究引导链已构建并通过开放 Linux QEMU 测试，未接入生产；许可审查、DSM 生命周期和硬件验收仍未完成。
- DS124 kexec 仅 loader LPI 关闭时无 corruption warning；开启会 taint，见 [RISK-010](docs/RISK_REGISTER.md)。DSM 生命周期、KVM L3/设备未验收，见 [RISK-002/007](docs/RISK_REGISTER.md)。

## 最近验证

- 2026-10-26：WSL2 amd64 镜像回归及 PR #25 ARC/ARM64/x86 合成检查通过；本轮未跑真实 ARM64 UEFI 冷启动。[证据](tests/qemu-dcz/README.md)；不等同于原生 Linux/KVM。
- 2026-10-25：DS124 stock initrd 在 2 GiB snapshot scratch 到达 login；原盘未变，未验收安装/生命周期。[记录](research/arm64/loader/README.md)
- 2026-10-25：ARM64 Linux/DS124 TCG kexec 到 login；DS124 LPI 开时 taint，设备/生命周期未验收。[记录](research/arm64/loader/README.md)
- 2026-10-25：x86_64 ISO 两次构建哈希一致，SeaBIOS/OVMF TCG 启动并关机；DSM 未测。[记录](research/x86_64/grub-loader/README.md)
- 2026-10-25：ARM64 UEFI/GRUB 原型与合成检查通过；Buildroot 尝试停在 glibc 完整 Git 历史下载，未产镜像或运行 UEFI QEMU。[记录](research/arm64/grub-loader/README.md)
- 2026-10-25：固定 ARC 的 ARM 型号筛选、ARM64 GRUB 构建目标/ESP、更新包模块和 DockDSM 运行时品牌 overlay 已扩展；未验 ARC ARM runtime、DSM ARM 或 kexec。[评估](research/arc/arm64-port-assessment.md)
- 2026-10-25：假 QEMU 验证 argv/畸形输入、PID/信号/退出码及 KVM 失败拒绝；平台快照通过，未跑真实 QEMU/DSM。[Provider](tests/boot-provider-legacy.py)、[平台](tests/platform.sh)
- 2026-10-25：ARC 准入故障注入通过；`vendor/arc` 未初始化时实库检查 fail closed，未准入组件。[测试](tests/bootloader-component-admission.py)、[门禁](scripts/check-bootloader-admission.py)
- 依赖锁定与未验证边界见[清单](docs/dependency-locks.md)；x86 安装回归见[记录](docs/archive/reviews/2026-10-22-installer-recovery.md)。

## 按需入口

- 自主源码：[源码审计](docs/bootloader-source-audit.md)、[研究入口](docs/arc-integration.md)
- 架构/设备：[运行架构](docs/runtime-architecture.md)、[测试矩阵](docs/test-matrix.md)、[Mac 选型](docs/mac-container-evaluation.md)
- 治理：[GOVERNANCE](docs/GOVERNANCE.md)、[AI_RULES](docs/AI_RULES.md)
