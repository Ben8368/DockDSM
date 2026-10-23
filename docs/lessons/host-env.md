# Lesson：宿主环境检查

- 改代码或跑本地验证前，先确认宿主 OS（Windows / macOS / Linux）、CPU 架构（x86_64 / arm64）与实际 shell；不要假设是 Linux bash。
- Windows 上区分原生 PowerShell 与 WSL：路径、换行、Docker sock、`python`/`python3` 与中文编码行为不同；WSL 细节见 [windows.md](windows.md)。
- 架构影响镜像平台、QEMU 目标与是否可用原生 KVM；未探测前不得按错误架构选加速器或宣称同架构结果。
- 嵌套环境（Windows+WSL、Mac 容器 VM、板卡 Docker）要同时记录外层与容器内视图，不能把外层能力直接算作 guest 宿主能力。
