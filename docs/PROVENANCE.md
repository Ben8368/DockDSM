# DockDSM 来源与独立维护

## 致谢与代码来源

DockDSM 感谢 [vdsm/virtual-dsm](https://github.com/vdsm/virtual-dsm) 提供 Docker/QEMU Virtual DSM 方案基础，也采用 [AuxXxilium/arc](https://github.com/AuxXxilium/arc) 为隔离研究型 Boot Provider 的上游源码。ARC 通过 `vendor/arc` submodule 固定到 `99195dbdf4e0a21c5304ddb06e07dc57419679bc`；DockDSM overlay 单独存于 `patches/arc/`，不会自动同步上游。

需要区分致谢与代码来源：当前代码库的一部分直接源自 vdsm/virtual-dsm。原始导入基线为 [`88c2d4673aa428c9dc9c9ae90eaf63d0e8e2335c`](https://github.com/vdsm/virtual-dsm/commit/88c2d4673aa428c9dc9c9ae90eaf63d0e8e2335c)（`build: Update QEMU base image to v7.50 (#1404)`）。原作者与贡献者归属继续保留；继承的 [MIT 许可证](../license.md)继续适用。重建 Git 历史、改名或独立维护都不改变这一事实。

ARC 源码仍由独立 submodule 提供，DockDSM 仓库只保存 gitlink 与本地补丁，不复制 ARC 源码文件或将其并入自有 MIT 代码。ARC 上游 README 声明禁止商业使用，仓库 `LICENSE` 标记 GPL-3.0，部分源文件另有 MIT 头部；其适用范围尚未澄清。因此当前不把 ARC 源码或构建产物捆绑到 DockDSM 镜像/发布物，不作商业使用授权声明。后续采用、构建或分发前，须按具体组件核实许可证、声明、来源和分发条件。Synology DSM、PAT、第三方基础镜像、QEMU 及其他依赖各自的权利与许可独立处理。源码接管方案与只读证据校验见[源码审计](bootloader-source-audit.md)；历史 overlay 见 [ARC 集成记录](arc-integration.md) 和 [ARC 研究说明](../research/arc/README.md)。最终自有引导器使用 DockDSM Bootloader 品牌，来源与许可证不因改名变化。

## 独立维护与仓库历史

DockDSM 由 Ben8368 独立维护，拥有自己的产品决策、问题跟踪和发布，不代表上述项目或 Synology 官方产品/背书。DockDSM GitHub 仓库历史已重建为单一初始化提交；先前可见的 DockDSM 提交链由维护者本地备份，并保留在[只读历史归档仓库](https://github.com/Ben8368/DockDSM-archive-20261022)。新的 Git 根提交不应被误读为所有代码均由该提交作者原创；GitHub contributor 图、外部 fork 与副本不受新仓库重建控制。

项目及镜像身份为 `Ben8368/DockDSM` / `ghcr.io/ben8368/dockdsm`。GHCR 旧包不会因 Git 历史重建而自动删除或改名；新镜像的构建发布需走 [CI / Publishing](ci.md#publishing)。

## 已重建根提交的证据边界

2026-10-22 当天，初始化根提交曾为 [`2bebdb2`](https://github.com/Ben8368/DockDSM/commit/2bebdb27af7b9d0185ce93b96a4b4eb0525b9331)，随后被当前根提交 `2da1c3d` 取代。`2bebdb2` 不在 `master` 可达历史中，只读归档仓库也不包含它，且该归档仓库已设为只读。为保留证据，主仓库已建立带注解 tag `refs/tags/evidence/2bebdb2`；需要长期引用时使用此 tag，不要依赖可达历史或归档仓库。

## 兼容边界

品牌与 Git 历史重建不全局重命名内部契约。`DSM_PLATFORM=virtualdsm`、`rtd1619b`、guest 的 `virtual-dsm-*` systemd 服务、`/usr/local/*/virtual-dsm` 路径、存储 schema、现有磁盘、Compose 服务名和本地宿主存储目录继续兼容，避免误建空盘或触发数据迁移。
