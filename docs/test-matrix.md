# 三设备验证矩阵

这是计划执行矩阵，不是已支持列表。当前能力以 [platforms](platforms.md) 和 [CONTEXT](../CONTEXT.md) 为准；证据级别沿用 [QUALITY](QUALITY.md)。宿主型号、容器架构、guest、外层虚拟机和实际 accelerator 必须同时记录。

## 设备角色与限制

| 设备 ID | 已知条件 | 计划环境与角色 | W00 待确认 |
| --- | --- | --- | --- |
| X | x86 设备 | x86-64 Linux + Docker 的同架构基准；ARC x86 后续 PoC；ARM TCG 对照 | 是否 x86-64、CPU/虚拟化能力、OS、RAM、磁盘/网卡；若只有 Windows/WSL，单独标注嵌套环境，不能计为裸机 Linux |
| M | MacBook Air M5 | ARM64 容器优先，比较 Mac 外层运行后端与 DSM 完整性能 | RAM、macOS、Colima/Docker/Apple container 版本、容器 VM 内核、磁盘落点、嵌套能力 |
| R | RK3588 | Linux ARM64 宿主上的 **Docker 容器内** KVM 验证，兼容真实 ARM 板卡环境 | 板型、系统/内核、容器可见 `/dev/kvm`、内存页、RAM、散热、存储接口、网卡/链路 |

RK3588 不安装或直接执行宿主 QEMU、fio、iperf、perf，不重编/替换内核，不修改宿主桥接/防火墙，不测试 Host QEMU。宿主侧仅管理 Docker 容器/卷/网络；探针与负载均通过 Docker 执行，不能以 privileged、宿主 PID/network 命名空间或挂载宿主根目录绕过该限制。内核不提供 KVM 时记录阻断，TCG 只能进入独立诊断行。

## 首批核心组合

| 用例 | 执行环境 / profile | 加速目标 | 责任与门禁 |
| --- | --- | --- | --- |
| X1 | x86-64 Linux → Docker amd64 → `virtualdsm` | KVM，严格无回退 | x86 主回归、配置/存储/关机/恢复、G1–G4 |
| X2 | 同 X1 → `virtualdsm` | 显式 TCG | 同架构 KVM/TCG A/B、无 KVM 环境错误路径 |
| X3 | x86-64 → Docker amd64 → `rtd1619b` | TCG multi | 跨架构正确性与 TCG 补丁回归；性能单独报告 |
| M1 | M5 → Colima Apple VZ → Linux arm64/Docker → `rtd1619b` | nested KVM | Mac 基准、历史环境复现、G1–G4；不预定为最快 |
| M2 | M5 → Apple container/OCI → `rtd1619b` | 嵌套能力及 guest 加速先实测 | Mac 性能候选；配置内核、卷/信号/网络适配单独验收 |
| M3 | M5 → Docker Desktop Apple VZ → `rtd1619b` | 可用性未知，先容器内 KVM probe | 资格通过后参加同负载性能对照 |
| M4 | M5 → Docker Desktop Docker VMM → `rtd1619b` | 可用性未知，先容器内 KVM probe | 按具体版本记录，不能凭 Docker VMM 名称宣称可用/最快 |
| M5 | M1 环境 → `rtd1619b` | 显式 TCG | 同架构加速对照，仅诊断，不与跨架构成绩混合 |
| M6 | M1 环境 → `virtualdsm` | x86 TCG | Mac 跨架构兼容样本；不把 Rosetta 当作 x86 guest KVM |
| R1 | RK3588 → Docker arm64 → `rtd1619b` | 容器内 KVM，严格无回退 | RK 主回归、G1–G4；关闭对应设备可移植性风险 |
| R2 | 同 R1 | 显式 TCG | KVM 不可用时诊断及同架构对照，不计 R1 通过 |

X1/M1/R1 是三个基准主组合；Mac 最终选定候选另完成同等门禁。M2–M4 先筛资格，失败不要求跑完全部 DSM 基准。首轮不枚举每台设备 × 每个 guest × 每个网络 × 每个版本的全组合；RK 上 x86 TCG 无首批目标，ARC 只安排后续 X4（x86 Docker + 新 ARC profile）。

## 容器内预检协议

1. 固定仓库 SHA、镜像 digest/平台、QEMU 可执行文件 hash、生产补丁清单、profile、PAT/build。所有 Linux 探针运行于对应容器环境，R 更不能用宿主二进制替代。
2. 记录 `uname -m`、内核、页大小、CPU 可见特性、容器用户、`/dev/kvm` 类型/所有者/权限与资源限额；宿主物理信息由设备登记补充，容器视图与外层视图区分。
3. 使用待验收镜像里的 QEMU 作无盘、暂停的 machine/CPU 初始化；ARM 采用现有 `virt,gic-version=3`、`-accel kvm -cpu host`，以探针回执及退出码确认，不能只看设备节点。
4. 检查可用容量、卷类型、剩余内存、端口冲突、时间同步、测试盘隔离、证据输出位置。已存在运行盘/容器不因预检失败被删除或修复。
5. 实际 DSM 启动后再保存 QEMU argv 和运行证据。KVM 档不提供 TCG 候补；误回退使该 KVM 样本失败。当前旧代码可能回退，故基线 harness 需要检测并拒收。

