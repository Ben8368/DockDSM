# ARC ARM64 移植可行性评估

> 本报告评估固定 ARC 4.1.2 快照 `99195dbdf4e0a21c5304ddb06e07dc57419679bc` 的 ARM64 移植边界。ARC 来源、组件准入和分发状态以[源码锁](../bootloader/source-lock.json)、[组件清单](../bootloader/component-manifest.json)及 [RISK-006](../../docs/RISK_REGISTER.md#risk-006p1arc-集成尚无运行与许可边界证据)为准；本报告不构成许可意见。

## 决策

- **研究方向：** 按项目目标，继续把固定 ARC 4.1.2 向 ARM64 移植；最终产品品牌为 DockDSM Bootloader，并保留 ARC 来源/许可证记录。
- **研究边界：** 通过 `patches/arc/` overlay 与隔离测试推进，不执行上游危险构建脚本，不整体导入源码/二进制。
- **生产门禁：** 保持关闭。RISK-006、ARM Buildroot/工具链闭包及目标 DSM 生命周期证据未关闭前，不构建/分发组合产物，不注册 `full-arm64` 或更改现有 `DSM_PLATFORM` 白名单。

## 证据与复用范围

ARC 4.1.2 README 将目标描述为 x86-64 PC/VM；其流程为 GRUB → ARC Buildroot 用户空间 → 生成 DSM boot files → `kexec` 交接。固定快照中的 GRUB 构建脚本默认只构建 `i386-pc`、`i386-efi` 和 `x86_64-efi`；启动菜单参数包含 x86 I/O 串口地址和 x86 内核选项。ARM 不是增加一个 QEMU binary 或 `DSM_PLATFORM` 分支就能启用的架构。

现有 DockDSM ARM64 研究可复用的部分：

- 版本化 `BootProvider` / `LaunchPlan` 契约与 `qemu-process` adapter。
- `research-arm64-linux-kexec` 的开放 Linux handoff。
- `research-arm64-dsm-kexec` 的 DS124 DSM kernel/initrd handoff；固定实验在 QEMU `virt` / GICv3 / TCG 下到达 DSM login，loader LPI 关闭，且没有 DSM 系统盘、网络或安装。
- 既有 `rtd1619b` direct boot 的 QEMU 设备、磁盘和生命周期证据；它不代表 ARC loader 的 ARM64 用户空间或启动介质已移植。

上述证据仅证明可复用的 QEMU/ARM64 交接部件和 DS124 实验路径。独立 ARM64 UEFI/GRUB 到 open Linux loader 的 Buildroot 原型及合成契约检查已实现；ARM64 Colima VM 已启动，Buildroot 实际构建和冷启动证据仍待取得。它们没有证明 ARC 用户空间可在 ARM64 构建或运行，也没有验证 ARC 的 DSM 构建流程。

固定 ARC 4.1.2 的 GRUB 构建默认目标为 `i386-pc`、`i386-efi`、`x86_64-efi`，但脚本已有目标列表参数；上游镜像工作流基线只暂存这些 x86 GRUB 目标，并固定获取 `apex`、检查 `bzImage-apex`/`initrd-apex`。ARC Configs 当前列出的平台族也均为 x86。研究 overlay 的 `0001` 将受限型号列表按 host arch 过滤，在 ARM64 上读 `Features`，并在“Show all”模式对架构不匹配的型号发出警告；当前没有 ARM profile，因此不会把现有 x86 模型报为兼容。`0002` 为 `grub.cfg` 增加 ARM64 `Image-*` loader 路径、按文件存在选择 DSM `Image-dsm` 或 `/zImage-dsm`、从 `grubenv` 读取可选板级串口与 kernel cmdline，并将引导菜单品牌改为 DockDSM；`0003` 为 `arm64-efi` 指定 AArch64 交叉工具链，并仅在目标含 `arm64-efi` 时把 GRUB FAT 分区标为 MBR EFI 类型 `0xef`；`0004` 将运行时标题、启动横幅和操作界面改为 DockDSM；`0005` 把 ARM64 目标加入内嵌 GRUB 镜像生成工作流；`0006` 把 ARM64 EFI GRUB 模块纳入 loader 更新包。即使 GRUB 工件生成成功，现有 workflow 仍只取得 x86 `apex` kernel/rootfs，且没有 ARM DSM profile、ARM Buildroot runtime 或 DSM kexec 启动证据。

## 直接移植的缺口

1. **ARM64 启动介质：** 为 `virt`/目标设备确定 ARM64 UEFI 或其它启动方式，生成可重复构建的 ARM64 GRUB/loader image，并验证 GRUB → ARM64 loader kernel。
2. **ARC Buildroot 闭包：** 获取并锁定 ARM64 defconfig、kernel、toolchain、软件包与完整源码。`arc-buildroot-essential`、`arc-buildroot-evo` 及 ARC 的 addons/modules/configs 等仍未闭合来源、版本或许可。
3. **ARC 应用与模型：** 确认 ARC 的 shell/Web/本机二进制在 aarch64 上可构建；定义 ARM DSM model、PAT 身份、kernel/initrd 处理与所需驱动/addon。当前 ARC 固定支持表是 x86 型号，不含经验证的 ARM profile。
4. **DSM 交接与硬件：** 将模型专用 ARM kernel/initrd、DTB、GIC、UART、SATA/网络等需求接入 ARM loader；分别验证 TCG、同架构 KVM 和目标设备，不能由 `rtd1619b` direct boot 代替。
5. **数据及生命周期：** 使用全新隔离存储完成安装、配置、卷、跨重启持久性、DSM 干净关机和恢复验收；不复用 Virtual DSM 或既有 DS124 运行盘。
6. **准入：** 关闭 ARC 根 GPLv3、README 非商业声明、文件级 MIT 头及第三方组件的范围问题；确认每项源码、构建产物和分发材料的来源与权利。RISK-006 未关闭前，不整体迁入或捆绑 ARC 组合产物。

## 推荐后续顺序

1. 继续通过 overlay 为 GRUB、Buildroot/kernel、ARC 用户空间与 DSM 交接增加独立 ARM64 分支；每一步保持 x86 默认路径和回退行为不变。
2. 获取并锁定 ARM64 Buildroot、`kexec`/GRUB 工具链及 ARC ARM64 runtime 依赖。当前 Essential/Evo 源码仓库不可访问，依赖闭包和权利范围仍按 RISK-006 处理；缺少输入时不运行上游 `scripts/grub.sh` 或镜像构建 workflow。
3. 以现有 DS124 / `rtd1619b` ARM64 路径为首个候选目标，确认实际 ARC DSM model/PAT、DTB、设备及 kernel/initrd 接口；完成 ARM64 loader → ARC menu → DSM kexec 的同 VM 测试。
4. 目标真实冷启动、DSM 安装/网络/存储/持久性/关机/恢复验收，以及依赖与许可审查全部完成后，才可申请生产支持。

## 参考

- [锁定 ARC 4.1.2 README](https://github.com/AuxXxilium/arc/blob/99195dbdf4e0a21c5304ddb06e07dc57419679bc/README.md)
- [锁定 ARC 4.1.2 GRUB 构建脚本](https://github.com/AuxXxilium/arc/blob/99195dbdf4e0a21c5304ddb06e07dc57419679bc/scripts/grub.sh)
- [锁定 ARC 4.1.2 GRUB 启动菜单](https://github.com/AuxXxilium/arc/blob/99195dbdf4e0a21c5304ddb06e07dc57419679bc/files/p1/boot/grub/grub.cfg)
- [DockDSM ARM64 kexec 研究](../arm64/loader/README.md)
- [ARC 集成研究入口](../../docs/arc-integration.md)
