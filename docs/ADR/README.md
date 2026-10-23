# Architecture Decision Records

ADR 记录影响长期维护的决定及理由。

## 状态

- **提议**：允许研究，不允许当作已锁定事实。
- **已接受**：实现必须遵守；改变时新增替代 ADR。
- **部分替代**：只有部分决定被取代；仍在生效的范围必须在 ADR 中明确，并链接接管的 ADR。
- **已替代**：保留历史，并链接替代它的新 ADR。
- **已拒绝**：保留曾评估方案及拒绝理由。

## 格式

文件名为 `NNNN-short-title.md`，正文包含：状态、日期、背景、决策、后果、替代方案、关联文档。状态为部分替代或已替代时，另需包含指向替代 ADR 的链接；部分替代还需写明“替代范围”。

## 当前 ADR

| 编号 | 状态 | 决策 |
| --- | --- | --- |
| [0001](0001-governance-entry.md) | 已接受 | 单一 AI 入口与证据驱动治理闭环 |
| [0002](0002-qemu-production-patch-series.md) | 已接受 | 生产 QEMU 补丁单一目录与共享 apply helper |
| [0003](0003-dockdsm-identity.md) | 部分替代 | 命名、来源披露与兼容迁移继续有效；保留旧 Git 历史的决定由 0004 替代 |
| [0004](0004-reinitialized-history-and-arc-roadmap.md) | 部分替代 | 历史重建、归属与数据隔离继续有效；统一 ARC 路线由 0006 替代 |
| [0005](0005-ci-validation-layers.md) | 已接受 | CI 分层、统一结果门禁与初始化全树检查 |
| [0006](0006-runtime-profiles-and-container-first.md) | 部分替代 | 分层、兼容与容器优先继续有效；接管顺序、引导器品牌/维护方式由 0009 替代 |
| [0007](0007-bot-collaboration.md) | 部分替代 | 自动小修复交由 0008；短期分支、人工合并及保护边界继续有效 |
| [0008](0008-scoped-bot-autofix.md) | 部分替代 | Jules 工作包范围交由 0010；低风险 PR 自动修复、单写入者与高风险边界继续有效 |
| [0009](0009-owned-bootloader-source.md) | 已接受 | 统一 DockDSM Bootloader、许可准入与自主源码接管阶段 |
| [0010](0010-scoped-jules-work-packages.md) | 已接受 | Jules 受控工具工作包、环境准备、文件占用与分阶段扩容 |