RK 以容器可见的 CPU 拓扑、允许 cpuset、页大小和 QEMU 初始化为准，不硬编码“大核是 CPU4–7”。默认不绑核、不改 governor；后续仅用 Docker cpuset 在实测可用集合做单变量实验。温度/频率不可读时记 unknown，不扩大宿主权限。

## 功能与稳定性验收

| Gate | 每个主组合要求 | 失败示例 |
| --- | --- | --- |
| H0 环境 | 预检完整，身份与真实 accelerator 明确 | 镜像平台不符、KVM fallback、磁盘来源不明 |
| H1 安装 | 独立空卷、固定官方输入、stock 配置向导完成；各 profile 自己的安装证据 | 仅 loader/HTTP 可达，拿另一型号 PAT 顶替 |
| H2 存储与管理 | configured、服务、实际健康卷、测试文件 SHA 一致；ARM 单盘 Basic/Btrfs | 用目录存在推断挂载，healthcheck 代替 DSM 配置 |
| H3 生命周期 | 同盘三次配置态冷启动，至少两次 DSM 正常关机；每次复核卷/文件/服务 | 容器停止冒充 guest-shutdown |
| H4 稳定性 | ≥30 分钟无 panic/oops/soft lockup 等；至少 30 组 HTTP 与 HTTPS 成功样本并保留时间 | 日志静默被解释为无错误、缩短 TCG 窗口制造假失败 |
| H5 恢复 | 停机副本备份/恢复到新位置，复核配置与 SHA；一次隔离副本的异常中断识别和恢复 | 在线复制盘、自动重装、丢失写入却报 clean |
| H6 候选发布 | 24h 受控混合负载，管理/存储/生命周期不退化 | 持续过热/内存不足、数据不一致、未解释的故障 |

H5 的故障注入仅针对明确新建的可丢弃副本；不得在 RK3588 宿主断电或中断宿主服务。ARM 的细节继续引用[裸机宿主验收协议](../research/arm64/bare-metal-acceptance-plan.md)和[运行盘契约](arm64-runtime-state.md)，执行方式仍受此处 Docker-only 限制。

历史 M5/Colima K5 记录见 [Phase 4A](../research/arm64/production-phase4a.md)，x86→ARM TCG F5 见 [Phase 3](../research/arm64/production-phase3.md#strict-f5-completed-acceptance-evidence--2026-10-15)。它们是已有范围内证据，不能视为本轮新 SHA、新 Mac 后端或 RK3588 的测试结果。

## 测量环境

现有 profile 首轮拟采用 2 vCPU / 2 GiB guest、32 GiB 全新稀疏盘，网络和设备保持原实现；资源不足时降低并明确新分组，不悄悄改变对照条件。外层 Mac VM 初始预算拟 4 vCPU / 8 GiB，须在 W00 确认物理资源足够。ARC 资源在 PoC 固定，不与不同 DSM 型号直接比较速度。

Linux Docker volume/原生 Linux 文件系统作为首个落点；Mac 共享目录和 Windows 文件系统路径单列实验，不把跨文件系统开销算作 guest 架构差异。RK 记录实际 NVMe/eMMC/USB/SD 后端，不假定设备拥有 NVMe。

## 证据记录模板

每轮产出一份脱敏摘要，完整串口、PAT、盘和凭据放在已忽略的 `test-output/` 或既有研究 work 目录。Git 中只放摘要和 manifest 哈希，不放秘密/专有二进制或长日志。

| 字段 | 必填内容 |
| --- | --- |
| 标识 | run_id、用例 ID、日期、操作者角色、repo SHA/dirty diff hash |
| 环境 | 物理设备、外层 OS/VMM、Linux kernel/page size、OCI 引擎版本、资源和磁盘/网络拓扑 |
| 身份 | 镜像 digest、QEMU hash、PAT/model/build、profile/config hash、盘来源/复制时停机证据 |
| 运行 | requested/actual accelerator、回退原因、实际 argv、各就绪时间点、采集器版本 |
| 结果 | H0–H6 分项 PASS/FAIL/BLOCKED/NOT_RUN，原始指标，样本数，异常和恢复结论 |
| 证据 | 原始文件索引与 SHA256、脱敏说明、未覆盖项、决定继续/退回的理由 |

“BLOCKED”只表示该设备用例被前置条件阻断；“NOT_RUN”表示未执行。不得把其它设备的 PASS 填入，也不将可选组合缺失解释为核心组合已完成。
