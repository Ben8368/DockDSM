# 性能基线与实验协议

计划协议；没有本轮设备跑分结果。执行组合由 [test-matrix](test-matrix.md) 定义，Mac 后端比较另见 [Mac 选型](mac-container-evaluation.md)。性能数字必须对应 repo SHA、完整环境和原始样本。

## 基线与采样纪律

1. 固定每组的官方 PAT/model/build、QEMU hash/补丁、镜像 digest、guest 资源、存储设备/文件系统、网络拓扑、测试工具版本。Virtual DSM 与 DS124 分组，不用不同 DSM 型号结果推出 CPU 架构优劣。
2. 先验证正确性再跑分。基线采用已有生产入口/实际 QEMU，不用研究 launcher 代替；首次安装、配置态重启、外层引擎启动三类时间分开。
3. 每次改变一个变量：外层容器后端、accelerator、日志、网络 backend、AIO/cache、存储落点均单独对照。固定输入后重复五次有效测量，交替 A/B 顺序并保留失败样本及失败率。
4. 配置态冷启动至少五次：冷启动指 QEMU 从停止重新启动，不代表宿主 page cache 冷。首轮为自然缓存；不擅自清理宿主 cache，RK 更不得写宿主 drop_caches。
5. 每次启动前需上一轮干净退出；如需重新复制，使用已停机、hash 可核对的一次性基线。不要给在线 VM 做文件级盘副本，也不要并发启动同一盘。
6. 记录空闲负载、电源、外层 VM 限额、散热可见信息；有 swap/热节流或其它重负载时另列结果。TCG 超时至少保留现有 900s 健康启动窗口，基准观察预算初定 30min；超时是删失/失败样本，不填作 1800s 成功时间。

## 时间与资源指标

| 指标 | 起止/定义 | 注意事项 |
| --- | --- | --- |
| prepare_s | 已校验输入进入准备 → 可启动产物完成 | 下载、提取、seed 构建细分；网络耗时不计入 CPU 启动优化 |
| boot_http_s | QEMU 进程实际启动 → 首次可达 HTTP | 仅表示管理可达，安装欢迎页也可能成功 |
| boot_configured_s | 同一起点 → 实际 configured 与必需服务证据 | 缺凭据/字段为 unknown，不能用 UI 截图标题替代 |
| boot_volume_s | 同一起点 → 目标卷挂载/健康与 marker hash 复核 | 已配置态与首次建卷分组 |
| shutdown_s | 明确的 DSM 关机请求 → guest-shutdown 与进程退出 | 记录请求通道、结果及 unclean 比例 |
| idle_cpu / memory | 完全就绪后静置 10min，按 1s 采样 | CPU 100%=1 个逻辑核；RSS、cgroup memory/peak 与外层 VM 分列 |
| logs_bytes / errors | 启动及稳态的日志量、panic/oops/lockup 等 | 降日志不能删掉错误判据；日志静默不证明稳定 |

时间使用单调时钟测间隔、UTC 标记事件，附采集间隔/精度。可达性按固定 5s 采样，HTTP/HTTPS 连续样本用于可靠性；不要将几十秒间隔的观察值包装成毫秒精度。

## 负载和瓶颈隔离

| 负载 | 初始协议 | 能说明什么 |
| --- | --- | --- |
| 存储顺序 I/O | 测试卷中独立 4GiB 文件，1MiB block，QD1/QD16，读/写分开；每轮 60s + 10s 预热 | 当前卷/后端吞吐；若测试集未超过各层缓存需标记缓存影响 |
| 存储随机 I/O | 4KiB，QD1/QD16，70/30 mixed 另开一组；固定工具/线程数 | IOPS、平均/p95/p99 completion latency、QEMU CPU |
| 写入可靠性 | 单独 fsync/fdatasync 用例、文件 hash、正常停止后重启；故障只在一次性副本 | 缓存/AIO 改变不能牺牲恢复和写入语义 |
| 网络 | 可用且经校验的 guest iperf3 与固定 peer；1/4 流、单向/反向各 60s，五轮 | 网络链路及 QEMU CPU 开销；先固定 USB NIC，仅变 backend |
| DSM 实际文件服务 | 固定共享目录、文件集和客户端，上传/下载与目录遍历分开 | SMB/DSM 应用+磁盘+网络整体体验，不能当纯网络速率 |
| 混合稳态 | 文件服务 + 管理探针 ≥30min；发布候选 24h | 延迟、CPU/RAM、错误、卷健康和散热下持续性能 |

