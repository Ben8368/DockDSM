# DockDSM Bootloader 与第三方 ARC 研究入口

> 本文保留固定 ARC 研究入口和 overlay 契约。自主源码、品牌与阶段顺序以 [ADR 0009](ADR/0009-owned-bootloader-source.md)、[源码审计](bootloader-source-audit.md)和[实施计划](implementation-plan.md)为准；执行状态见 [CONTEXT](../CONTEXT.md)。

## 目标架构

```text
Profile + Boot Provider
├─ virtualdsm：保留既有引导
├─ rtd1619b：保留 DS124 direct kernel boot
└─ full-x86_64（拟议）：独立 loader 镜像 → DSM
             ↓
Runtime adapter → 容器内 QEMU VM → DSM guest
```

Docker 负责运行 QEMU 进程，并不直接提供虚拟化。ARC 在同一台 QEMU VM 中作为 DSM 引导阶段，不是 ARC 再启动一个嵌套 QEMU VM 来运行 DSM。ARC 公开 Docker 示例使用独立 loader 镜像与数据盘；具体实现、设备参数和端口须按固定版本复核并在 DockDSM 中独立验证。

首个 PoC 只安排在 x86 Docker（测试矩阵 X4）。RK3588 继续限制为 Docker 内既有 ARM 路径；Mac 容器后端选型不依赖 ARC。ARC 管理界面、loader 就绪与 DSM 就绪分别观察。

## 当前代码事实

- `src/entry.sh` 根据 `DSM_PLATFORM` 建立当前虚拟机启动命令。
- `src/platform/virtualdsm.sh` 是现有 Virtual DSM x86 启动路径。
- `src/platform/rtd1619b.sh` 是 DS124 ARM64 的直接 kernel/initrd 路径，依赖现有 QEMU ARM64 补丁和特定磁盘/硬件契约；它不是 ARC，也不能直接视为可插入 ARC 的现成模块。
- `vendor/arc` 以 Git submodule 固定 ARC 上游源码；DockDSM overlay 独立位于 `patches/arc/`。它不进入现有镜像构建路径。初始化和补丁说明见 [ARC 研究说明](../research/arc/README.md)；来源与许可边界见 [PROVENANCE](PROVENANCE.md)。

### 源码融合状态

- 已固定上游快照 `99195dbdf4e0a21c5304ddb06e07dc57419679bc`（ARC 4.1.2），不跟随浮动分支自动更新。
- DockDSM overlay 在型号列表显示规范化架构，并在受限列表中按 host arch 过滤；既有配置缺省 `x86_64`，CPU 特性读取兼容 ARM64 的 `Features` 字段。`arm64-efi` GRUB 交叉编译、EFI 分区标记、内嵌 GRUB 镜像工作流和更新包中的 ARM64 EFI GRUB 模块已加入；运行时标题、启动横幅和一般操作界面使用 DockDSM 品牌，ARC 来源/许可标注、内部配置键与上游 API 标识仍保留。固定配置表仍只有 x86 型号，尚无 ARM DSM profile、ARM runtime kernel/rootfs 或实际 ARC ARM 启动证据。
- 上游 README 的禁止商业使用声明、仓库 GPL-3.0 `LICENSE` 与个别文件 MIT 头部尚未厘清。当前用 submodule 保持源码来源边界，不把源码/构建产物捆绑至 DockDSM 镜像或发布物。
- 这是源码入口与 UI overlay 的隔离研究接入，不等同于 `full-x86_64` profile、DSM 安装/启动或生产支持已经实现。

## 既有研究门禁

以下保留技术门禁；阶段执行顺序由 [ADR 0009](ADR/0009-owned-bootloader-source.md) 接管，不再把性能基线作为静态源码接管的前置条件。

### 兼容与运行门禁

[实施计划](implementation-plan.md) G0–G4 定义输入、设备基线、性能对照、等价和恢复证据。源码审计与接管先按 Phase 1 推进；新运行路径必须完成适用的旧平台回归、存储隔离及对应设备验收，不以三设备性能实验阻断静态接管。

### Phase 3：DockDSM Bootloader x86 隔离 PoC（G5 / W50）

1. 固定 ARC 源码/发布版本和校验；梳理 loader、Buildroot、模型配置、内核/ramdisk 生成链及每个被采用组件的许可证/声明。
2. 建立独立的 x86 profile、Compose/数据目录和 QEMU 参数，不复用现有 vDSM/DS124 数据盘，不覆盖当前默认平台。
3. 验证 Docker 内 QEMU 的 KVM 设备、CPU/机器型号、loader 控制台/管理网络和 Docker 端口发布；KVM 不可用时明确报告，不伪造加速。
4. 在全新可丢弃磁盘上验证 DockDSM Bootloader 配置、DSM 启动/安装、卷与重启持久性、DSM UI 干净关机、容器停止超时和升级失败恢复。
5. 单独评审 DSM 型号与 Synology PAT/EULA 约束；不实现序列号伪造、服务/许可解锁或绕过授权机制。

