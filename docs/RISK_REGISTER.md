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
- **问题：** 上游 x86 Docker/QEMU 示例不能替代本仓库的完整 DSM 启动、模型、存储、网络、健康检查、关机、升级/恢复证据；固定镜像 workflow 仅取 `apex`/`bzImage-apex` 并暂存 x86 GRUB，ARM64 Buildroot/runtime/DSM model 路径尚未建立；README 使用声明与 GPLv3 LICENSE 的适用边界仍需澄清。
- **当前策略：** 按 [ADR 0009](ADR/0009-owned-bootloader-source.md) 接管 DockDSM Bootloader；[源码审计](bootloader-source-audit.md)已识别浮动 Buildroot/releases、预编译 blob 和许可适用范围缺口。许可证/二进制来源/可构建源码闭包未关闭前，保留固定研究 submodule，不整体迁移或捆绑争议产物；不迁入授权/序列号绕过，保持 Virtual DSM/DS124。
- **组件证据：** 逐项门禁与缺口以 [component-manifest.json](../research/bootloader/component-manifest.json) 为唯一状态表；[取证记录](archive/reviews/2026-10-23-bootloader-component-admission.md)区分 Buildroot 多端点不可访问、LKM/Custom 无实现源码、Modules 缺失 src/ 及动态 SDK/firmware、GRUB seed 缺对应源码。ARM64 overlay 现状见[移植评估](../research/arc/arm64-port-assessment.md)；离线检查不解除准入或分发阻断。
- **关闭证据：** 确认适用许可及 DSM 使用约束；独立 profile 通过全新盘安装、管理面、持久化、干净关机和升级恢复验收后，另行决定支持范围。

### RISK-007（P1）：Mac 容器后端的加速、持久化与性能选型未验证

- **阻断 Gate：** Apple container、Docker Desktop VZ/VMM 的 DockDSM 支持和“最佳性能”声明；不否定已有 Colima K5 历史证据。
- **问题：** 外层 VMM 可运行容器不保证内部 QEMU 获得 KVM；OCI 镜像兼容不保证 Docker API、Compose、卷、信号和健康检查兼容。存储落点与双层网络可能主导实际 DSM 性能。
- **当前策略：** [W12/Mac 选型](mac-container-evaluation.md)先做固定版本资格筛选，再以相同 QEMU/PAT/负载测量。KVM 路径保留，HVF 宿主运行不计入容器化结果；未测不排名。
- **关闭证据：** 所选后端的容器内加速、实际 DSM H0–H6、备份恢复及可重复对照结果；候选失败原因与未支持项单列。

### RISK-008（P1）：机器人自动写入与自动派单端到端未验收

