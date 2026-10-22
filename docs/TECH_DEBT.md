# 技术债

技术债是已经进入实现、当前有意保留且未来需要偿还的妥协。尚未实现或尚未验证的外部假设属于 [RISK_REGISTER.md](RISK_REGISTER.md)。

## 分级

- **P0**：数据安全、正确性或当前验收阻断。
- **P1**：明显影响可靠性、性能或维护性，应在近期迭代偿还。
- **P2**：长期结构优化。

## 活跃技术债

### TD-001：ARM 容器停止缺少访客侧关机代理

- **优先级 / 位置 / 来源 / 目标阶段：** P1；`src/platform/rtd1619b.sh` `platformGuestShutdown`；Phase 3 生命周期；F5 前后。
- **当前妥协与原因：** ARM 路径明确要求通过 DSM UI/API 关机；共享 `power.sh` 的 x86 qemu-host API 不适用；容器 `docker stop` 仍可能走超时回退。
- **影响与最坏结果：** 自动化验收依赖凭据齐全的 UI shutdown；凭据失效时无法完成干净 guest-poweroff。
- **偿还方案：** 在不降低安全边界的前提下，评估 QMP 协作关机或受控 API 客户端；任何方案需保留 `guest-shutdown` 收据语义。
- **验证方式：** 两次干净关机出现 `All filesystems unmounted.`、`guest-poweroff`、QEMU rc=0。

### TD-002：构建依赖仍包含可变外部输入

- **优先级 / 位置 / 来源 / 目标阶段：** P1；`Dockerfile`、`requirements.txt`、Debian package repositories；2026-10-22 W01；G0。
- **当前妥协与原因：** Docker frontend、qemux/debian images、qemu-host、patology 文件和 Python direct/transitive packages 已固定身份；APT 使用滚动 Trixie 仓库，QEMU configure-time subproject fetch 行为尚未由双架构原生构建确认。
- **影响与最坏结果：** 未快照的系统包或构建期下载可能让同一源码产生不同镜像或破坏跨架构构建，也可能污染性能 A/B。
- **偿还方案：** 按[依赖清单](dependency-locks.md)维护镜像 digest、文件 commit/hash、Python hashes；验证并固定 Debian snapshot 与任何 configure-time 下载后关闭此债。
- **验证方式：** 原生 amd64/arm64 重建、来源身份校验、包闭包与镜像回归；不以单次构建成功替代输入锁定。

### TD-003：启动编排依赖基础镜像脚本与共享 Shell 状态

- **优先级 / 位置 / 来源 / 目标阶段：** P1；`src/entry.sh`、`src/platform/*` 与基础镜像 `/run`；2026-10-22 规划审查；G3–G4。
- **当前妥协与原因：** source 链及共享变量保留既有 x86 行为，平台钩子已部分隔离，但启动/磁盘/网络职责尚未形成独立类型化契约。
- **影响与最坏结果：** 基础镜像行为漂移或新增平台造成跨平台回归；不能仅由本仓库源文件判断全部运行时行为。
- **偿还方案：** 先固定基础镜像，再用 legacy adapter、只读 LaunchPlan 和真实 argv 对照逐步分离；[架构设计](runtime-architecture.md)定义边界。
- **验证方式：** 两个既有 profile 的参数/失败行为等价、三设备真实验收、旧盘无自动迁移和可回退证据。

登记模板：

```text
TD-XXX：标题
优先级 / 位置 / 来源 / 目标阶段
当前妥协与原因
影响与最坏结果
偿还方案
验证方式
```

## 生命周期

1. 红绿灯审查中的跨任务 🟡 或明确延期的实现妥协进入本文件。
2. 修复必须有回归证据；完成后移入 `docs/archive/tech-debt/YYYY-MM.md`。
