# ARC 上游源码与 DockDSM overlay

`vendor/arc` 是指向 [AuxXxilium/arc](https://github.com/AuxXxilium/arc) 的 Git submodule，固定在上游 `main` 的快照 `99195dbdf4e0a21c5304ddb06e07dc57419679bc`（ARC 4.1.2）。ARC 的源码历史由上游维护；DockDSM 的修改单独放在 `patches/arc/`，避免把改动误写进 ARC 上游或 DockDSM 的 MIT 来源树。

在 Windows + WSL 的 bash 环境中初始化并应用研究补丁：

```bash
git submodule update --init --recursive vendor/arc
bash research/arc/apply-patches.sh
```

补丁只为 ARC 的 DSM 型号列表增加架构列。读取平台配置中的 `arch`，缺省显示 `x86_64`；标题说明当前 ARC 不支持 ARM64。应用后 `vendor/arc` 工作树会显示本地修改，重置该 submodule 可还原上游快照。

ARC 不会随 DockDSM 镜像构建或发布；本目录只提供固定源码入口和隔离 overlay。上游 README 声明禁止商业使用，仓库 `LICENSE` 标记 GPL-3.0，部分源文件另有 MIT 头部。各声明存在适用范围不一致，必须在捆绑源码、构建产物或发布 ARC profile 前审清；该集成不构成许可证意见或商业使用授权。DSM/PAT 使用限制也独立适用。当前仅验证补丁对固定源码的应用及静态检查，不代表 ARC DSM 启动已验收。
