<h1 align="center">DockDSM</h1>

<p align="center">用 Docker 管理 DSM 虚拟机，让部署、启动和维护有清晰边界。</p>

[![CI](https://github.com/Ben8368/DockDSM/actions/workflows/test.yml/badge.svg?branch=master)](https://github.com/Ben8368/DockDSM/actions/workflows/test.yml)
[![CodeQL](https://github.com/Ben8368/DockDSM/actions/workflows/codeql.yml/badge.svg?branch=master)](https://github.com/Ben8368/DockDSM/actions/workflows/codeql.yml)

## 项目定位

DockDSM 是独立维护的 DSM 虚拟化容器方案。Docker 管理 QEMU 进程、网络、持久化卷与生命周期；DSM 在拥有独立内核的虚拟机中运行，不是共享宿主内核的普通应用容器。同架构且宿主允许时使用 KVM，跨架构依赖较慢的 TCG。

**目标架构：控制层 → 平台配置与可选启动提供者 → 容器化 QEMU → DSM。**

我们采用性能基线起步、逐步重构运行架构的路线：保留 Virtual DSM 与 ARM64 direct boot，ARC 作为后续独立启动提供者接入。ARC 与 DSM 是同一台 VM 内的不同启动阶段。设计决定见 [ADR 0006](docs/ADR/0006-runtime-profiles-and-container-first.md)。

> **当前还没有集成 ARC。** 现有代码可运行 Virtual DSM x86，并提供实验性的 DS124 ARM64 direct-boot 路径。ARM64 容器镜像、ARM64 DSM 与 ARM64 ARC 是三件不同的事；不能把已有 ARM64 路径当作 ARC 移植已经完成。

## 能力边界

| 路径 | 当前实现 | 限制 |
| --- | --- | --- |
| `DSM_PLATFORM=virtualdsm` | 默认 x86 Virtual DSM 启动路径 | ARM64 宿主运行 x86 guest 使用 TCG；KVM 需同架构及可用设备 |
| `DSM_PLATFORM=rtd1619b` | 实验性 DS124 ARM64 直接 kernel/initrd 启动 | 仅 DSM 7.2.2-72806 与精确官方 PAT；单盘 Basic/Btrfs 有证据 |
| ARC x86-64 | 计划中的隔离 PoC | 尚未合入；不能用于现有数据盘 |
| ARC ARM64 | 后续 loader 可行性研究 | 尚未实现，不在当前支持范围 |

现有 ARM64 KVM 证据来自 Apple M5 / Colima Apple VZ / ARM64 Linux 的嵌套 KVM 环境，不代表裸机 ARM64 或所有 ARM 主机。Surveillance Station 的实际摄像头、许可、录像/回放验收仍未完成。

详细参数与证据以 [平台契约](docs/platforms.md)、[当前状态](CONTEXT.md)和[兼容性矩阵](docs/surveillance-compatibility.md)为准。

## 从源码开始

需要 Linux Docker Engine、Compose v2、足够的磁盘空间和可访问构建依赖的网络。Windows/macOS 通常还依赖 Linux VM；Docker Desktop 本身不保证容器能够使用 KVM。

优先使用仓库提供的本地构建配置；它默认 TCG、仅绑定本机管理端口，不要求特权设备：

```bash
git clone https://github.com/Ben8368/DockDSM.git
cd DockDSM
# 默认 x86 Virtual DSM；启动前检查 DSM 的许可与硬件使用条件。
docker compose -f compose.local.yml build
docker compose -f compose.local.yml up -d
docker compose -f compose.local.yml logs -f
```

管理入口为 [HTTP 5000](http://127.0.0.1:5000) / [HTTPS 5001](https://127.0.0.1:5001)。安装和跨架构模拟可能耗时较长；进程启动或 HTTP 可达不等于已完成 DSM 配置与建卷。

- 默认持久化目录：`./storage-local`。已有安装须保持原目录和 `DSM_PLATFORM`；不要用切换平台的方法复用旧盘。
- ARM64 设置、KVM 显式启用、停止和恢复步骤见[部署指南](docs/getting-started.md)。
- 仓库重建**不会自动发布镜像**。`ghcr.io/ben8368/dockdsm` 是发布目标；注册表是否已有可用版本应以实际 Packages 与发布记录为准。在首次发布前不要直接依赖 `latest` 示例。

## 数据与安全

- 先备份再升级。试验 ARC 或重装必须使用全新隔离目录，不能自动迁移、重新分区或格式化现有磁盘。
- 先从 DSM UI 干净关机，再停止容器；Docker stop 超时后的终止不算干净关机。
- 管理端口默认只绑定 loopback；远程访问应经过可信网络或有鉴权的代理，不直接暴露公网。
- ARM64 路径使用用户态 NAT，不保证局域网发现或摄像头自动发现；DSM 升级超出已验证版本需独立评审。
- 不提供序列号伪造、服务解锁或授权绕过；不承诺额外摄像头许可、QuickConnect、商店或套件兼容。

## 工程路线与文档

1. 固定依赖并建立 x86、MacBook Air M5、RK3588 性能与兼容基线；RK3588 仅用 Docker 容器验证，Mac 对比容器后端后选型。
2. 先做加速、日志、网络和 I/O 单变量实验，再逐步分离平台配置、运行后端、生命周期与存储状态。
3. 通过旧路径兼容与恢复门禁后接入隔离的 ARC x86 PoC；Host QEMU 与 ARM64 loader 独立评估，不作为现有平台的前置依赖。

| 主题 | 文档 |
| --- | --- |
| 部署与本地构建 | [开始使用](docs/getting-started.md) |
| 平台参数与限制 | [平台接口](docs/platforms.md)、[环境变量](docs/environment.md) |
| 工程规划与架构 | [实施计划](docs/implementation-plan.md)、[运行架构](docs/runtime-architecture.md) |
| 设备与性能 | [测试矩阵](docs/test-matrix.md)、[性能协议](docs/performance-baseline.md)、[Mac 容器选型](docs/mac-container-evaluation.md) |
| ARC 与 ARM64 扩展 | [可选启动提供者路线](docs/arc-integration.md) |
| 包安装与诊断 | [安装说明](docs/package-installation.md)、[Surveillance Station](docs/surveillance-station.md) |
| 测试、CI 与发布 | [CI 设计](docs/ci.md)、[质量门禁](docs/QUALITY.md) |
| 协作 | [贡献指南](CONTRIBUTING.md)、[AI 入口](AGENTS.md)、[安全报告](SECURITY.md) |

## 致谢、来源与许可

感谢 [vdsm/virtual-dsm](https://github.com/vdsm/virtual-dsm) 提供 Docker/QEMU Virtual DSM 代码基础，感谢 [AuxXxilium/arc](https://github.com/AuxXxilium/arc) 提供引导器架构与实现参考。

DockDSM 自行维护产品方向与发布，不自动同步上述项目，也不代表任何项目或 Synology 官方背书。**独立维护不抹去代码来源**：继承的 MIT 条款、原作者与贡献者归属保留于 [license.md](license.md)、[NOTICE](NOTICE) 和 [PROVENANCE](docs/PROVENANCE.md)。ARC 当前仅为参考，未来引入其代码或产物前须逐组件审查许可与分发条件。

DSM、PAT、商标和其他第三方组件由相应权利人所有，不受 DockDSM 的 MIT 声明重新许可。使用前需自行确认 Synology EULA、目标硬件与相关使用条件；仓库不分发 DSM 专有镜像。
