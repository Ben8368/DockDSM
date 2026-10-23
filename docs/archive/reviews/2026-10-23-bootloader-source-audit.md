# 2026-10-23 Bootloader 源码接管审计证据

本记录仅保存本工作包证据；当前阶段与阻断见 [CONTEXT](../../../CONTEXT.md)，准入规则见[源码审计](../../bootloader-source-audit.md)。

## 基线与环境

- PR #19 HEAD `5005083821498fc123bb6b41ce25575a3b842035`：最新 CI result / CodeRabbit success，3 条 review threads 已回复并解决；2026-10-23 15:05:01（Asia/Shanghai）squash 合并为 `4a70602e04038f8ae8d63f011eb35377f6c6c6f0`。`gh pr view 19 --json state,mergedAt,mergeCommit,headRefOid,url` 返回 MERGED；完整 Phase 0 验证见[修复记录](2026-10-23-pr19-review-fixes.md)。
- 新分支 `codex/bootloader-source-audit` 从已 fetch 的 `origin/master` / `4a70602` 建立。原 `C:\DockDSM` 的分叉 master 和未跟踪 `vendor/arc` 保留；本工作使用隔离 worktree。
- Windows x64，Intel Core i7-10700；PowerShell 7.6.5，Python 3.14。WSL Ubuntu 24.04 x86_64，内核 `6.6.87.2-microsoft-standard-WSL2`，Git 2.43.0、Python 3.12.3，Docker client/server 29.9.0。
- Windows/WSL PATH 无 QEMU；WSL `/dev/kvm` 存在但未进行 KVM 初始化或 guest 启动，不能作为加速能力证据。

## Audit Report

总体评价：🟡 仅允许静态审计与准入工作包；不涉及生产启动、磁盘或凭据。迁移和组合分发被 RISK-006 的许可、二进制来源和源码闭包阻断。审计只读固定 Git objects，不执行继承代码，不把 shallow clone 当完整上游历史；L2/L3 另行取证。

## 已执行验证

| 环境 | 命令 | 结果 |
| --- | --- | --- |
| Windows | `python tests/bootloader-source-audit.py` | 10 项通过；涵盖路径含空格、只读、脏工作树、错误 HEAD/tree/大小/摘要/schema、浅历史、partial clone 禁止隐式获取 blob、继承 GIT 环境与 CLI 失败关闭 |
| Windows | `python scripts/audit-bootloader-source.py --source C:\DockDSM\vendor\arc` | commit/tree、76 entries、22,988,687 blob bytes 和 6 份证据 SHA256 全部符合锁文件；shallow=true / reachable=1，未认证完整上游历史 |

partial clone 用例先在未加约束的实现上失败（审计意外成功，证明触发了隐式 blob 下载）；加入 `GIT_NO_LAZY_FETCH=1` 和空 `GIT_ALLOW_PROTOCOL`、缺失 blob 失败检查后，回归通过。

WSL 使用一次性 `/var/tmp/dockdsm-phase1-validation` clone（基于 `4a70602`，覆盖本工作包候选文件并加入 index），不运行 Windows worktree 的 `.git` 路径。完整输出保存在本机 `/var/tmp/dockdsm-phase1-logs/`：

| 环境 | 命令 | 结果 |
| --- | --- | --- |
| WSL | `python3 tests/bootloader-source-audit.py` | 10 项通过 |
| WSL | `python3 scripts/governance-docs-check.py`；`python3 tests/governance-docs.py` | 治理检查和 11 项治理回归通过；Context 在 45 行/3,000 字符内 |
| WSL | `python3 tests/branding.py`；`python3 tests/ci-policy.py`；`python3 tests/arc-overlay.py`；`python3 tests/bot-dispatch.py` | 分别 5、20、8、12 项通过 |
| WSL | `python3 scripts/check-tree.py`；`python3 scripts/check-config.py`；`python3 scripts/git-hooks-test.py` | tree/config/hook 检查通过，包含新文件 |
| WSL | `bash research/arm64/tests/smoke.sh`；`bash tests/production-x86-command.sh` | 既有 ARM smoke 与 x86 fake-QEMU argv 回归通过；不是 DSM 启动 |
| WSL | `git diff --cached --check` | 通过 |

## 未覆盖与回退

未执行上游 `img-gen.sh` 或其他构建入口，未获取/修改 PAT、DSM 私有镜像、个人序列号或现有磁盘；未构建/发布组合 Bootloader 镜像。Linux x86 的 DSM L2/KVM L3、Mac ARM64 容器后端、RK3588 Docker-only 均未运行。没有新生产配置或数据迁移；撤回本工作包即可回到 PR #19 的临时研究入口，既有平台启动路径不变。
