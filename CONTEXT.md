# 当前状态

> **最后确认：** 2026-10-23
> **阶段：** Phase 1 — 组件准入；正式清单与离线门禁已实现，源码迁移尚未准入。
> **代码基线：** 本轮起点 master `fcc7330`；生产路径仍为 Virtual DSM x86 与实验性 DS124 `rtd1619b` direct boot。

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
3. 接管后实现中立 Profile / Boot Provider 契约，以旧平台等价回归保护存储和生命周期。

## 当前阻断与风险

- 根 GPLv3、README 非商业声明、文件 MIT 头及依赖源码范围未闭合；不整体搬入争议内容或捆绑分发，见 [RISK-006](docs/RISK_REGISTER.md#risk-006p1arc-集成尚无运行与许可边界证据)。
- 自有引导器未构建或接入生产；DS124 direct boot 证据不代表 ARM64 Bootloader 移植成功。
- 本轮宿主 Windows AMD64 / PowerShell；Shell 回归经另行探测的 WSL Ubuntu x86_64 执行；未运行 DSM L2、KVM L3、Mac 或 RK3588 测试；设备风险见 [RISK-002/007](docs/RISK_REGISTER.md)。

## 最近验证

- 2026-10-23：组件来源复核、离线门禁和故障注入回归见[组件准入记录](docs/archive/reviews/2026-10-23-bootloader-component-admission.md)；没有组件获准迁入/组合构建/分发。

- 2026-10-23：PR #19 `5005083` 的 CI result / CodeRabbit success，3 条审查讨论已处理，合并为 `4a70602`；本地修复与远端门禁见[证据](docs/archive/reviews/2026-10-23-pr19-review-fixes.md)。
- 2026-10-23：Phase 1 固定 Git objects 审计与离线回归的命令、结果和未覆盖项见[源码审计证据](docs/archive/reviews/2026-10-23-bootloader-source-audit.md)。
- 既有依赖锁定与未验证边界见[依赖清单](docs/dependency-locks.md)；x86 安装保盘及健康检查见[回归记录](docs/archive/reviews/2026-10-22-installer-recovery.md)。

## 按需入口

- 自主源码：[源码审计](docs/bootloader-source-audit.md)、[研究入口](docs/arc-integration.md)
- 架构/设备：[运行架构](docs/runtime-architecture.md)、[测试矩阵](docs/test-matrix.md)、[Mac 选型](docs/mac-container-evaluation.md)
- 治理：[GOVERNANCE](docs/GOVERNANCE.md)、[AI_RULES](docs/AI_RULES.md)
