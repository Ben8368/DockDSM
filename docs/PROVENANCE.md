# DockDSM 来源与独立维护

## 致谢与代码来源

DockDSM 感谢 [vdsm/virtual-dsm](https://github.com/vdsm/virtual-dsm) 提供 Docker/QEMU Virtual DSM 方案基础，也感谢 [AuxXxilium/arc](https://github.com/AuxXxilium/arc) 提供 ARC 引导器的架构与实现参考。两个项目均非 DockDSM 的上游依赖；DockDSM 自行维护路线，不自动同步任何仓库。

需要区分致谢与代码来源：当前代码库的一部分直接源自 vdsm/virtual-dsm。原始导入基线为 [`88c2d4673aa428c9dc9c9ae90eaf63d0e8e2335c`](https://github.com/vdsm/virtual-dsm/commit/88c2d4673aa428c9dc9c9ae90eaf63d0e8e2335c)（`build: Update QEMU base image to v7.50 (#1404)`）。原作者与贡献者归属继续保留；继承的 [MIT 许可证](../license.md)继续适用。重建 Git 历史、改名或独立维护都不改变这一事实。

ARC 当前是架构/实现参考，不代表 ARC 源码已复制、合并或随 DockDSM 分发。未来若移植或分发 ARC 代码及构建产物，须先按具体组件核实许可证、声明、来源和分发条件；ARC 仓库的 README 使用限制与 LICENSE 文本应一并审查，不能仅凭致谢替代许可审查。Synology DSM、PAT、第三方基础镜像、QEMU 及其他依赖各自的权利与许可独立处理。

## 独立维护与仓库历史

DockDSM 由 Ben8368 独立维护，拥有自己的产品决策、问题跟踪和发布，不代表上述项目或 Synology 官方产品/背书。DockDSM GitHub 仓库历史已重建为单一初始化提交；先前可见的 DockDSM 提交链由维护者本地备份，并保留在[只读历史归档仓库](https://github.com/Ben8368/DockDSM-archive-20261022)。新的 Git 根提交不应被误读为所有代码均由该提交作者原创。

项目及镜像身份为 `Ben8368/DockDSM` / `ghcr.io/ben8368/dockdsm`。GHCR 旧包不会因 Git 历史重建而自动删除或改名；新镜像的构建发布需走 [CI / Publishing](ci.md#publishing)。

## 兼容边界

品牌与 Git 历史重建不全局重命名内部契约。`DSM_PLATFORM=virtualdsm`、`rtd1619b`、guest 的 `virtual-dsm-*` systemd 服务、`/usr/local/*/virtual-dsm` 路径、存储 schema、现有磁盘、Compose 服务名和本地宿主存储目录继续兼容，避免误建空盘或触发数据迁移。
