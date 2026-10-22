# 机器人自动化操作约定

长期边界见 [ADR 0008](ADR/0008-scoped-bot-autofix.md)，启用与验收状态只见 [CONTEXT](../CONTEXT.md)。

## PR：CodeRabbit Triage Auto-fix

原生规则名为 `DockDSM — low-risk PR autofix`，位于 CodeRabbit 的 Triage → Rules。选择单一 DockDSM 仓库，不能选择 All（会包含其它及未来仓库）。

所有条件同时满足：非 draft 的 Open PR；Risk=Low；Blast radius=Low；Review effort=Low；CodeRabbit review status=Reviewed；Security risk=Minimal。路径候选为 `docs/**`、`tests/**`、`*.md`。缺失或过期证据不能授权执行。

排除标签：`risk:high`、`agent:codex`、`jules`、`arm64`、`qemu`、`security`、`data-loss`、`needs:hardware-test`、`hardware-testing`、`phase-acceptance`、`ci`、`dependencies`、`docker`、`guest`、`web`。

匹配后自动处理失败 CI、CodeRabbit findings 和人工反馈，每次 run 最多两轮，保留人工讨论待复核。新的活动可能触发新 run；轮数限制不等于总费用上限。第一次任务可能启用 Coding Agent 试用；需要额外付费或额度不足时由维护者处理，不自动调整计费。

路径只筛候选，标签和风险分级也不是硬权限。修复指令要求读 AGENTS / CONTEXT / LESSONS；保留测试断言和真实验收边界；不得改变安装/磁盘/恢复、ARM、生产 QEMU、安全/凭据、依赖固定版本或 CI/发布权限。超范围或两轮失败交给维护者。

### 单写入者与停用

- Codex 正在修改的 PR 保留 `agent:codex`；Jules 正在修改的 PR 标记 `jules`。Jules 产出 PR 时应自行加该标签，维护者复核归属。
- 移除归属标签只代表允许规则重新评估；先结束原写入任务，再交接。不要同时指令 Jules 与 CodeRabbit 改同一分支。
- 暂停未来匹配：Rules → Pause。停止已经开始的任务还需在任务页关闭 Autofix / 停止任务；只加排除标签不保证中断在途任务。维护者接管前确认已停止。
- `.coderabbit.yaml` 中 finishing_touches 开关控制按需功能，不能作为持续规则默认开启的替代。保留关闭的按需写入口，原生 Triage 规则单独管理。

## Issue：小任务表单 → Jules

使用 `🤖 Small task for Jules` 模板，填写类别、1–3 个具体文档/测试路径、改动与验证命令并勾选授权。模板先加 `bot:request`；[派单 workflow](../.github/workflows/bot-dispatch.yml) 读取最新 Issue 后检查双方写权限、保护标签和表单，再加 `jules`。Jules 从该标签启动并产出 PR。

普通公开 Issue、外部作者、机器人触发、关闭 Issue、已归属任务、权限查询失败与不合规路径均不自动派单。表单格式错误可修正后移除并重新加 `bot:request`；不会监听每次 edited 自动重派。移除标签不会撤销已启动的 Jules 任务，需在 Jules 中停止。

Actions 只访问 GitHub 元数据与标签，不 checkout 或执行 Issue 代码，不使用 PAT，也不会把表单验证命令作为 shell 执行。路径清单限制派单范围，机器人仍有 App 分支写权限，因此合并前必须核对实际 diff。

## 外部依据与验证

- [CodeRabbit Triage rules](https://docs.coderabbit.ai/triage/rules)：条件、原生 Auto-fix 与 run 上限。
- [CodeRabbit Autofix](https://docs.coderabbit.ai/code/deliver-changes)：PR 持续修复控件及停止方式。
- [CodeRabbit billing](https://docs.coderabbit.ai/code/access-and-billing)：试用、额度与付费门槛。
- [Jules Issue tasks](https://jules.google/docs/running-tasks/)：jules 标签触发。
- 本地回归：`python3 tests/bot-dispatch.py`，使用实际 workflow JavaScript 和模拟 API，禁止产生真实派单。
