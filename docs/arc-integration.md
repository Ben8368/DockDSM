# DockDSM ARC 与 ARM64 路线

> 当前状态：ARC 未集成；ARC ARM64 移植尚未开始。这里记录目标和分阶段工程门槛，不代表已完成合并或支持。

## 目标架构

```text
Docker（生命周期、隔离、卷、端口）
└─ QEMU VM（优先同架构 KVM；可用性由宿主与权限决定）
   └─ ARC loader（先 x86-64；未来评估 ARM64 port）
      └─ ARC 构建并交接 DSM 启动文件/内核/ramdisk
         └─ DSM guest
```

Docker 负责运行 QEMU 进程，并不直接提供虚拟化。ARC 在同一台 QEMU VM 中作为 DSM 引导阶段，不是 ARC 再启动一个嵌套 QEMU VM 来运行 DSM。ARC 公开 Docker 示例使用独立 loader 镜像与数据盘；具体实现、设备参数和端口须按固定版本复核并在 DockDSM 中独立验证。

## 当前代码事实

- `src/entry.sh` 根据 `DSM_PLATFORM` 建立当前虚拟机启动命令。
- `src/platform/virtualdsm.sh` 是现有 Virtual DSM x86 启动路径。
- `src/platform/rtd1619b.sh` 是 DS124 ARM64 的直接 kernel/initrd 路径，依赖现有 QEMU ARM64 补丁和特定磁盘/硬件契约；它不是 ARC，也不能直接视为可插入 ARC 的现成模块。
- `docs/PROVENANCE.md` 说明 DockDSM 与 vdsm/virtual-dsm 的代码来源；ARC 当前仅为致谢的参考项目，并未合并其代码。

## 实施路线

### 阶段 A：x86 ARC 隔离 PoC

1. 固定 ARC 源码/发布版本和校验；梳理 loader、Buildroot、模型配置、内核/ramdisk 生成链及每个被采用组件的许可证/声明。
2. 建立独立的 x86 profile、Compose/数据目录和 QEMU 参数，不复用现有 vDSM/DS124 数据盘，不覆盖当前默认平台。
3. 验证 Docker 内 QEMU 的 KVM 设备、CPU/机器型号、loader 控制台/管理网络和 Docker 端口发布；KVM 不可用时明确报告，不伪造加速。
4. 在全新可丢弃磁盘上验证 ARC 配置、DSM 启动/安装、卷与重启持久性、DSM UI 干净关机、容器停止超时和升级失败恢复。
5. 单独评审 DSM 型号与 Synology PAT/EULA 约束；不实现序列号伪造、服务/许可解锁或绕过授权机制。

### 阶段 B：ARM64 ARC/loader 适配研究

先做移植可行性矩阵，不把 x86 Buildroot/内核/ARC 应用假定为可跨架构复用：

- ARM64 loader kernel、initrd/Buildroot 用户空间与启动介质格式是否可构建及维护；
- QEMU `aarch64` machine、固件/UEFI 或直接启动方式，与 ARC 预期 boot flow 的接口；
- ARC 的硬件探测、驱动/addon、模型配置、DSM 平台选择及内核/ramdisk 修改是否能抽象出 ARM64 后端；
- DS124 `rtd1619b` 当前 QEMU 设备、QEMU patches、磁盘布局、console/network 和启动参数哪些可复用，哪些必须重写；
- 同架构 ARM64 KVM 与 amd64→ARM64 TCG 的构建/运行差异，目标硬件与可重复 CI 测试环境。

该阶段可能需要与 ARC 项目协作或维护独立 ARM64 loader fork；未确认上游架构许可、维护边界及必要组件兼容前，不承诺“两个仓库已合并”。

### 阶段 C：支持门禁

只有 ARM64 loader 可重复构建、在声明的目标硬件以真实启动链冷启动、DSM 完成安装并验证磁盘持久性/网络/干净关机/恢复，且依赖与许可审查完成后，才更新支持矩阵。Apple VZ nested KVM 或合成测试单独不足以代表裸机 ARM64 支持。

## 保持不变的安全与兼容要求

- ARC profile 使用全新隔离数据目录；不自动导入、重分区或格式化旧存储。
- loader 管理端口默认只绑定 loopback/受保护网络；明确区分 loader ready 与 DSM configured/volume/HTTP ready。
- DSM 型号、PAT、包/Surveillance Station 授权边界分别记录，不能因 loader 改变而推断授权或兼容性。
- 生产 QEMU 补丁仍只能从 `patches/qemu/8.2.2/` 进入；研究用 ARM 补丁先隔离并评审。
- 仓库来源、许可证及项目致谢见 [PROVENANCE](PROVENANCE.md)，长期决定见 [ADR 0004](ADR/0004-reinitialized-history-and-arc-roadmap.md)，未解决风险见 [RISK-006](RISK_REGISTER.md)。

## 固定参考资料

以下为本次路线制定时核对的公开项目资料；实施前须再次固定到实际采用的版本并复核。

- [ARC README（commit `1e227408465a08660289c9a782edacd067cf747b`）](https://github.com/AuxXxilium/arc/blob/1e227408465a08660289c9a782edacd067cf747b/README.md)：说明当前 x86-64 loader、Buildroot/kexec 流程、full DSM 与 vDSM 区别及项目使用声明。
- [ARC Docker 说明](https://github.com/AuxXxilium/arc/blob/1e227408465a08660289c9a782edacd067cf747b/docker.md) 与 [Dockerfile](https://github.com/AuxXxilium/arc/blob/1e227408465a08660289c9a782edacd067cf747b/Dockerfile)：QEMU 容器的 loader 镜像、数据盘及端口示例。
- [ARC LICENSE](https://github.com/AuxXxilium/arc/blob/1e227408465a08660289c9a782edacd067cf747b/LICENSE)：采用/分发前须结合 README 声明及具体组件进行许可审查。
- [vdsm/virtual-dsm](https://github.com/vdsm/virtual-dsm)：DockDSM 现有代码的来源之一；完整来源记录见 [PROVENANCE](PROVENANCE.md)。
