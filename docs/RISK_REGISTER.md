# 风险与开放假设

本文件只登记尚未验证的外部不确定性；实现后有意保留的妥协进入 [TECH_DEBT.md](TECH_DEBT.md)。

## 分级

- **P0**：阻断指定验收门禁。
- **P1**：不阻断当前门禁，但会改变发布或体验边界。
- **P2**：后续增强风险。

## 活跃风险

### RISK-002（P1）：裸机 ARM64 与跨主机 KVM 可移植性未验证

- **阻断 Gate：** 裸机 ARM64 或其他 ARM64-host 的兼容性/性能声明；不阻断已完成的 Phase 4A K5。
- **问题：** Apple M5 + Apple VZ nested KVM 已通过官方 PAT fresh install 与完整 K5 lifecycle；这不证明裸机 Linux ARM64、其他 CPU generation，或 Phase 3 runtime 跨主机可移植性。目标平台变化时 CPU feature/LPA2 暴露仍需实测。
- **环境证据与协议：** [Phase 4A](../research/arm64/production-phase4a.md)；新增目标按其中独立 KVM 初始化、CPU feature、冷启动与管理面协议验证。
- **关闭证据：** 裸机 ARM64 与额外目标主机上的独立冷启动、管理面和稳定性证据；Phase 3 runtime 另按其专属跨主机协议验收。

### RISK-003（P2）：Surveillance Station 与包安装矩阵未完成

- **阻断 Gate：** 功能完整度声明。
- **问题：** 只读诊断、双架构合成分类和显式官方 SPK 安装助手已加入；本地 SPK 元数据检查不等于 DSM 安装验证。官方 SPK 安装、许可、摄像头预览、录像/回放及持久化仍没有目标 DSM 实际证据。
- **关闭证据：** 至少一个平台完成 [端到端验收](surveillance-station.md)；另一个平台的状态单独保留在[兼容矩阵](surveillance-compatibility.md)。

### RISK-004（P2）：历史 Thumb 跨页实验结果未澄清

- **阻断 Gate：** 单个 TB 跨两物理页的动态覆盖声明；不改写既有 AArch64 DSM F5 证据。
- **问题：** 整理历史夹具时，修正汇编 `.endr` 后，生产 QEMU 8.2.2 的 Thumb 实验返回 0x1234，预期为 0x1000；目标半字实际为零。普通半字 store 和显式 cache-maintenance 对照同样失败，尚不能归因为 DC ZVA 补丁或确定为夹具错误。
- **证据与边界：** 忽略目录 `research/arm64/work/local-file-cleanup/thumb-investigation/` 保存三组日志；`local-archive-2026-10-15/diagnostics/thumb-investigation/` 保存修复后的实验源码。二进制 SHA256 与 [Phase 4A 预检](../research/arm64/production-phase4a.md) 相同。该实验未进入正式 [DC ZVA 测试](../tests/qemu-dcz/README.md)，正式套件仅声明已核查的 AArch64 覆盖。
- **关闭证据：** 独立核对 Thumb 解码、异常返回、访客内存和实际 TB 覆盖，获得可重复且能解释 store 对照结果的最小实验，再决定修正夹具或调查 QEMU。

### RISK-005（P1）：DSM 升级超出已验证构建

- **阻断 Gate：** 对 DSM 7.2.2-72806 之后版本的兼容性、安全性或升级可恢复性声明。
- **问题：** 自动安装、驱动、Storage Manager、Basic/Btrfs、启动和持久化证据仅覆盖 DS124 / rtd1619b / DSM 7.2.2-72806 及精确 PAT。DSM 更新界面可见不代表升级已验证。
- **当前策略：** 用户文档明确标为 unsupported / unvalidated；不得宣称任意未来 DSM 更新安全。保持可恢复的 storage 备份，不由自动化替换现有 runtime。
- **关闭证据：** 每个声明支持的 PAT/build 独立通过身份校验、fresh install、管理/服务、存储、生命周期和持久化验收。

### RISK-006（P1）：ARC 集成尚无运行与许可边界证据

- **阻断 Gate：** ARC 生产支持、捆绑/分发或商业许可声明。
- **问题：** 上游 x86 Docker/QEMU 示例不能替代本仓库的完整 DSM 启动、模型、存储、网络、健康检查、关机、升级/恢复证据；README 使用声明与 GPLv3 LICENSE 的适用边界仍需澄清。
- **当前策略：** 已确定先做隔离的 x86 ARC PoC，再研究 ARM64 loader port；当前尚未开始集成。固定版本、隔离数据盘、完成组件许可/DSM 边界审查前，不捆绑或分发 ARC；不启用授权/序列号绕过，保持现有 Virtual DSM/DS124 路径。
- **关闭证据：** 确认适用许可及 DSM 使用约束；独立 profile 通过全新盘安装、管理面、持久化、干净关机和升级恢复验收后，另行决定支持范围。

## 已关闭风险

- [RISK-001：Phase 3 严格 F5](archive/risks/2026-10.md#risk-001)。
