# 机器人自动化操作约定

长期边界见 [ADR 0008](ADR/0008-scoped-bot-autofix.md) 与 [ADR 0010](ADR/0010-scoped-jules-work-packages.md)，启用与验收状态只见 [CONTEXT](../CONTEXT.md)。

## PR 合并前：等待 CodeRabbit

维护者或 Agent 合入前须确认 CodeRabbit commit status 为 success，并与 `CI result` 一并核验；`CI result` 先绿时仍应等待审查结束。不把 CodeRabbit 设为 GitHub required check。完整表述见 [AI_RULES](AI_RULES.md#pr-推送与远端验证)。

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

使用 `🤖 Small task for Jules` 模板，填写类别、精确路径、改动、验收条件与验证命令，勾选授权和依赖/额度/文件占用确认。模板先加 `bot:request`；[派单 workflow](../.github/workflows/bot-dispatch.yml) 读取最新 Issue 后检查双方写权限、保护标签、表单与队列占用，再加 `jules`。Jules 从该标签启动并产出 PR。

### 维护者触发与接单回执

- 用户要求后续尽量使用维护者身份触发。保留上述表单及 workflow 授权校验；最终触发优先使用已核实写权限的维护者 GitHub 会话，不为此向 Actions 注入 PAT 或扩大权限。
- 当前 workflow 自动加 `jules` 只证明标签请求成功，不能报告“Jules 已接单”。接单须有 `google-labs-jules[bot]` 的回执评论及 Jules 任务链接；无回执时标记“待确认”。本地门禁、标签、Actions success 和 App 已安装均不能代替接单回执。
- 若自动标签没有回执，先核查 Jules 中是否已有对应任务；确认没有任务后，可用维护者身份移除并重加一次 `jules`，核查标签事件的实际 actor 和新回执。已有任务时不重触发，不循环重试；无法确认任务状态时不把重复标签当成修复。
- 已有维护者会话无法使用或无法核实身份时，报告触发边界；不借机器人身份冒充维护者，不自动创建或更换凭据。接单回执只证明任务已建立，交付仍需独立审阅 diff 和验证。

普通公开 Issue、外部作者、机器人触发、关闭 Issue、已归属任务、权限查询失败与不合规路径均不自动派单。表单格式错误可修正后移除并重新加 `bot:request`；不会监听每次 edited 自动重派。移除标签不会撤销已启动的 Jules 任务，需在 Jules 中停止。

Actions 只访问 GitHub 元数据与标签，不 checkout 或执行 Issue 代码，不使用 PAT，也不会把表单验证命令作为 shell 执行。路径清单限制派单范围，机器人仍有 App 分支写权限，因此合并前必须核对实际 diff。

### Jules 额度

当前账户的已核实额度及核实日期只记于 [CONTEXT](../CONTEXT.md#当前决策)。派单前以账户界面及 [Jules Limits and Plans](https://jules.google/docs/usage-limits/) 复核可用额度和并发；不沿用旧版固定数值。官方日任务额度按滚动 24 小时统计，计量单位是 task/session，不是聊天消息条数。界面出现额度限制或付费提示时报告维护者处理，不自动升级、购买或变更计费。

### 工作包范围与验收

机器允许路径以 workflow 为唯一事实源；表单列的是当前任务的精确文件子集，不是授权整个目录。

| 类别 | 文件预算 | 任务边界 |
| --- | --- | --- |
| Documentation | 1–3 | 普通使用说明、错误解释和示例；不改治理权限、平台契约、阶段结论 |
| Tests | 1–3，可含配套普通文档 | 离线边界/异常回归；不改敏感准入、安全、ARM/QEMU、安装恢复和 CI 门禁测试 |
| Tooling | 最多 6，且必须含实现文件 | 仅 workflow 逐项准入的离线工具及其测试/说明；不开放任意 scripts 或产品源码 |

首个准入工作包是离线测试结果汇总：`scripts/dev/summarize-test-results.py`、`tests/dev/summarize-test-results.py`、`docs/dev/test-results.md`。这些是允许新建的路径，不表示工具已经实现；当前仅三条路径可用，六文件预算不会自动放开其它文件。输入使用合成结果，保留 failed/skipped/not-run 的区别，未知输入明确报错；不执行报告中的命令，不修改 CI result，不读取凭据、原始设备日志或真实磁盘。其它模块须先审查风险、冻结接口和前置条件，再同步允许路径与拒绝回归。

每单写清：当前行为与一个交付目标、精确文件、依赖已合入的基线、允许/禁止副作用、正反例、验证命令和未覆盖层级。新工具用例必须能识别错误输出与退出码；发现现有缺陷时保留失败复现，不删断言、不静默扩路径。新测试若需要修改 CI 才能长期运行，由主执行者负责接线并一起审查。

不要重复派发已有任务；同一工作包优先在原任务反馈返工，一个工作包一个直接面向 master 的 PR。依赖工作包在前项合入后从最新 master 开始，不创建 stacked PR。最终检查实际 diff（包括新增、删除、改名），Jules PR 维持 `jules` 归属，满足 AI_RULES 的 CI/CodeRabbit 门禁后由维护者合并。

### 文件占用与在途容量

- workflow 使用仓库级 concurrency 串行完成查询与加标签，不是按 Issue 各自加锁。当前采用默认单 pending；后来的事件可能替换尚未执行的 run。官方 `queue: max` 尚不被本仓库固定 Actionlint 识别，保留现有门禁并登记 [TD-005](TECH_DEBT.md#td-005jules-串行派单尚无持久请求队列)。逐单核查 run 与回执；取消的请求须维护者重新触发，不能报告接单。
- 分页读取打开的 `jules` Issue，保守占用其 Allowed paths；四个在途 Issue 已满时不新增。没有可解析路径的历史任务阻止新派单，先核实和整理原任务；不靠移除标签绕过。
- 分页检查所有打开 PR 的实际路径，包括改名前路径；重叠或文件列表触及 API 截断上限则拒绝。五个打开的 Jules PR 时停止补单，draft 也计入。此计数比“未初审 PR”更保守。
- API 查询失败不写标签。派单前再次确认 Issue 内容、状态和标签未变；没有执行 Issue 中的命令。权限为 `issues:write` 与 `pull-requests:read`，无 checkout/PAT/内容写权限。
- GitHub 检查不能观察本地未推送编辑、其他仓库任务或已被关闭却仍运行的 Jules session，也不能消除人工同时操作造成的全部竞争。维护者必须检查本地文件占用、账户任务及额度；活动 Issue 的范围保持冻结，变更先停工并重新交接。
- Issue 应在交付合入或确认取消/停止后关闭；移除标签和关闭 Issue 都不会自动停止 Jules。拒绝/容量不足的请求没有后台自动重试，原因在 Actions 日志；条件解除后移除并重加 `bot:request`。

### 环境、试运行与回退

先按 [Jules 环境](jules-environment.md)运行 Initial Setup 和快照验证；每单仍检查实际版本与目标命令。供应商支持功能开发，不代表目标 DSM、ARM 或 KVM 可在其 VM 完成验收。

| 阶段 | 每滚动 24 小时的新任务建议 | 并行建议 | 升档条件 |
| --- | --- | --- | --- |
| 试运行 | 8–12，有适合任务才派 | 3–4 | 至少 10 个完成复核的交付样本 |
| 扩容候选 | 20–30 | 6–8 | 首次验收通过率 ≥80%，无越界，净节省时间为正且无审查积压 |

这是项目建议，不是供应商额度或必须填满的配额；工作流先固定四个在途 Issue / 五个打开 Jules PR 的保守门槛，升档须主执行者修改门槛、测试和本约定后再生效。每日数量与账户真实并发由派单者核实，workflow 不声称实现了账户滚动额度计量。

每个工作包在原 Issue/PR 记录接单链接、交付链接、首次验收是否通过、复核与返工耗时、越界情况及 CI 结果。净节省时间以预计自行实现耗时减去派单/复核/返工耗时估算，标明估算；十个样本后统一评估，不制造另一份当前状态表。

出现越界、断言削弱或无法确认写入归属时停止该类别新增任务；先在 Jules 确认暂停/停止，再交主执行者处理。环境失效先修复快照，积压先审查现有 PR。需要回退 Tooling 时移除类别及路径准入并运行拒绝回归，已启动任务另行停工；不撤销生产门禁来追求吞吐。

网页计划可能定时自动批准，不能当作强制人工门禁。API 可用 `requirePlanApproval: true`，但 API/CLI 调度仍是后续评估项；不新增第二入口或定时任务，不创建 API key。未来迁移须保留权限核验、去重、文件占用、限流和回执取证。

## 外部依据与验证

- [CodeRabbit Triage rules](https://docs.coderabbit.ai/triage/rules)：条件、原生 Auto-fix 与 run 上限。
- [CodeRabbit Autofix](https://docs.coderabbit.ai/code/deliver-changes)：PR 持续修复控件及停止方式。
- [CodeRabbit billing](https://docs.coderabbit.ai/code/access-and-billing)：试用、额度与付费门槛。
- [GitHub concurrency](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency)：串行与 pending 队列上限。
- [GitHub PR files](https://docs.github.com/en/rest/pulls/pulls#list-pull-requests-files)：分页与 3000 文件上限。
- [Jules Environment](https://jules.google/docs/environment/)：Ubuntu 环境与快照。
- [Jules Plan](https://jules.google/docs/review-plan/) 与 [Sessions API](https://jules.google/docs/api/reference/sessions)：计划审批行为。
- [Jules Issue tasks](https://jules.google/docs/running-tasks/)：jules 标签触发。
- 本地回归：`python3 tests/bot-dispatch.py`，使用实际 workflow JavaScript 和模拟 API，禁止产生真实派单。
