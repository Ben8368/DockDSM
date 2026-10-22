# Surveillance Station 兼容性验收矩阵

状态严格使用以下含义：

- **PASS**：对应平台上的官方包/功能已有实际证据。
- **FAIL**：已执行该平台的实际测试且未通过。
- **BLOCKED**：缺少官方固件/包、有效许可、摄像头、网络或目标 DSM 条件，测试无法执行。
- **NOT TESTED**：该平台实际功能尚未测试。

合成测试只验证诊断代码，不把 Surveillance Station 运行标为 PASS。
2026-10-21 本地仓库没有运行中的 DSM 容器，也未向任务提供官方 Surveillance
Station SPK、有效许可证或网络摄像头；本轮没有执行真实包安装或 NVR 端到端测试。

## 平台验收

| 测试项目 | `virtualdsm` x86 | `rtd1619b` ARM64 | 证据 / 阻断项 |
| --- | --- | --- | --- |
| 平台与 guest CPU 架构识别 | NOT TESTED | NOT TESTED | 合成报告分类测试 PASS；尚无本轮 DSM 实际 collector 报告 |
| 官方 SPK 架构/DSM 版本接受 | BLOCKED | BLOCKED | 需要各平台 Package Center 与匹配官方 SPK 的实际检查 |
| 安装依赖检查 | BLOCKED | BLOCKED | 需要已启动 DSM、Storage Manager/volume、PostgreSQL、SVE 与 Package Center |
| 正式 SPK 安装 | BLOCKED | BLOCKED | 无目标 DSM 和官方 SS SPK；ARM64 只针对 DS124 DSM 7.2.2-72806 |
| 套件启动 | BLOCKED | BLOCKED | 依赖官方包安装成功；需检查 `synopkg status` 与 `pkgctl-*` 服务 |
| 摄像头手动连接 | BLOCKED | BLOCKED | 当前无授权测试摄像头与可核对 RTSP 网络路径 |
| 实时预览 | BLOCKED | BLOCKED | 需 DSM UI、有效摄像头账户和实际视频流 |
| 录像写入 | BLOCKED | BLOCKED | 需已配置录制共享文件夹、容量和授权 |
| 录像回放 | BLOCKED | BLOCKED | 需至少一段实际生成的录像 |
| 运动事件与时间轴标记 | BLOCKED | BLOCKED | 需实际运动源与官方套件事件记录 |
| 有效设备许可录像 | BLOCKED | BLOCKED | 需查看官方 License 页面并使用许可范围内摄像头 |
| DSM/容器重启后状态和录像持久化 | BLOCKED | BLOCKED | 需两个平台分别完成同一持久化盘的关机、重启、回放和新录像验证 |

## 已执行的代码级合成检查

| 检查 | 结果 | 证据 |
| --- | --- | --- |
| DSM kvmx64 到 package arch x86_64 映射 | PASS | `tests/surveillance/readiness.py` |
| DSM rtd1619b 到 package arch armv8 映射 | PASS | `tests/surveillance/readiness.py` |
| INFO 架构与 DSM 最低版本分类 | PASS | `tests/surveillance/readiness.py` |
| 依赖、volume、服务状态分类 | PASS | `tests/surveillance/readiness.py` |
| HTTPS DNS/TCP/TLS 错误类别 | PASS | `tests/surveillance/readiness.py` |
| 匿名 RTSP 端点响应与无凭据报告 | PASS | `tests/surveillance/readiness.py` |
| 授权状态与历史日志分类分离 | PASS | `tests/surveillance/readiness.py` |
| 官方 SPK 元数据、架构/DSM 匹配与默认 dry-run 安装保护 | PASS | `tests/surveillance/install.py` |

这些结果只覆盖输入夹具和报告逻辑，不能替代上一张表的 DSM/SPK/摄像头测试。

## 未完成验收的最短路径

对每个平台单独准备独立的持久化 DSM 测试目录、官方兼容 SPK、已授权摄像头和有效
Surveillance Device License。按 [安装与端到端流程](surveillance-station.md) 完成
Package Center 安装、Live View、连续录像、Timeline/Playback、DSM UI 干净关机、
相同 storage 目录重启和旧录像回放。随后附上不含密钥/密码的诊断 JSON 与私有测试
收据，再更新对应平台的状态。
