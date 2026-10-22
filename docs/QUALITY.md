# 质量与验收

## 证据分层

| 层级 | 含义 | 示例 |
| --- | --- | --- |
| L0 静态 | 语法、策略、文档预算、QEMU 补丁干净应用 | ShellCheck、governance-docs-check、`tests/qemu-patches.sh` |
| L1 合成 | 无官方 PAT 的单元/合成与镜像构建检查 | ARM installer/runtime、image validation、accelerator/lifecycle policy |
| L2 产品运行时 | 官方 PAT 的产品冷启动、配置和持久化 | Phase 3 F5、Phase 4A K5 |
| L3 硬件加速 | 指定宿主和加速器上的运行证据 | M5 + Apple VZ nested KVM；裸机 ARM64 单独列项 |

上层通过不能代替下层未跑项。CI 不证明 DSM 启动或 KVM 兼容。

## CI 自动门禁

统一检查名为 **CI result**。常规静态/双架构合成、补丁与 smoke 必须成功；原生镜像仅能在已证明 docs-only 的范围内跳过。初始化根提交、运行时/CI 变更、未知基线和发布前必须跑完整原生 amd64/arm64 镜像验证。

失败、取消、缺失输出与非预期 skipped 均阻断。具体路由、权限和发布规则只在 [CI 设计](ci.md)维护；测试策略与验收层级以本文件为准。

| Accepted baseline | Evidence |
| --- | --- |
| Phase 3 F5 + Watchdog L5 | [Strict F5 boot, watchdog scan, persistence and UI shutdown evidence](../research/arm64/production-phase3.md#strict-f5-completed-acceptance-evidence--2026-10-15) |
| Phase 4A K5 | [Official PAT fresh install, configured KVM boots, volume, marker and lifecycle evidence](../research/arm64/production-phase4a.md) |

统一 CI result 通过是自动通行条件；人工 `🚦 Audit Report` 仍是源码合并前的独立门禁。CodeQL、PR 标签与 stale 自动化不替代该审查。

## 完成定义（摘要）

- Phase 3 F5：配置态、PostgreSQL、volume1、persistence SHA、30/30 HTTP、HTTPS 200、两次干净 guest-shutdown、≥30 分钟无 soft lockup/oops/panic。
- 不得用 host-directed `docker stop` / SIGINT 充当干净关机。