fio/iperf3 必须确认适配 guest 架构且可正常运行，再固定二进制来源/hash；安装工具不能改 DSM 内核、watchdog 或覆盖系统组件。若 guest 工具不可得，记录为未运行，可用真实文件服务测试补充，但不能将它标作 fio/纯网络等价证据。工具置于专用测试目录，可在实验后清理。

宿主路径基准使用独立测试容器/卷，guest 内测试用其测试共享目录，禁止对宿主物理盘、VM system image 或活动块设备直接运行写入压测。4GiB 为起始测试集，空间不足时先调整实验预算，保留空闲空间，不硬跑至满盘。direct I/O 若被文件系统/引擎拒绝，记不支持，不能静默退成 buffered 再比较。

网络对端可由另一台现有设备的独立容器承担，但对端不能同时承担被测 VM；先测对端/链路上限，固定有线/Wi-Fi、链路速率、加密与 MTU。RK 采集及所有 peer 工具仍通过 Docker。Mac 的 Linux 内、macOS 与 LAN 对端是三组拓扑，不能混排。

## 优化实验清单

| 顺序 | 实验 | 保持不变 | 纳入条件 |
| --- | --- | --- | --- |
| E01 | 同架构 KVM / TCG；Mac 外层候选分组 | guest/PAT/QEMU、内层网络/磁盘 | 真实加速证据、重启/关机通过 |
| E02 | 普通/详细日志 | earlycon、console、root、AHCI/LED/UART 与 watchdog 策略 | 错误和退出仍可观测；先逐项减少调试参数 |
| E03 | USB CDC + user / TAP | guest NIC/驱动、资源、存储 | TAP 拓扑/权限/清理经审查；RK 仅容器内，不改宿主桥 |
| E04 | raw/AHCI 的 cache 与 AIO | guest 设备与分区几何 | 一次只改一个选项，验证支持/flush；拒绝 cache=unsafe |
| E05 | 1/2/4 vCPU 与容器 cpuset | 其它参数 | 避免过量分配；RK 不猜大核编号；分别测 KVM/TCG |
| E06 | TCG 热点、TB 失效成本 | 生产四补丁 | 先 profile 采样；诊断构建与性能构建分离，不删除 0004 |
| E07 | 新 QEMU 候选 | 相同硬件契约与固定测试 | 独立 ADR/补丁移植；DC ZVA、F5/K5 与目标设备重新验收 |

网络 backend 与 NIC 模型是不同维度，见 [QEMU 网络文档](https://www.qemu.org/docs/master/system/devices/net.html)。cache/AIO 的实际选项需由固定 8.2.2 构建能力与文件系统确认，不能用最新手册保证旧二进制支持；参数语义参考 [QEMU invocation](https://www.qemu.org/docs/master/system/invocation.html)。现有 ARM 已启用多线程 TCG，继续增加 vCPU 需测量同步与设备开销，见 [MTTCG](https://www.qemu.org/docs/master/devel/multi-thread-tcg.html)。

## 判定与报告

- 正确性为硬门禁：数据 hash、卷健康、关机收据、错误和恢复任一失败，则不接受优化；性能优势不能抵销。
- 五次结果报告原始值、median、min/max、失败率；如此小的启动样本不报告有统计意义的 p95。I/O p95/p99 基于每轮足够的完成请求，样本数不足 1000 时不作尾延迟判断。
- 初始工程筛选阈值：目标指标 median 改善 ≥10%，且其它关键时延/吞吐退化不超过 5%；这是待基线校准的决策门槛，不是收益承诺。噪声范围与差异重叠时追加一批五轮；仍不清楚则结论为无明确收益。
- 每项先登记要改善的指标；不能事后只挑最好看的一项。Mac 候选如有明显吞吐/资源/运维取舍，分别报告，不能声称全局最优。
- 输出 environment manifest、原始 CSV/JSONL、事件索引、失败记录、图表与脱敏结论；原始大文件留在忽略目录，Git 仅提交小型汇总与校验索引。

仅完成构建、静态检查或此协议编写，均不能声称 G1 性能基线完成。
