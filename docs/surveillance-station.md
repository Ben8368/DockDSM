# Surveillance Station 安装、诊断与端到端验收

本流程适用于 `DSM_PLATFORM=virtualdsm` 和实验性 `DSM_PLATFORM=rtd1619b`。
诊断命令只读取 DSM 状态。它不会安装 SPK、写入配置、访问摄像头密码、
修改授权、事件数据库或录像元数据。

Surveillance Station 的真实兼容性需要在每个平台分别用官方 SPK、有效许可、
网络摄像头和持久化 DSM 磁盘验证。合成测试只证明诊断分类逻辑，不证明套件
可运行。

## 安装前检查

优先通过 DSM Package Center 安装与当前 DSM 版本及平台兼容的官方套件。
若必须手动安装，应从 Synology 官方渠道取得匹配版本的 SPK，并继续使用
Package Center 的手动安装流程。Package Center 执行包格式、架构、版本和
签名检查；不要通过第三方修改包或身份信息绕过这些检查。

Synology 的套件格式用 SPK `INFO` 中的 `arch` 列出受支持的平台/架构，
`os_min_ver` / `os_max_ver` 表示 DSM 版本范围。官方映射中，`kvmx64`
属于 `x86_64`，`rtd1619b` 属于 `armv8`。检查的来源是 DSM 硬件平台标识，
而不是 Docker 主机的 CPU。已经安装的套件可由诊断工具读取其 INFO 字段；
未安装 SPK 的兼容性仍须由 Package Center 对官方包进行实际检查。

