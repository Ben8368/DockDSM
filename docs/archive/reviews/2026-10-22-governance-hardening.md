# 2026-10-22 治理加固与远端状态核验

## 范围

- 按用户确认的治理行动规划，修复阶段一致性检查失效、ADR 部分替代语义和仓库内保护状态留痕。
- 本轮只修改治理脚本、测试、工作流与文档；未修改产品源码、QEMU 补丁、镜像或发布流程。

## 远端核验

2026-10-22 使用维护者授权的 GitHub API 核验：

- 仓库创建于 `2026-10-22T04:05:05Z`，默认分支为 `master`。
- 远端分支为 `master`（protected）与 `renovate/github-actions-non-major`（unprotected）。
- `master` 使用 classic branch protection，Rulesets 为空：
  - 必需检查：`CI result`，`strict=true`
  - `enforce_admins=true`，要求线性历史，禁止强推与删除分支
  - 必须解决审查讨论
  - required approving reviews = 0，符合 `ADR 0007` 的单维护者设计
- 提交 `2da1c3d` 的 CI run `39742544175` 全部 job 成功，包括 amd64、arm64 原生镜像构建与 `CI result`。
- PR #4（Renovate）已由维护者于 `2026-10-22T08:12:14Z` 合并为 `cda22b7`；PR #2 关闭未合并，仍有 1 条未解决审查讨论；暂无 GitHub Release。

## 证据边界

- `2bebdb2` 是当天更早的初始化根提交，不是被归档的旧仓库历史；当前 `master` 已由 `2da1c3d` 取代。
- 该提交不在 `master` 可达历史中，也未出现在只读归档仓库；归档仓库已归档，无法写入。
- 已在主仓库建立带注解 tag `refs/tags/evidence/2bebdb2`，作为长期引用；tag 不改变 `master` 历史。

## 改动

- `scripts/governance-docs-check.py`：支持 `--root`；阶段声明缺失或与 README/SECURITY 不一致时失败；校验 ADR 索引与文件状态一致；支持“部分替代”并要求替代链接与替代范围。
- `tests/governance-docs.py`：新增合成回归，覆盖阶段声明缺失、阶段不一致、ADR 索引不一致、部分替代缺范围、已替代缺链接。
- `docs/ci.md`：记录分支保护核验快照；本地验证增加治理回归。
- `docs/QUALITY.md`：明确 `🚦 Audit Report` 是流程性强制，CI 不检查 PR 正文。
- `docs/ADR/README.md`、`ADR 0003`、`ADR 0004`：引入“部分替代”并明确仍生效范围。
- `docs/PROVENANCE.md`、`CONTEXT.md`、`docs/implementation-plan.md`：记录重建根提交的证据边界，并修剪 CONTEXT 中已由 PROVENANCE 承载的非阻断说明。
- `docs/AI_RULES.md`、`CONTRIBUTING.md`、`AGENTS.md`、`docs/ci.md`、PR 模板：定义非阻塞 PR 流程；推送/创建 PR 仍需用户明确授权，推送后不等待远端 CI，合并前确认 `CI result`。
- 主仓库：建立 `refs/tags/evidence/2bebdb2`，使被取代的根提交可长期引用。

## PR 审查反馈

CodeRabbit 在 PR #5 指出三点，均已修复并补充回归：

- ADR 索引只按编号前缀匹配，未校验精确文件名；现要求索引目标与文件同名，并拒绝重复编号。
- 替代 ADR 链接可为自链接或非 ADR 文档；现要求指向同目录、存在且编号不同的 ADR。
- 实施计划仍使用裸 SHA；现改用 `refs/tags/evidence/2bebdb2`。
- `.github/workflows/test.yml`、`CONTRIBUTING.md`：接入新增治理回归。
- `.githooks/commit-msg`：提示前缀改为 `DockDSM:`。

## 验证

| 命令 | 结果 |
| --- | --- |
| `python3 scripts/governance-docs-check.py` | 通过 |
| `python3 tests/governance-docs.py` | 11/11 通过 |
| `python3 scripts/git-hooks-test.py` | 通过 |
| `python3 tests/branding.py` | 5/5 通过 |
| `python3 tests/ci-policy.py` | 16/16 通过 |
| `python3 scripts/check-tree.py` | 通过 |
| `git diff --check` | 通过 |
| `git ls-remote origin refs/tags/evidence/2bebdb2` | 指向带注解 tag，解引用为 `2bebdb2` |

## 未覆盖

- 记录中的 `2da1c3d` CI run 只证明基线；PR #5 的 reviewed head 需在合并前单独核验 `CI result`，不以基线 run 代替。
- PR #4 已合并，但首次正式发布仍未执行；人工审查与发布闭环中的发布部分仍缺样本。
- 归档仓库只读，未写入；证据 tag 位于主仓库，不改变 `master` 历史。
- 未运行真机 DSM、KVM、ARM64 或镜像构建；本轮结论不涉及产品运行时能力。
