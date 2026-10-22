# DockDSM 产品范围摘要

权威展开见根 [readme.md](../readme.md) 与 [platforms.md](platforms.md)。本文件只固定范围边界，避免在多处复制长文。

## 目标

- DockDSM 独立维护 Docker 管理的 QEMU/KVM DSM 方案；目标启动链为 Docker → QEMU/KVM → ARC loader → DSM。
- 当前代码仍是 Virtual DSM x86 与实验性 DS124 / `rtd1619b` ARM64 两条既有路径；ARC 尚未集成，ARC ARM64 移植尚未开始。
- 目标是先保留 x86 ARC 启动能力，再研究把现有 ARM64 平台能力移植到 ARC/兼容 loader；只有通过分阶段构建、冷启动、存储和授权边界验收后才列为支持。
- 新仓库历史以单一初始化提交开始；品牌和历史重建不改变继承代码的来源、许可证及原作者归属。
- 下一次发布目标为 `ghcr.io/ben8368/dockdsm`；仓库重建不代表新镜像已经发布。

## 非目标（当前）

- 不宣称物理 DS124 分区表完全兼容。
- 不默认同步 vdsm/virtual-dsm 或 AuxXxilium/arc 的变更。
- 不在未验证前宣称 ARC x86 生产支持、ARM64 ARC 移植、Surveillance Station 或商店级支持。
- 不把研究用诊断补丁当作未晋升的生产行为。