Surveillance Station 相关依赖随 DSM 与套件版本变化。本项目针对当前目标
版本检查 Storage Manager、`pgsql-adapter.service`、Surveillance Video
Extension 和 Surveillance Station。旧 DS124 root 可能没有 Storage Manager；
按 [ARM 包安装说明](package-installation.md#arm-initialization)使用精确官方
DS124 PAT 内的 Storage Manager，或通过 Package Center 手动安装。SVE 需要
在线 Package Center 流程；主套件手动 SPK 安装不代表依赖已满足。

安装前确认：

1. DSM 平台、`uname -m`、DSM 版本/build 与官方 SPK 的 `arch`、DSM 版本要求相符。
2. DSM UTC 时间正确，DNS 可解析，系统能够完成 Synology HTTPS TLS 握手。
3. Storage Manager 可用，`/volume1` 是真实挂载且以 `rw` 挂载；仅存在同名目录不算数据卷。
4. `/volume1` 有满足预期录制时长的空间。没有适用于所有摄像头的统一容量门槛。
5. 按当前 DSM/SPK 版本在 Package Center 满足官方依赖；检查 Storage Manager、
   PostgreSQL adapter、SVE 与 Surveillance Station 的安装和服务状态。诊断器报告
   可观测状态，但不把所有版本都假定为依赖 PostgreSQL 或 SVE。
6. 摄像头网络地址可从 DSM 主动访问。通过宿主 SSH 使用已配置的端口转发；不要在诊断命令里放入摄像头账户或完整 RTSP URL。

从有现成 SSH key 的主机运行只读诊断：

```sh
python3 scripts/surveillance-readiness.py \
  --guest admin@127.0.0.1 --port 5022 --sudo --network
```

`--sudo` 使用 `sudo -n`，需要已有非交互 sudo 权限。`--network` 会从 DSM
访问 Synology 套件目录与下载站点的 HTTPS 根 URL。HTTP 403/404 仍可证明
DNS/TCP/TLS 传输成功，但不表示套件下载、包授权或 NVR 服务已获许可。

对一个已知的摄像头 IP 做不带凭据的 RTSP TCP 探测：

```sh
python3 scripts/surveillance-readiness.py \
  --guest admin@127.0.0.1 --port 5022 --sudo \
  --camera-ip 192.168.1.50 --rtsp-port 554
```

探测发送匿名 RTSP `OPTIONS`，不导出 IP 地址；401/404 响应表示 RTSP 端点
已经响应，不表示账户认证成功或视频可以解码。连接失败会按 DNS、TCP、超时、
TLS/证书或其他 curl 类别报告。RTSP 探测不验证 RTP/UDP、H.264/H.265 解码、
ONVIF 发现或摄像头事件回调。

若 DSM 内已执行 collector 并私下保存 TSV，可离线生成 JSON：

```sh
python3 scripts/surveillance-readiness.py --from-report report.tsv
```

JSON 仅包含安全状态、有限的套件元数据、分类结果和最近日志类别，不包含原始
日志行、摄像头地址、明文密码、序列号、许可证密钥或请求正文。最近日志匹配
只提供线索；旧的授权或启动告警不证明当前故障的根因。Exit code `0` 表示
前置条件通过，`2` 表示发现阻断/失败，`3` 表示检查不完整或尚未检查网络。
`end_to_end` 和 `authorization` 会一直保持 `NOT TESTED`，直到人工完成下方验收。

## 官方 SPK 安装助手

从 Synology 官方渠道下载与当前 DSM 匹配的 Surveillance Station SPK。默认运行
只检查已启动 DSM 的平台、时钟、`/volume1` 挂载状态和本地 SPK 的 `INFO` 架构/版本；
它不会上传文件或修改 DSM：

```sh
python3 scripts/surveillance-install.py \
  --guest admin@127.0.0.1 --port 5022 \
  --spk ./SurveillanceStation.spk
```

如果官方安装包明确要求 Surveillance Video Extension，且你已有官方 SVE SPK，按依赖
顺序提供它；仅在 SVE 尚未安装时提供该 SPK。安装仍使用 DSM 自带的 `synopkg`，由
套件管理器执行其正常检查：

```sh
python3 scripts/surveillance-install.py \
  --guest admin@127.0.0.1 --port 5022 \
  --sve-spk ./SurveillanceVideoExtension.spk \
  --spk ./SurveillanceStation.spk --apply
```

传入 `--apply` 后，助手才会通过现有 SSH 连接上传这些 SPK，并以 `sudo -n` 调用
`synopkg install`；目标需要预先配置非交互 sudo。助手拒绝覆盖已安装套件，并会在结束时
尽力清理上传的临时文件；若 SSH 中断，需在 DSM 中手动移除对应的
`/tmp/vdsm-surveillance-*.spk` 文件。包校验或依赖不通过时，以 DSM Package Center 的
错误为准，再按需回到 Package Center 安装。助手不获取或修改许可证，不绕过包签名/平台
校验；授权只在 DSM 官方 License 页面核对。安装成功也不等于摄像头、录像、回放或持久化
已通过验收。

## 官方安装顺序与故障分流

在 DSM Package Center 中按当前提示安装 Storage Manager（目标平台需要时）、
Surveillance Video Extension（若官方包要求）和 Surveillance Station。记录官方包版本、DSM
版本/build、平台架构和完整错误文本；错误文本留在私有环境中，发布报告只保留
分类。

先看诊断 JSON，再按类别排查：

| 分类 | 证据与处理 |
| --- | --- |
| 系统环境 | DSM 时间、`/volume1` 挂载/只读状态、可用空间、PostgreSQL 和 Storage Manager |
| 架构/版本 | DSM `unique`、guest CPU 架构、官方平台架构映射、已安装 SPK 的 INFO 元数据；官方 SPK 由 Package Center 实测 |
| 依赖安装 | Package Center 与 `synopkg status` 状态；确认 SVE 安装完成后再检查主套件 |
| DNS/HTTPS | `--network` 的 curl 返回码分开标出 DNS、连接、超时、TLS 握手和证书错误 |
| 文件系统 | `/volume1` 是否真实 rw 挂载、默认 `surveillance` 共享文件夹是否存在、collector 账户只读权限检查 |
| 服务启动 | `synopkg status` 与 `pkgctl-*` service 状态；查看本机 `synopkg.log`、`synopkgmgr.log`、套件日志的匹配时间段 |
| 授权 | 仅在 Surveillance Station 的 License 页面查看官方许可状态；诊断工具不读许可、不更改身份 |
| 摄像头连接 | DSM 到指定 IP/RTSP TCP 端点；成功响应仍需在套件里添加摄像头并完成实际预览 |
| 视频/录像 | 服务启动不等于 stream decode、录像写入或回放成功；在 DSM UI 验收摄像头状态、录像文件和回放时间轴 |

Synology 开发者文档将平台架构写入 SPK 的 INFO 字段（arch、os_min_ver、
os_max_ver）；DSM 的 Package Center 用来呈现并校验可安装包。诊断器对已安装包
读取这些字段作一致性检查，正式 SPK 的接受结果仍以 DSM Package Center 为准。

Synology 官方帮助指出，Surveillance Station 的本地录像使用它管理的共享文件夹；
共享文件夹需位于有效卷并允许套件服务使用。诊断中的目录存在和 collector 写权限
不能替代 `SurveillanceStation` 服务用户权限或真实录制写入验证。

## 用户态 NAT 与摄像头网络

DS124 ARM64 使用 USB CDC ECM、QEMU user-mode NAT 和端口转发。该网络路径允许
DSM 主动连接摄像头的手动 IP，但 guest 没有宿主 LAN 的二层地址。广播/组播
发现（如自动 ONVIF 搜索）不可假设可用；这不是手动 IP 连接失败的证据。
默认不引入 TAP/bridge，也不需要 `privileged: true`。

RTSP 控制连接和 RTP 媒体流是不同检查。若摄像头和 Surveillance Station 提供
RTSP interleaved/TCP 选项，可在端到端验证时优先测试它。UDP RTP、摄像头主动
回调与 ONVIF 事件需要在目标网络逐项实测。诊断脚本只探测 DSM 发起的 RTSP TCP
请求，不会开放额外 QEMU 端口。

## x86 与 ARM64 端到端验收

为两个平台分别准备独立的测试持久化目录，并保持测试期间容器始终挂载同一目录。
不得用现有用户磁盘做重装、格式化或重置实验。ARM64 仅适用于本文档当前接受的
DS124 / `rtd1619b` / DSM 7.2.2-72806 版本。

每个平台分别记录 `docs/surveillance-compatibility.md` 中的状态和私有证据路径：

1. 保存 package readiness JSON；在 DSM Package Center 检查官方 Surveillance Station
   SPK 的平台架构、DSM 版本要求与依赖。
2. 使用 Package Center 安装 SVE（若版本要求）及 Surveillance Station；记录安装后
   `synopkg status`、套件服务、PostgreSQL、Storage Manager 和 volume 状态。
3. 在 Surveillance Station > Camera > Add 中手动填写摄像头 IP、厂商/型号及凭据。
   密码只输入 DSM UI，不放进 SSH 参数、RTSP URL、shell 历史或诊断报告。
4. 确认摄像头状态正常，实际打开 Live View 并持续预览至少 10 分钟。截图或私有
   测试记录应能关联平台、DSM/SPK 版本和摄像头编号（不要包含密码）。
5. 在套件 UI 创建/选择 recording storage，检查容量与录像轮转设置。启用连续录制，
   等待产生带时间戳的录像文件，再从 Timeline/Playback 搜索并播放同一时间段。
6. 单独检查运动事件：先验证摄像头或 DSM 的实际检测源，再确认事件列表和时间轴
   标记。不要将普通录制或诊断日志当成运动检测通过。
7. 正常从 DSM UI 关机，按相应平台的生命周期流程重启同一个容器和同一 storage 目录。
   再次确认套件状态、摄像头配置、旧录像回放和新录像写入。ARM64 使用已文档化的
   guest shutdown 路径。
8. 在套件 License 页面核对实际可用设备许可，并在许可范围内完成摄像头录像。
   不记录或导出许可密钥；许可证不足时将测试标为 `BLOCKED`。

只有完成官方包安装、至少一台网络摄像头实时预览、录像、回放和同一持久化磁盘
重启后的验证，才可以将某个平台的核心端到端行标为 `PASS`。其他事件与许可能力
独立记录，不从核心通过结果推断。

## Surveillance Station 内部机制研究边界

参考项目展示了几类内部格式，但它们不属于 Virtual DSM 公开或稳定 ABI：

- `@SSRECMETA/RecLog` 按 12 小时分段；参考桥接按 8 字节文件头、每秒 7 字节记录
  访问录制/运动标记。字节布局和时间窗口必须对具体 Surveillance Station 版本验证。
- 普通 motion timeline 还涉及 `detection_event_motion`、
  `detection_event_motion_count`、缩略图容器和 RecLog；只写其中一层可能产生 UI/API
  不一致。
- 参考 `ss_shm_tap` 通过 `/proc/sysvipc/shm` 枚举 SysV 共享内存，并以
  `shmat(..., SHM_RDONLY)` 读取基于特定版本结构解析出的 stream group/frame。
  key 前缀、帧头、环槽和相机映射没有在 Virtual DSM 中验证。
- 参考 `ss_mpp_motiond` 使用 Rockchip MPP HEVC decoder、DRM/dma-buf 与
  `/dev/mpp_service`，再将 luma 差分事件回写 RecLog。这依赖 Rockchip 设备，不能
  移植到 QEMU DS124。源码中没有通用 CPU decoder fallback；Realtek guest 上的软件
  解码与温度/性能需要单独测量。

本项目当前只生成诊断分类，不读取或写入这些内部数据。不得让 RecLog、SQLite、
缩略图或共享内存桥接成为官方套件安装、录像和回放的前置条件。

## 官方参考

- [Synology Package Developer Guide：平台架构标识](https://help.synology.com/developer-guide/appendix/platarchs.html)
- [Synology Package Developer Guide：INFO 必需字段](https://help.synology.com/developer-guide/synology_package/INFO_necessary_fields.html)
- [Synology：使用 Package Center 安装应用](https://kb.synology.com/en-me/DSM/tutorial/How_to_install_applications_with_Package_Center)
- [Synology Surveillance Station：录像存储](https://kb.synology.com/en-me/SurveillanceStation/help/SurveillanceStation/recording_storage)
- [Synology Surveillance：是否需要续订设备许可证](https://kb.synology.com/en-global/Surveillance/tutorial/Do_I_need_to_renew_my_surveillance_device_licenses)
