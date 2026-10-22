# MacBook Air M5 容器化性能选型

设计中。目标是在完整 DSM 负载、持久化和恢复门禁下选出合适的 Mac 容器后端；保持 KVM 路径兼容，不能先验把它设为最优。本文只定义 Mac 子矩阵，设备统一登记见 [test-matrix](test-matrix.md)。

## 分清两层虚拟化

```text
macOS / M5
  └─ 外层：VZ、Docker VMM 等提供 Linux 容器运行环境
       └─ Linux OCI workload：DockDSM 的定制 QEMU
            └─ 内层：KVM（需嵌套能力）或 TCG → DSM
```

QEMU 官方将 KVM 列为 Linux accelerator、HVF 列为 macOS accelerator。因此在 Linux 容器中简单把 QEMU 参数改成 `-accel hvf`，不能获得 macOS HVF；它需要不同的宿主运行实现。[QEMU accelerator 说明](https://www.qemu.org/docs/master/system/introduction.html)

Apple VZ 是管理虚拟机的框架；KVM 是内层 Linux 的虚拟化接口，这两者在上述路径中可以同时存在。Apple 提供嵌套虚拟化能力查询，具体环境仍需检测。[Apple 嵌套虚拟化](https://developer.apple.com/documentation/virtualization/vzgenericplatformconfiguration/isnestedvirtualizationsupported?language=objc)

## 候选与资格门槛

以下官方文档核对于 2026-10-22；main/在线文档不是发布锁定。执行时必须记录安装版本，对照其 release 文档和实际探针，不照搬版本不匹配的配置。

| 候选 | 采用理由 | 先验证什么 | 不预先假定什么 |
| --- | --- | --- | --- |
| M1 Colima + Apple VZ + Docker | 有本项目历史 K5 参考；保留 Docker/Compose 使用方式 | VZ nested 开关、ARM Linux kernel、容器 KVM、Linux 内部卷、PID1/关机 | 不能由旧证据推断本轮环境仍可用，也不锁定它最快 |
| M2 Apple `container` + OCI image | Apple 官方提供轻量 VM 运行 OCI 的路线，值得比较单 VM 工作负载 | release 支持、`--virtualization`、带 KVM 的 Linux kernel、同一 QEMU、持久卷/端口/信号 | 不等于 Docker daemon；OCI 镜像兼容不等于 Compose/API 兼容 |
| M3 Docker Desktop + Apple Virtualization framework | 比较常用 Docker 工作流与 VZ 的组合 | 当前 Desktop 版本是否提供所需嵌套能力及容器 `/dev/kvm` | “使用 Apple VZ”不自动意味着把嵌套能力开放给容器 |
| M4 Docker Desktop + Docker VMM | 容器优化后端值得筛选 | 确切实现/版本、容器内 KVM 初始化、卷/端口/退出语义 | 官方文件 I/O 或容器启动优化不代表 DSM 整体更快；不假定支持/不支持 nested |

Colima 文档提供 VZ 与 nested virtualization 配置；M1 先按固定版本核验。[Colima 配置](https://colima.run/docs/configuration/)

Apple container 通过轻量 VM 执行 OCI 镜像；官方 runtime 文档提供 `--virtualization`，并要求支持嵌套的芯片和具备虚拟化支持的 Linux 内核。故 M2 是可行性候选，不能跳过内核与 QEMU 检查。[Apple container](https://github.com/apple/container)、[runtime configuration](https://github.com/apple/container/blob/main/docs/runtime-configuration.md)

Docker 文档区分 Docker VMM 与 Apple Virtualization framework，并描述不同 Desktop 版本下的实现变化；该页没有给出本项目所需的 DSM/KVM 嵌套兼容保证。因此 M3/M4 先做能力门禁，再决定是否进入完整基准。[Docker VMM](https://docs.docker.com/desktop/features/vmm/)

## 资格筛选顺序

1. 记录已安装版本、可用资源与现有工作负载；在独立 profile/卷中验证，不为跑分重置用户 Docker Desktop 或 Colima 数据。
2. 用同一 linux/arm64 OCI payload 和相同 QEMU hash，验证运行时入口、环境变量、持久卷、网络端口、信号与退出码。
3. 容器内 KVM 探针通过后启动现有 `rtd1619b`，完成配置/卷/正常关机。不能只测一条普通 Linux 容器命令。
4. 若候选只支持 TCG，将其归入 portable 对照；从“硬件加速 DSM 优选”池中排除，并记录限制。不要因为外层启动很快就推荐给长期 DSM 运行。
5. 具备资格的候选进入性能与恢复测试。默认只让一个后端承担负载，避免两个外层 VM 争用资源使结论失真。

若 M2 需要自选 Linux kernel，它仅用于外层容器 VM，必须固定来源、配置和 hash；不得替换 DSM guest kernel，也不得借此修改 RK3588 宿主内核。若 release 不含所需能力，将候选记录为待后续版本，不在本轮开发内核适配。

## 性能实验

统一 guest/PAT、QEMU 与四补丁、2 vCPU / 2 GiB、相同新建测试盘内容与负载，按[性能协议](performance-baseline.md)采样；同时记录外层 VM 的实际限额。Apple 每容器 VM 与共享 Linux VM 的外层内存计量不同，既报告 QEMU RSS，也报告 macOS 整体增量，不能用 `docker stats` 直接等同 Apple VM 占用。

| 维度 | 比较方法 |
| --- | --- |
| 日常恢复 | 外层引擎已启动时，DSM QEMU start → configured + healthy volume |
| 从零启动 | 引擎停止到同一就绪点，拆分外层启动、容器启动、guest 启动；不混入镜像下载 |
| 存储 | 引擎管理的 Linux 原生卷为第一组；macOS bind mount/VirtioFS 另开一组；记录卷实际实现，不假定同名 volume 相同 |
| 网络 | Linux 环境内 peer、macOS peer、独立局域网 peer 分别测；固定 guest NIC/user backend，记录所有转发层 |
| 稳态 | 同样 DSM 文件服务负载、空闲 CPU/RAM、30min 及 24h 持续运行；记录电源、睡眠、温度/降频可见信息 |
| 运维 | 正常关机、引擎重启后的持久性、备份/恢复、端口/卷管理、日志/诊断可用性 |

主机睡眠/唤醒是额外兼容用例：先在可丢弃副本做，记录 guest 时间、连接恢复与卷健康；不能把 MacBook 合盖导致的停止当作 QEMU 性能问题。不可读的温度/能耗指标记 unavailable，不虚构。

## 如何选“最佳”

先通过数据正确性、可恢复性和加速身份门禁，再比较吞吐/时延、DSM 就绪时间、整体资源占用与可操作性。若一项领先而另一项退化，展示取舍；不以任意加权总分掩盖数据风险，也不因单次容器启动快就判定胜者。

同一负载下，若候选达到性能协议的可重复收益门槛且无重要回归，推荐为该负载的性能档；若差异落在噪声范围，优先保留兼容与维护成本低的后端。可保留“Docker 兼容推荐”和“OCI 性能推荐”两个明确选项，不能把 Apple container 包装成已兼容 Compose。

验收报告需列出每个候选的版本、能力门禁、失败原因、原始数据、存储/网络路径与回退方法。没有实测结果时仅发布候选清单，不宣布最快方案。

## 暂不纳入的架构

- macOS 原生 QEMU/HVF：可成为未来宿主后端研究，但 QEMU 已不在 Linux 容器内，不满足本轮容器化优选比较边界。
- 管理 UI 在容器内、QEMU 在 macOS 宿主：不能计作“DSM 运行时容器化”。
- 直接用 VZ/Apple container 的 Linux kernel 接口启动 DSM：需要另验 DS124 AHCI/LED/UART 等硬件契约；不能直接替代定制 QEMU。
- amd64 容器用户空间翻译：不证明 x86 DSM 内核具备硬件加速。跨架构保留 TCG 兼容，不承诺高性能。
