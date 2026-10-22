# 当前状态

> **最后确认：** 2026-10-22
> **阶段：** 性能基线与运行架构规划已落文档；x86 安装恢复保护已本地修复并通过合成回归，未进行设备验收。
> **代码基线：** DockDSM `master` 已包含初始化后的治理与依赖提交；产品代码仍为 Virtual DSM x86 与实验性 DS124 `rtd1619b` direct-boot ARM64。

## 当前决策

- DockDSM 独立维护，不自动同步上游；Git 根历史重建不改变现有代码来源和 MIT 归属，见 [PROVENANCE](docs/PROVENANCE.md) 与 [ADR 0004](docs/ADR/0004-reinitialized-history-and-arc-roadmap.md)。
- 采用性能实验 → Profile/Runtime 分层 → 生命周期/存储 → 扩展平台路线；ARC 是可选 Boot Provider，见 [ADR 0006](docs/ADR/0006-runtime-profiles-and-container-first.md)。
- 设备为 x86、MacBook Air M5、RK3588；RK 仅 Docker 容器验证，Mac 比较容器后端后选型，详见[测试矩阵](docs/test-matrix.md)。
- 当前 `virtualdsm` 与 DS124 `rtd1619b` 启动实现和存储兼容边界保持不变；见 [平台契约](docs/platforms.md)。
- CI 已采用保守范围路由、原生双架构检查和统一 `CI result`；发布仍需手动授权，见 [CI 设计](docs/ci.md)。
- Renovate / Jules / CodeRabbit 已接入；[依赖看板 #3](https://github.com/Ben8368/DockDSM/issues/3)与 Jules 文档 PR 已生成，普通依赖仍先审批，Dependabot 负责安全修复；低风险 PR 自动修复规则已启用，Issue 自动派单待 workflow 合并；边界见 [ADR 0008](docs/ADR/0008-scoped-bot-autofix.md)。
- 生产 QEMU 补丁仍只经 [8.2.2 补丁系列](patches/qemu/8.2.2/README.md)进入镜像。

## 近期优先级

1. W00/W01：补齐三设备环境登记，固定镜像、QEMU 与工具来源。
2. W10–W12：执行既有平台基线及 Mac 容器候选资格/性能对照，记录真实 accelerator 与就绪证据。
3. W20–W23：按基线选择 KVM、日志、网络和 I/O 单变量实验；之后进入平台/状态分层，见[实施计划](docs/implementation-plan.md)。

## 当前阻断与风险

- ARC 尚未进入 Docker/QEMU 生产镜像或当前默认启动链；现有 ARM64 是 direct boot，不是 ARC。ARC x86 以及 ARM64 loader 均未验收，见 [ARC 路线](docs/arc-integration.md) 与 [RISK-006](docs/RISK_REGISTER.md)。
- 既有 ARM64 Phase 4A/K5 与 Phase 3/F5 证据只适用于记录的 DS124 direct-boot 环境，不可转用于 ARC 启动链或裸机可移植性声明。
- RK3588、Mac 新容器后端及本轮性能基线未运行；设备软件/资源需盘点，见 [RISK-002/007](docs/RISK_REGISTER.md)。

## 最近验证

- 2026-10-22：x86 不完整安装保盘修复通过本地 L0/L1；健康检查由 Jules 提交 PR #8 待审查，见[修复与派单记录](docs/archive/reviews/2026-10-22-installer-recovery.md)。
- 2026-10-22：README/部署文档与 CI 重写；本地静态、策略和合成回归通过，见 [验证记录](docs/archive/reviews/2026-10-22-ci-redesign.md)。云端结果按当前 `master` SHA 的 [Actions](https://github.com/Ben8368/DockDSM/actions) 核验，不以旧 run 代替。
- 2026-10-22：同步当时远端根提交（现由 `refs/tags/evidence/2bebdb2` 固定；该根提交已被 `2da1c3d` 取代，证据边界见 [PROVENANCE](docs/PROVENANCE.md#已重建根提交的证据边界)）；本轮文档验证与范围记录见[规划审查](docs/archive/reviews/2026-10-22-runtime-plan.md)。
- 2026-10-22：机器人授权、Issue 派单、Dashboard、PR 的 CI 与本地配置/署名校验见[接入记录](docs/archive/reviews/2026-10-22-bot-setup.md)；最终根提交云端结果按当前 SHA 核验。
- 2026-10-22：核验 master 分支保护，并加固治理检查、ADR 语义与重建提交证据边界，见[治理加固记录](docs/archive/reviews/2026-10-22-governance-hardening.md)。

- 2026-10-22：低风险 PR 规则 Active、现有两条 PR 不匹配；本地派单回归与未验收边界见[自动修复记录](docs/archive/reviews/2026-10-22-bot-autofix.md)。

## 按需入口

- ARC/ARM64：[docs/arc-integration.md](docs/arc-integration.md)、[docs/platforms.md](docs/platforms.md)
- 工程规划：[实施计划](docs/implementation-plan.md)、[运行架构](docs/runtime-architecture.md)、[Mac 选型](docs/mac-container-evaluation.md)
- 来源/治理：[docs/PROVENANCE.md](docs/PROVENANCE.md)、[docs/GOVERNANCE.md](docs/GOVERNANCE.md)、[docs/AI_RULES.md](docs/AI_RULES.md)
