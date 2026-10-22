# 维护者职责

当前以本文件定义责任域；在 `CODEOWNERS` 建立前，合并前重点按下表执行。

## 责任域

| 领域 | 规划范围 | 合并前重点 |
| --- | --- | --- |
| Product / Platforms | 产品范围、`virtualdsm` / `rtd1619b` | 不夸大 KVM/商店/验收状态 |
| QEMU / TCG | `patches/qemu/8.2.2`、apply helper | 补丁可干净应用、研究/生产边界 |
| ARM runtime | 安装、runtime schema、生命周期 | 失败封闭、不丢用户盘 |
| CI / Release | workflows、GHCR 发布 | 统一 CI result、发布前完整检查、无秘密泄漏 |
| Governance / Quality | AGENTS、Context、Risk、测试 | 事实源、证据状态、署名 trailer |

## 机器人协作

机器人协作遵循 [ADR 0007](ADR/0007-bot-collaboration.md) 与 [ADR 0008](ADR/0008-scoped-bot-autofix.md)：Codex 负责核心开发与复核，Jules 承接授权小任务，CodeRabbit 审查并按规则修复低风险 PR，Renovate 维护依赖，Actions / CodeQL 验证，维护者最终合并与发布。一个分支同时只有一个写入者；自动化触发与交接见[操作约定](bot-automation.md)。

`jules` 是 Jules Issue 触发标签；`agent:codex` 仅标记归属，由维护者在 Codex 中派单。`risk:high` 和 `needs:hardware-test` 标记需要额外评审或设备证据的任务，不作为自动授权。高风险任务不交给 Jules；CI 修复也不得超出原任务范围。

## 必须升级评审

- 生产 QEMU 补丁系列增减或语义变化。
- ARM 运行时磁盘策略、重置/恢复语义变化。
- 对外发布镜像标签或默认平台行为变化。
- 安全、凭据处理或专有产物策略变化。

## 合并原则

- 🔴 不得合并；🟡 必须进入 Risk 或 Tech Debt。
- 客观验证和主观确认分开记录。
- 长期边界变化必须有 ADR。
