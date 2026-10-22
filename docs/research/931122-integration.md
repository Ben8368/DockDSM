# 931122 项目技术对照与基线

检查时间：2026-10-21。外部仓库提交 SHA 来自其当前默认分支 HEAD；本次仅在系统临时
目录浅克隆读取文件，没有把任何外部代码带入 Virtual DSM。

## Virtual DSM 开发前基线

- 分支：`codex/surveillance-arm64-integration`，开发前 HEAD：`484f39923b8cb53b71f129fe7c9844b0a388187f`。
- 开发前工作树与 index 干净；本轮沿用该隔离分支，没有切换或覆盖用户工作。
- 默认 `virtualdsm` 仍走现有 x86 启动参数；`rtd1619b` 是 DS124 / DSM 7.2.2-72806 实验路径。
- ARM64 生产 QEMU 当前只有一个 sysbus AHCI port、一个 SATA 系统盘；USB CDC ECM 经 user-mode NAT 转发管理端口。
- 通用包诊断已经只读检查平台、clock、volume、PostgreSQL、网络传输和近期日志分类，但没有专项 Surveillance Station JSON 或手动摄像头探测。
- Surveillance Station、官方套件安装、摄像头、许可、录像、回放和重启持久化在开发前均未验证。

开发前自动化基线在 Ubuntu 24.04 WSL、amd64 上执行。测试依赖只安装在临时 venv；
未修改依赖清单：

| 验证 | 开发前结果 |
| --- | --- |
| `python3 scripts/governance-docs-check.py` | PASS |
| `python3 scripts/git-hooks-test.py` | PASS |
| `bash tests/platform.sh` | PASS |
| `bash tests/pat-acquisition.sh` | PASS |
| `python3 tests/package-readiness.py` | PASS |
| `python3 tests/guest-integrations.py` | PASS |
| `bash tests/guest-clock.sh` | PASS |
| `python3 tests/image-validation.py` | PASS |
| `python3 tests/arm-installer.py`（WSL root，合成镜像） | PASS |
| `python3 tests/arm-runtime.py` | PASS |
| `python3 tests/x86-installer-regression.py` | PASS |
| `python3 tests/proprietary-artifacts.py` | PASS |
| `python3 tests/production-x86-command.py` | PASS |
| tracked shell `bash -n` + ShellCheck，`scripts/check-config.py`，`git show --check HEAD` | PASS |
| `bash tests/qemu-patches.sh` | PASS；生产 QEMU v8.2.2 四补丁干净应用 |
| `bash research/arm64/tests/smoke.sh` | PASS |

真实 DSM、x86/ARM64 镜像运行和摄像头验收不是这些合成测试的覆盖范围。开发前
Docker amd64 baseline build 已完成：`git archive HEAD | docker build --platform linux/amd64
--progress=plain -t virtual-dsm:baseline-484f399 -` 成功，manifest-list digest 为
`sha256:2dd67213b6d30b4f69a72a3484202939ec752254a642d8c2c2e333930c95e419`。这是初始
源码构建证据，不是 DSM 访客或 NVR 验收。WSL 里不能非交互
sudo 的首次尝试未用于结论；之后以 WSL root 运行同一项合成安装器测试通过。Windows
宿主 Python 的尝试受到 GBK 默认编码、Windows 无 `os.chown`、NTFS symlink 权限和
缺少 `dissect` 依赖影响；这些测试随后在 Linux/WSL 正确运行环境下重跑。

## 外部项目版本与许可

