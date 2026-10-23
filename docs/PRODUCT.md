# DockDSM 产品范围摘要

本文件固定产品范围；使用入口见 [readme.md](../readme.md)，已有平台接口见 [platforms.md](platforms.md)，执行状态见 [CONTEXT](../CONTEXT.md)。

## 目标

- DockDSM 独立维护具有明确兼容矩阵、可靠存储和生命周期管理的 DSM 虚拟化运行平台；首个运行后端为 Docker/QEMU，采用渐进重构。
- 保留 Virtual DSM x86 和 DS124 / `rtd1619b` direct boot 的平台与数据契约；新引导链目标为 DockDSM Bootloader，不要求既有平台迁移。
- 按源码准入与接管 → 统一品牌/Boot Provider 接口 → x86 构建与运行验收 → ARM64 Bootloader 研发推进；Python 控制层、Profile、Runtime、存储/生命周期渐进接入，见 [ADR 0009](ADR/0009-owned-bootloader-source.md)和[实施计划](implementation-plan.md)。
- 首批设备为 x86、MacBook Air M5、RK3588。RK3588 只使用 Docker 容器验证；Mac 兼容 KVM，并通过不同容器后端的完整负载对照选型。具体环境及未验证项见 [测试矩阵](test-matrix.md)。
- 新仓库历史以单一初始化提交开始；品牌和历史重建不改变继承代码的来源、许可证及原作者归属。
- 下一次发布目标为 `ghcr.io/ben8368/dockdsm`；仓库重建不代表新镜像已经发布。

## 非目标（当前）

- 不宣称物理 DS124 分区表完全兼容。
- 不默认同步 vdsm/virtual-dsm 或 AuxXxilium/arc 的变更。
- 首批不做全面重写、全设备/全 DSM 型号覆盖、远程 Web 控制或跨架构高性能承诺；ARM64 Bootloader 等待 x86 工作链验收，Host QEMU/libvirt 另行评估。
- 不在未验证前宣称 DockDSM Bootloader x86 生产支持、ARM64 引导器移植、Surveillance Station 或商店级支持。
- 不把研究用诊断补丁当作未晋升的生产行为。
