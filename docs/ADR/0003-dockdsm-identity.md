# ADR 0003：DockDSM 独立命名与兼容迁移

- 状态：部分替代
- 替代范围：仅“不重写已有 Git 历史”的决定由 ADR 0004 替代；命名、来源披露与内部兼容决定继续有效。
- 替代决定：见 [ADR 0004](0004-reinitialized-history-and-arc-roadmap.md)
- 日期：2026-10-22

## 背景

项目已独立维护 Docker/QEMU 中的 DSM 运行方案。继续使用与上游相同的仓库和产品名称会混淆发行方；本轮明确使用 DockDSM，并参考 OpenHID 的来源披露方式。

## 决策

- 产品及 GitHub 仓库名为 DockDSM（`Ben8368/DockDSM`）；新镜像发布目标为 `ghcr.io/ben8368/dockdsm`。不把更名当作镜像已发布。
- 上游快照导入、贡献归属与 MIT 保留记录在 [PROVENANCE](../PROVENANCE.md)，README 仅摘要和链接；不重写已有 Git 历史。
- 运行时入口/支持链接使用 DockDSM；Synology Virtual DSM 仍是访客产品名。内部 `virtual-dsm` 服务、路径、平台 ID、磁盘/schema 和部署存储保持兼容，不做全局字符串替换。
- 原 GHCR 包和既有镜像不删除。新发布后由用户显式切换镜像并验证；本轮不自动提交、推送源码或发布。
- 向导与 ARC 可行性见 [评估](../arc-integration.md)。它们不因命名决策而获得生产支持，默认平台和启动协议不变。

## 后果

源码品牌与仓库地址清晰，新旧镜像包需分别管理。更名后需要用新仓库地址重新检查外部集成/发布权限；未配置或未验证的服务不得宣称完成。用户无需移动本地工作区或重建已有 DSM 磁盘。

## 替代方案

- 只改 README：不能解决仓库身份混淆。
- 全量重命名 `virtual-dsm` 内部标识：会造成无必要的兼容与数据迁移风险。
- 直接用 ARC 替代默认启动器：与品牌变更无关，且缺乏独立启动/存储/生命周期和许可证据。

## 关联文档

- [产品范围](../PRODUCT.md)
- [发布规则](../ci.md#publishing)
- [ARC 集成评估](../arc-integration.md)