- **阻断 Gate：** 宣称无人值守的小修复闭环已验证；不阻断带人工审查的试运行。
- **问题：** Triage 规则已配置，但尚无本次规则实际生成提交的证据；已有 [Issue #22](https://github.com/Ben8368/DockDSM/issues/22#issuecomment-6368743907) → [PR #24](https://github.com/Ben8368/DockDSM/pull/24) 的 Jules 接单/交付回执，但扩容后的队列/冲突检查、Tooling、环境快照及停止/交接尚未端到端验收。标签、模型风险分级、路径候选和自然语言指令均非文件级写权限隔离。
- **当前策略：** 按[自动化约定](bot-automation.md)限制仓库、低风险和两轮上限；Issue 仅接受维护者授权且不执行外部输入；单写入者、最终 diff 审阅、CI 与人工合并。需要额外计费时停止并交维护者处理。
- **关闭证据：** 真实低风险 Issue → Actions → Jules PR、原生规则修复与停止/交接均保留审计记录，确认 CI 不被削弱、费用边界及高风险不自动执行；新增工作包类别须有环境预检、路径占用/容量拒绝及交付样本。

### RISK-009（P1）：APT 与镜像上游重建信息未完整锁定

- **阻断 Gate：** 声称完整 bit-for-bit 镜像可重复；不阻断固定 OCI/Python/QEMU 源码身份下的静态审查。
- **问题：** Docker 基础镜像、BuildKit frontend、qemu-host、patology、Python 包、QEMU 源码及其 Meson 子项目 commit 已固定。但 `apt-get update` 仍从滚动 Trixie 仓库解析 build/runtime packages；目前仅记录了 amd64 本次直接依赖版本。qemux 基础镜像的上游 Dockerfile/source provenance 也未独立审计。
- **当前策略：** 依赖身份、SHA256、当前 amd64 APT 解析版本见[依赖清单](dependency-locks.md)。不猜测 snapshot 日期或包版本；维持现有双架构构建和生产 QEMU 补丁流程。
- **关闭证据：** 为 amd64/arm64 确认 Debian snapshot 和完整安装闭包，记录包来源身份，并核实 qemux 基础镜像上游构建来源；原生两架构构建与镜像回归通过。

### RISK-010（P1）：kexec 后继承的 GICv3 LPI 表覆盖 target kernel

- **阻断 Gate：** ARM64 Bootloader 的 DS124/GICv3 kexec 兼容性声明；不阻断开放 Linux 的 GICv2 或 GICv3 ITS-off 研究 smoke。
- **问题：** 原 `kexec_file_load`（`kexec -s`）路径即使传入 `--mem-min=0x42000000`，仍将 Buildroot/Linux 6.12.112 target kernel 放在 `0x41000000`，与 loader LPI property/pending tables (`0x41060000`/`0x41070000`) 重叠；target 重置 64 KiB property table 时覆盖自身文本并 Oops。改用 legacy `kexec_load`（`kexec -c`）后，下界生效，open Linux GICv3/A55/ITS-on 在 loader LPI 保持开启时从 `0x42000000` 开始加载并通过 handoff。官方 DS124 7.2.2-72806 在 loader LPI 开启时虽到达 login，但输出 `Booted with LPIs enabled, memory probably corrupted`，并进入内核 damage-control 路径、taint 后关闭 LPI；故 DS124 研究 provider 继续要求 loader-only `irqchip.gicv3_nolpi=1`。结合 `kexec_load --mem-min` 后，DS124 diskless handoff 所有段均位于 `0x42000000` 以上，loader 与 target 不再有该警告，DSM target 在 `0x40170000` 分配新 property table并到达 login。
- **证据与边界：** 配置、命令和日志见[ARM64 loader 研究记录](../research/arm64/loader/README.md)。2026-10-25 官方 DS124 72806 内核使用通用 `linux,dummy-virt` DTB，在同一 patched QEMU TCG VM 经 kexec 到无盘 login；独立 scratch probe 发现 `rtk_ahci`、SATA link、`QEMU HARDDISK` 和 4,194,304 扇区。stock DSM initrd 在 snapshot-backed 2 GiB sparse scratch 上再次到达 login，预期 timeout 后 backing 仍为 mode 0600、单链接、0 allocated blocks。patched sysbus AHCI 对 `readonly=on` 在 guest 启动前报 `Block node is read-only`；通过配置让 guest 看见可写临时 COW overlay，验证只证明 backing 未改变，不证明 guest 设备为只读。上述证据不证明 DSM 用户数据盘、分区、卷、网络、安装、持久化、管理面或设备验收。研究参数不进入生产 profile。
- **关闭证据：** 对选定 QEMU `virt`/补丁契约验证设备树、内存、CPU、串口、存储和网络；在独立测试盘完成 DSM 安装、持久化、干净关机与恢复，并证明 ITS 生命周期安全。TCG 登录提示不等于 DS124 硬件或 DSM 生命周期验收。

### RISK-011（P2）：ARM64 UEFI/GRUB loader 尚无真实构建与启动证据

- **阻断 Gate：** ARM64 UEFI/GRUB loader 支持声明；不阻断已验证的 ARM64 direct boot 或 DS124 kexec 研究结论。
- **问题：** `research-arm64-grub-linux` 原型与合成契约检查已实现；Buildroot 2025.02.19 源树 provenance 校验通过，但 ARM64 Colima 构建停在 glibc 完整 Git 历史下载，未产出镜像；AArch64 UEFI QEMU 串口启动链也未验证。
- **当前策略：** 保持 research-only；重试时用 VM 本地输出和下载缓存，在 Linux 上以验证过的 Buildroot 2025.02.19 及外部 AArch64 UEFI firmware 完成构建与 TCG 冷启动，不注册 `full-arm64`。
- **关闭证据：** 记录 Buildroot 输入身份与镜像 SHA256、实际串口日志中的 GRUB/kexec/目标关机标记及 QEMU 退出码 0；DSM 安装与目标设备验收另行过门禁。[实验记录](../research/arm64/grub-loader/README.md)

## 已关闭风险

- [RISK-001：Phase 3 严格 F5](archive/risks/2026-10.md#risk-001)。
