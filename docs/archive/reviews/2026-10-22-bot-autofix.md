# 2026-10-22：低风险自动修复配置与验证

## 远端事实

- CodeRabbit 页面显示 Ben8368 / Advanced / Admin，并通过 Coding Agent readiness 检查。
- 原生规则 `DockDSM — low-risk PR autofix` 已保存为 Active，范围仅 DockDSM；刷新并重新读取后，六项风险/状态条件、路径、排除标签和两轮上限仍保留。
- 创建时扫描两条开放 PR，匹配数为 0，未选取现有 PR。PR #8 有 ci 标签，PR #9 有 data-loss / agent:codex / risk:high，不被接管。
- 页面提示首个 Auto-fix 任务将启动 Coding Agent 试用。未开通新的付费 add-on，未修改预算、权限或分支保护。
- 已创建 bot:request 标签；Issue 派单 workflow 需进入默认分支后才响应事件。

## 验证边界

本地测试执行 workflow 内嵌的真实 JavaScript，以模拟 API 检查维护者、外部作者、机器人、标签、路径、表单与权限失败分支；不创建虚假 Issue 验收任务。远端尚无本次规则实际修复提交及 Actions → Jules 自动接单证据，见 RISK-008。

## 本地结果

- `python3 scripts/governance-docs-check.py`：通过。
- `python3 tests/governance-docs.py`：全部治理回归通过。
- `python3 tests/bot-dispatch.py`：10 项通过（执行真实派单 JavaScript，含多组路径/权限/标签子案例）。Windows Node 与 WSL 调用均通过。
- `python3 tests/ci-policy.py`：16 项通过。
- `python3 scripts/check-config.py`、`python3 scripts/check-tree.py`、`git diff --check`：通过。
- `actionlint .github/workflows/bot-dispatch.yml .github/workflows/test.yml`：通过；工具版本 1.7.12，从官方 release 获取并核验 SHA256。
- 真实 Issue/PR 自动修复、DSM 冷启动、硬件及镜像构建：本地未运行。本次只修改协作配置、workflow、文档及回归测试。
