# Architecture Decision Records

ADR 记录影响长期维护的决定及理由。

## 状态

- **提议**：允许研究，不允许当作已锁定事实。
- **已接受**：实现必须遵守；改变时新增替代 ADR。
- **已替代**：保留历史，并链接替代它的新 ADR。
- **已拒绝**：保留曾评估方案及拒绝理由。

## 格式

文件名为 `NNNN-short-title.md`，正文包含：状态、日期、背景、决策、后果、替代方案、关联文档。

## 当前 ADR

| 编号 | 状态 | 决策 |
| --- | --- | --- |
| [0001](0001-governance-entry.md) | 已接受 | 单一 AI 入口与证据驱动治理闭环 |
| [0002](0002-qemu-production-patch-series.md) | 已接受 | 生产 QEMU 补丁单一目录与共享 apply helper |
| [0003](0003-dockdsm-identity.md) | 已替代 | DockDSM 独立命名、来源披露与兼容迁移 |
| [0004](0004-reinitialized-history-and-arc-roadmap.md) | 已接受 | 单根历史重建与 ARC/ARM64 目标路线 |
| [0005](0005-ci-validation-layers.md) | 已接受 | CI 分层、统一结果门禁与初始化全树检查 |
