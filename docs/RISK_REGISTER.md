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
- **目标设备：** RK3588 按[测试矩阵 R1](test-matrix.md)在 Docker 容器内完成探针与 DSM 验收；不允许以宿主直接运行 QEMU 或修改宿主内核/桥接替代。失败仅形成对应板型/内核组合的结论。
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
- **当前策略：** 按 [ADR 0009](ADR/0009-owned-bootloader-source.md) 接管 DockDSM Bootloader；[源码审计](bootloader-source-audit.md)已识别浮动 Buildroot/releases、预编译 blob 和许可适用范围缺口。许可证/二进制来源/可构建源码闭包未关闭前，保留固定研究 submodule，不整体迁移或捆绑争议产物；不迁入授权/序列号绕过，保持 Virtual DSM/DS124。
- **关闭证据：** 确认适用许可及 DSM 使用约束；独立 profile 通过全新盘安装、管理面、持久化、干净关机和升级恢复验收后，另行决定支持范围。

### RISK-007（P1）：Mac 容器后端的加速、持久化与性能选型未验证

- **阻断 Gate：** Apple container、Docker Desktop VZ/VMM 的 DockDSM 支持和“最佳性能”声明；不否定已有 Colima K5 历史证据。
- **问题：** 外层 VMM 可运行容器不保证内部 QEMU 获得 KVM；OCI 镜像兼容不保证 Docker API、Compose、卷、信号和健康检查兼容。存储落点与双层网络可能主导实际 DSM 性能。
- **当前策略：** [W12/Mac 选型](mac-container-evaluation.md)先做固定版本资格筛选，再以相同 QEMU/PAT/负载测量。KVM 路径保留，HVF 宿主运行不计入容器化结果；未测不排名。
- **关闭证据：** 所选后端的容器内加速、实际 DSM H0–H6、备份恢复及可重复对照结果；候选失败原因与未支持项单列。

### RISK-008（P1）：机器人自动写入与自动派单端到端未验收

- **阻断 Gate：** 宣称无人值守的小修复闭环已验证；不阻断带人工审查的试运行。
- **问题：** Triage 规则已配置，但尚无本次规则实际生成提交的证据；Actions 加标签后的 Jules App 接单、试用/额度和实际分支写入仍需真实任务验证。标签、模型风险分级、路径候选和自然语言指令均非文件级写权限隔离。
- **当前策略：** 按[自动化约定](bot-automation.md)限制仓库、低风险和两轮上限；Issue 仅接受维护者授权且不执行外部输入；单写入者、最终 diff 审阅、CI 与人工合并。需要额外计费时停止并交维护者处理。
- **关闭证据：** 真实低风险 Issue → Actions → Jules PR、原生规则修复与停止/交接均保留审计记录，确认 CI 不被削弱、费用边界及高风险不自动执行。

### RISK-009（P1）：APT 与镜像上游重建信息未完整锁定

- **阻断 Gate：** 声称完整 bit-for-bit 镜像可重复；不阻断固定 OCI/Python/QEMU 源码身份下的静态审查。
- **问题：** Docker 基础镜像、BuildKit frontend、qemu-host、patology、Python 包、QEMU 源码及其 Meson 子项目 commit 已固定。但 `apt-get update` 仍从滚动 Trixie 仓库解析 build/runtime packages；目前仅记录了 amd64 本次直接依赖版本。qemux 基础镜像的上游 Dockerfile/source provenance 也未独立审计。
- **当前策略：** 依赖身份、SHA256、当前 amd64 APT 解析版本见[依赖清单](dependency-locks.md)。不猜测 snapshot 日期或包版本；维持现有双架构构建和生产 QEMU 补丁流程。
- **关闭证据：** 为 amd64/arm64 确认 Debian snapshot 和完整安装闭包，记录包来源身份，并核实 qemux 基础镜像上游构建来源；原生两架构构建与镜像回归通过。

## 已关闭风险

- [RISK-001：Phase 3 严格 F5](archive/risks/2026-10.md#risk-001)。