| 仓库 | 检查版本 | 许可/边界 | 处理 |
| --- | --- | --- | --- |
| [931122/rk_syno_pack](https://github.com/931122/rk_syno_pack/tree/309682cd79e46620d96f15cbaa861941d73cca2c) | `main`，`309682cd79e46620d96f15cbaa861941d73cca2c` | 仓库根无 LICENSE；子模块包含独立的 SynoXtract 与 rk_syno_kernel。没有足够依据复制 packkit 源码。 | 研究构建流程、设备契约和测试风险；本项目实现独立诊断。 |
| [931122/rk_syno_kernel](https://github.com/931122/rk_syno_kernel/tree/c6d327b94e694c8d380618d0831c30d92f20a5f4) | HEAD 分支 `rk-dsm-port-7.3-86009`，`c6d327b94e694c8d380618d0831c30d92f20a5f4` | 根 `COPYING` 为 GPL-2.0 WITH Linux-syscall-note；`drivers/hwmon/syno_hddmon.c` 声明 `MODULE_LICENSE("Proprietary")`，厂商部分另有边界。 | 未复制内核或驱动代码；Linux GPL 不自动授权 Synology proprietary 驱动。 |
| [931122/Surveillance-Station](https://github.com/931122/Surveillance-Station/tree/bd332fbbfa90c3eaeb8208e29ba44535e745dec7) | `main`，`bd332fbbfa90c3eaeb8208e29ba44535e745dec7` | 根 LICENSE 是 GPL-3.0，但树中有按版本/架构提供的 Synology 二进制 payload；仓库许可证不证明第三方厂商二进制可再分发。 | 不提取或集成二进制修改；仅记录其为第三方补丁项目。 |
| [ohyeah521/Surveillance-Station](https://github.com/ohyeah521/Surveillance-Station/tree/4ad22d96c0b53c579cb0ad80cb30906aabec54ae) | `main`，`4ad22d96c0b53c579cb0ad80cb30906aabec54ae` | README 明示 license crack/恢复流程，发布树包含 `activated.sh`、第三方二进制 payload；GPL 文本不能许可规避 Synology 商业授权。 | 明确排除授权绕过脚本、二进制补丁和包源。 |

## 逐项技术对照

| 参考实现 / 源码位置 | 观察到的机制 | Virtual DSM 处理 |
| --- | --- | --- |
| `rk_syno_pack/tools/ss_event_bridge/README.md`、`ss_event_bridge.py` | SQLite `recording.db` / `detection_event.db` 写入 motion、count、thumbnail token；另补 RecLog 元数据。文档要求先手工备份并按版本检查表结构。 | 不接入事件写入。需要真实版本 schema、并发/锁、备份/恢复和一次性测试库验收；官方套件可用性不依赖桥接。 |
| `rk_syno_pack/tools/ss_motion_bridge/ss_reclog.c` | RecLog 用 8-byte header 与每秒 7-byte record；12 小时窗口；对目标字节做读改写，另有可选创建/扩展及备份。 | 仅作为研究格式；不写 RecLog。文件布局是内部实现，不能视为稳定公开 ABI。 |
| `rk_syno_pack/tools/ss_shm_tap/ss_shm_tap.c` | 枚举 SysV shm，`shmat(..., SHM_RDONLY)`；以固定头字段和相邻 key 推测 stream group，再提取 H.264/H.265 Annex-B 帧。 | 可复用“先只读观察”的工程原则，不复制解析器；没有从本项目 DSM/SS build 验证过 ABI、camera/group 映射或并发帧一致性。 |
| `rk_syno_pack/tools/ss_mpp_motiond/ss_mpp_motiond.c` | RK MPP HEVC decoder、DRM DMA buffer 与简单 luma 差分检测，延迟后回写 RecLog；依赖 `/dev/mpp_service` 和 RK 图形/内存接口。 | 不集成 Rockchip 专属设备代码。QEMU DS124 是 Realtek virt machine，没有已验证 MPP/NPU/DRM DMA 设备；CPU H.264/H.265 fallback 需独立解码性能测试。 |
| `rk_syno_pack/scripts/common.sh`、`patches/0000-rk-initrd-fixes.sh` | 修改 Rockchip PAT initrd 的 `model.dtb`：生成 `internal_slot@N`、`ahci/ata_port`、`rtk_ahci/ata_port`，同时改 `synoinfo.conf` 的 `maxdisks`；root handoff 同步 DTB 和盘位数；替换 Rockchip `syno_hddmon.ko`。 | 这是 RK 板卡驱动/DTB 路径，不能移植到 Realtek DS124。可以对照 DSM 盘位契约，但不修改官方 PAT、initrd、DTB 或驱动。 |
| `patches/qemu/8.2.2/0001-arm-virt-dsm-platform.patch` | 当前 QEMU sysbus AHCI 显式设置 `num-ports=1`，只把 `hd[0]` 接到 port 0。 | ARM 多盘需要 QEMU 端口扩展和与 DSM `internal_slot`/`maxdisks` 的完整匹配验收；目前不实现，避免虚假 Storage Manager 盘位或触发已有池重建。 |
| `rk_syno_kernel/drivers/hwmon/syno_hddmon.c` 与 Rockchip DSM DTB | `syno_hddmon` 依赖 Synology SATA/盘位/热插拔契约，且源码标记 proprietary。 | 仅研究依赖接口，不构建、替换或发布它。Virtual DSM 使用现有生产 QEMU/stock DS124 路径。 |

## Surveillance Station 专项实现

本轮实现 `src/guest/surveillance-diagnostics.sh` 与
`scripts/surveillance-readiness.py`：只读收集平台/guest 架构、DSM build、Synology
`synopkg status`、已安装 INFO 架构/版本字段、package service、volume 与默认录制目录、
PostgreSQL、最近日志类别和可选网络探测。摄像头探测只接受数字 IP 与端口，匿名发送
RTSP OPTIONS；报告不保留摄像头 IP、日志行、密码、序列号或许可材料。它不安装包、
打开数据库、读取共享内存或写事件/RecLog。

`tests/surveillance/readiness.py` 接入双架构 synthetic CI，覆盖 x86/x64 与 DS124/armv8
映射、依赖/卷/服务、HTTP/TLS、RTSP、授权隔离和报告输入边界。真实 DSM 和正式 SPK
仍按 [Surveillance Station 验收矩阵](../surveillance-compatibility.md) 单独记录。

后续补充了 `scripts/surveillance-install.py`：用户提供官方 SPK 后，默认只核对 DSM
平台/时钟/卷和包 INFO；只有显式 `--apply` 才经现有 SSH、非交互 sudo 和 DSM `synopkg`
安装，并拒绝覆盖已安装包。合成回归覆盖 SPK 元数据与目标架构/DSM 版本门禁。这仍未
验证任何真实 SPK 安装、授权或 NVR 功能；也没有集成第三方授权绕过代码或二进制。
