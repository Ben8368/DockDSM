# ADR 0004：重建仓库历史并确立 ARC/ARM64 路线

- 状态：已接受
- 日期：2026-10-22
- supersedes：ADR 0003 中“保留既有 Git 历史”的决定；不撤销其内部标识兼容边界。

## 背景

维护者决定将 DockDSM 作为独立项目重新初始化 Git 历史，并将目标架构收敛为 Docker 管理 QEMU/KVM 中的 ARC loader，再由 ARC 构建/引导 DSM。ARC 当前面向 x86-64；DockDSM 已有 DS124 / `rtd1619b` ARM64 路径，但它是直接 kernel/initrd 启动，不是 ARC 移植。

## 决策

1. 将旧 `Ben8368/DockDSM` 改名并归档为 `DockDSM-archive-20261022`，随后创建新的同名公开仓库；旧 Git 对象及远端元数据已备份。新仓库 `master` 从单个根初始化提交开始，只维护 `master`。
2. DockDSM 独立维护，不自动同步或跟随任一项目。对外感谢 vdsm/virtual-dsm 的 Docker/QEMU Virtual DSM 基础，以及 AuxXxilium/arc 的 ARC 引导架构与参考实现。
3. 透明披露：当前部分代码源自 vdsm/virtual-dsm。保留其 MIT 条款及原作者/贡献者归属。ARC 先作为参考，不声称已经合并；如复制或分发其代码/产物，先完成组件级许可证和分发审查。致谢不能替代许可证义务。
4. 产品目标是 Docker → QEMU/KVM → ARC → DSM。先固定 x86 ARC 启动/管理/数据盘和恢复契约，再独立设计 ARM64 ARC/loader port，复用经审查的 DockDSM ARM64 硬件、QEMU、存储和运行时知识。不得把现有 `rtd1619b` direct-boot 代码改名成 ARC 支持。
5. 在分阶段测试与目标环境证据完成前，ARC x86 与 ARC ARM64 都是未交付能力；保留当前 Virtual DSM 与 DS124 启动路径及现有磁盘兼容性，不自动迁移或格式化。

## 后果

新 `master` 的 GitHub contributor/history 视图可能需要 GitHub 重新计算；创建新仓库而非原地强推，以隔离旧 contributor 缓存；重建不等于删除旧归档、GitHub 的其他引用、fork 或外部副本。源文件仍准确记录代码来源。ARC/ARM64 的实现工作量、硬件支持范围、许可与运行时兼容性仍需逐阶段验证。

## 验收门槛

- GitHub `master` 仅含新的根初始化提交，远端不存在其他分支；本地仅保留 `master`。
- 归属/许可说明、来源快照、内部存储与平台标识均保留。
- ARC x86 先通过隔离 profile 的启动、配置、DSM 安装、数据盘持久化、干净关机和升级/恢复测试；ARM64 另有 loader 架构、启动链、QEMU/KVM/TCG、存储和目标设备证据后才可声明支持。

## 关联文档

- [产品范围](../PRODUCT.md)
- [来源与致谢](../PROVENANCE.md)
- [ARC/ARM64 路线与当前状态](../arc-integration.md)
- [ADR 0003：品牌与兼容迁移](0003-dockdsm-identity.md)
