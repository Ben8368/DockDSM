# ADR 0006：以平台配置和可选启动提供者逐步重构运行架构

- 状态：部分替代
- superseded by：[ADR 0009](0009-owned-bootloader-source.md)
- 替代范围：源码接管顺序、引导器品牌与自主维护方式由 [ADR 0009](0009-owned-bootloader-source.md) 接管；本 ADR 的既有平台兼容、分层、数据隔离与设备门禁继续有效。
- 日期：2026-10-22
- supersedes：ADR 0004 的统一 ARC 目标启动链和 ARC 优先顺序；保留其历史重建、来源归属、数据隔离与独立维护决定。

## 背景

维护者要求落实[架构与性能分析](https://chatgpt.com/share/6ad9a9ea-a228-83ea-9c94-b4c2aaadc0fa)的方向，本轮只做规划。此前路线把 ARC 作为全部平台目标启动层，容易使已有 DS124 direct boot 成果依赖尚未证明的 ARM64 loader。源码已经具有平台钩子、Python 安装/状态工具、QMP 退出观察和回归夹具，具备渐进拆分条件。

设备为 x86、MacBook Air M5、RK3588。维护者明确 RK3588 仅使用 Docker 容器验证；Mac 则要兼容 KVM，并评估最佳性能的容器化方案。

## 决策

1. 产品方向是具有明确兼容矩阵、可靠存储和生命周期的 DSM 虚拟化运行平台。采用性能基线 → 局部优化 → Profile/Runtime 分层 → 状态与恢复 → 新平台扩展的顺序。
2. 以 Python 实现后续本地控制层和类型化计划；Shell 保留为兼容启动适配层。首批不引入分布式服务、远程 API 或 Web UI，不重新实现现有 QEMU 设备。
3. Profile 声明 guest 硬件契约；Boot Provider 管理 vDSM legacy、DS124 direct kernel、未来 ARC loader；Runtime adapter 管理进程/容器。三者不互相代替，也不允许任意排列未经验证的组合。
4. Docker 是首个交付后端。RK3588 始终只执行 Docker 内验证；Mac 另比较 Colima/VZ、Apple OCI container、Docker Desktop 后端，按完整 DSM 负载选择。外层 VMM 与内层 QEMU accelerator 分别记录，不宣称某个名称天然最快。
5. 同架构 KVM 与跨架构 TCG 分档；新的严格性能档初始化失败即止。保持现有 ENV/回退兼容；不能无说明改变 `KVM=Y` 的已有行为。
6. 不可变产物与可写状态分离。旧 `/storage`、manifest schema 及磁盘几何有显式兼容层；首批不自动迁移旧盘。生命周期与管理/配置/卷就绪分别留证。
7. ARC x86 通过平台接口做隔离 PoC；ARM64 loader、Host QEMU、libvirt 与新 QEMU 版本是独立研究项。Host QEMU 评估仅面向 x86 Linux，不进入 RK3588 或 Mac 容器性能主矩阵。
8. 不调整生产 QEMU 四补丁的来源/晋升规则；供应链先固定来源和哈希，runtime 镜像拆分在行为稳定后依据维护收益决定。

## 后果

近期投入转向可重复性能证据、诊断与恢复；ARC 集成被后移，避免用新 loader 掩盖既有运行层问题。保留旧执行路径增加短期测试成本，但使回归、迁移与回退可审查。Apple container 是 OCI 候选，不假定兼容 Docker API/Compose，也不假定默认内核提供 KVM。

本 ADR 接受的是设计方向，不表示控制器、profile schema、Mac 新后端或 RK3588 支持已经实现。实现状态与证据仍由 CONTEXT 和目标设备验收决定。

## 替代方案

| 方案 | 取舍 |
| --- | --- |
| 仅改 KVM/日志参数 | 可作为起点，不能解决多平台状态与恢复边界 |
| 所有平台统一 ARC | ARM64 移植不确定性成为已有 direct boot 的依赖，拒绝作为统一前提 |
| 全面重写 / Go 或 Rust 重建 | 重新承担已解决的设备与安装风险，暂不采用 |
| 直接使用 Host QEMU/HVF | 不能满足 RK Docker-only 与 Mac 容器化主目标，保留 x86 后续评估 |

## 关联文档

- [实施计划](../implementation-plan.md)、[架构契约](../runtime-architecture.md)
- [三设备矩阵](../test-matrix.md)、[Mac 容器选型](../mac-container-evaluation.md)
- [产品范围](../PRODUCT.md)、[ADR 0004](0004-reinitialized-history-and-arc-roadmap.md)