PoC 交付包需包含固定 commit/release、loader 校验、所有动态下载依赖的锁定清单、QEMU 机器/设备/磁盘连接表、loopback 管理端口清单、空盘安装/两次干净生命周期/停机备份恢复证据。关闭或受控处理 loader 自更新，避免运行中漂移。无法审清组件边界则保留研究记录，不捆绑分发。

扩展性验收：新增 profile/provider 与注册信息即可运行，不修改 `virtualdsm`/`rtd1619b` 的安装和磁盘逻辑。拟议 `full-x86_64` 标识必须在实现及回归后显式注册，当前 `DSM_PLATFORM` 不接受它；不将研究名称 `arc-x86` 作为新公开接口。

### Phase 4：ARM64 Bootloader 可行性研究（W61）

x86 工作链验收后，先做移植可行性矩阵，不把 x86 Buildroot/内核/继承应用假定为可跨架构复用：

本轮目标是将固定 ARC 4.1.2 的引导能力逐步移植为 DockDSM Bootloader，并保留源码来源与许可记录。集成边界由固定 `vendor/arc` submodule 与 `patches/arc/` overlay 组成；当前 checkout 中 submodule 工作树尚未初始化，overlay 也尚未进入生产镜像构建。ARM64 移植状态与缺口见[评估](../research/arc/arm64-port-assessment.md)。

ARM64 UEFI → GRUB → Buildroot loader → kexec 的开放 Linux 实验仅验证底层启动部件，不运行 ARC 用户空间或 DSM；它不是 ARC ARM64 移植完成的证据。[实验说明](../research/arm64/grub-loader/README.md)

- ARM64 loader kernel、initrd/Buildroot 用户空间与启动介质格式是否可构建及维护；
- QEMU `aarch64` machine、固件/UEFI 或直接启动方式，与 ARC 预期 boot flow 的接口；
- ARC 的硬件探测、驱动/addon、模型配置、DSM 平台选择及内核/ramdisk 修改是否能抽象出 ARM64 后端；
- DS124 `rtd1619b` 当前 QEMU 设备、QEMU patches、磁盘布局、console/network 和启动参数哪些可复用，哪些必须重写；
- 同架构 ARM64 KVM 与 amd64→ARM64 TCG 的构建/运行差异，目标硬件与可重复 CI 测试环境。

该阶段以 DockDSM Bootloader 的 ARM64 专用 backend 为目标；可复用配置和构建逻辑，不能强用 x86 内核/启动设备。未确认架构、许可、源码与交接兼容前，不宣称移植完成。

先交付 go/no-go 报告：比较相对 direct boot 的用户价值、可构建组件、内核交接方式、需新增的硬件适配、维护成本与阻断项。可行性不足时暂缓，DS124 direct boot 仍可独立推进。需要外部协作时另行取得发送消息的授权。

### 支持门禁

只有 ARM64 loader 可重复构建、在声明的目标硬件以真实启动链冷启动、DSM 完成安装并验证磁盘持久性/网络/干净关机/恢复，且依赖与许可审查完成后，才更新支持矩阵。Apple VZ nested KVM 或合成测试单独不足以代表裸机 ARM64 支持。

## 保持不变的安全与兼容要求

- 新 Bootloader profile 使用全新隔离数据目录；不自动导入、重分区或格式化旧存储。
- loader 管理端口默认只绑定 loopback/受保护网络；明确区分 loader ready 与 DSM configured/volume/HTTP ready。
- DSM 型号、PAT、包/Surveillance Station 授权边界分别记录，不能因 loader 改变而推断授权或兼容性。
- 生产 QEMU 补丁仍只能从 `patches/qemu/8.2.2/` 进入；研究用 ARM 补丁先隔离并评审。
- 仓库来源、许可证及项目致谢见 [PROVENANCE](PROVENANCE.md)，长期决定见 [ADR 0009](ADR/0009-owned-bootloader-source.md)，未解决风险见 [RISK-006](RISK_REGISTER.md)。

## 固定参考资料

以下为本次路线制定时核对的公开项目资料；实施前须再次固定到实际采用的版本并复核。

- [ARC README（commit `99195dbdf4e0a21c5304ddb06e07dc57419679bc`）](https://github.com/AuxXxilium/arc/blob/99195dbdf4e0a21c5304ddb06e07dc57419679bc/README.md)：说明 x86-64 loader、构建流程及项目使用声明。
- [ARC Docker 说明](https://github.com/AuxXxilium/arc/blob/99195dbdf4e0a21c5304ddb06e07dc57419679bc/docker.md) 与 [Dockerfile](https://github.com/AuxXxilium/arc/blob/99195dbdf4e0a21c5304ddb06e07dc57419679bc/Dockerfile)：QEMU 容器的 loader 镜像、数据盘及端口示例。
- [ARC LICENSE](https://github.com/AuxXxilium/arc/blob/99195dbdf4e0a21c5304ddb06e07dc57419679bc/LICENSE)：标记 GPL-3.0；应与 README 的使用声明及具体组件声明一并审查。
- [vdsm/virtual-dsm](https://github.com/vdsm/virtual-dsm)：DockDSM 现有代码的来源之一；完整来源记录见 [PROVENANCE](PROVENANCE.md)。
