# AI 开发与审查规则

> 协作入口见 [AGENTS.md](../AGENTS.md)，当前状态见 [CONTEXT.md](../CONTEXT.md)，文档治理见 [GOVERNANCE.md](GOVERNANCE.md)。

## 1. 工作顺序

```text
读取 Context / Lessons → 检查宿主环境 → 确认当前阶段与事实源 → 修改 → 红绿灯审查 → 客观验证 → 更新唯一权威文档 → 汇报
```

- 答疑或评审只做只读检查，除非用户同时要求修改。
- 默认不自动提交、推送、发布或创建外部资源。
- **开始任何实施、本地构建或验证前**，先检查并在本轮汇报中写明宿主环境；纯概念答疑可跳过。至少确认：
  - OS：Windows / macOS / Linux（若为 WSL，标明“Windows + WSL”，不要只写 Linux）
  - CPU 架构：`x86_64`/`amd64` 或 `arm64`/`aarch64`
  - Shell：PowerShell / bash / zsh 等，后续命令按此选择
  - 建议探测：`uname -s` / `uname -m`（Unix/WSL）；Windows 原生可用 `$PSVersionTable.OS` 与 `$env:PROCESSOR_ARCHITECTURE`
  - 按探测结果选择路径、换行、包管理与 Docker/QEMU 命令；未确认前不得假设 Linux bash 或错误架构。可复发细节见 [host-env](lessons/host-env.md) 与 [windows](lessons/windows.md)。
- 开始实施前评估任务复杂度；对范围清晰、低风险、可独立验收且符合 Jules 表单的简单文档 / 测试任务，主动考虑派单完成全部或部分工作，其余工作由当前执行者负责。纯答疑、紧耦合步骤或不适合机器人权限的任务直接本地处理，不为派单而拆分。

## 2. 红绿灯审查

产品源码发生变化后、运行完整验证前，必须输出：

```markdown
## 🚦 Audit Report

**总体评价：** [ 🔴 阻断 / 🟡 可通行 / 🟢 通过 ]

**1. 🔴 阻断项：**
- 无 / 具体问题

**2. 🟡 跟进项：**
- 无 / 具体问题及权威登记位置

**3. 验证计划：**
- 命令、真实路径与未覆盖项
```

审查至少覆盖：真实性、范围、生产/研究边界、补丁与凭据安全、异常路径、可测试性。

分级：

- 🔴：安全越界、伪造就绪、生产/研究补丁混用、数据丢失、契约破坏或阶段越权。
- 🟡：不阻断当前目标，但存在已登记的兼容性、性能或验收缺口。
- 🟢：范围内目标完成，客观验证通过，没有未登记风险。

🔴 不得合并或宣称完成；🟡 必须进入 `RISK_REGISTER` 或 `TECH_DEBT`。

## 3. 验证层级

| 变化 | 最低验证 |
| --- | --- |
| 仅治理文档 | `python3 scripts/governance-docs-check.py` |
| Shell / 平台脚本 | 上述 + `shellcheck` + `bash research/arm64/tests/smoke.sh` |
| QEMU 补丁 | 上述 + `bash tests/qemu-patches.sh` |
| 生产镜像 / ARM 行为 | 上述 + 文档化冷启动或合成回归；不得用构建代替访客证据 |

未执行的项写“未运行”及原因。

### Jules 任务拆分

- 派单前确认子任务可独立交付，限定 1–3 个精确文件路径，并写明验收条件与验证命令；使用仓库现有 Small task for Jules 表单和 `bot-dispatch` workflow，不另开并行写入通道。
- 用户已授予常设授权：符合本节条件的简单文档 / 测试任务可直接通过表单派单，无需再次询问一般性授权；仍须在表单中明确当前任务的授权、精确路径、验收条件和验证命令，并确认没有其他写入者。该常设授权不扩大当前任务范围、允许类别 / 路径或仓库自动化权限。
- Jules 只负责约定的子任务；主执行者复核实际 diff、运行约定验证并整合。Jules 的 PR、CI 通过或自述均不替代代码审查和目标环境证据。
- 无法安全派单或派单失败时，继续由当前执行者完成，不等待机器人；完整派单边界和流程见 [机器人自动化操作约定](bot-automation.md#issue小任务表单jules)。

## 4. 文档与 Git

- 只更新发生事实变化的权威文档，遵守 [GOVERNANCE.md](GOVERNANCE.md)。
- 默认不自动 `git commit` / `git push` / 发布；仅在用户明确要求时执行。

### PR 推送与远端验证

- 本地验证完成后，**仅在用户明确要求时**推送工作分支并创建 PR；**不阻塞等待远端 CI**。汇报 PR 链接、HEAD SHA 与“`CI result` 待核验”即可结束本轮。
- 默认一个工作包 / 用户请求对应一个直接面向 `master` 的 PR；一个 PR 可以包含多个主题清晰、可分别审查的 commit，不要求压成单 commit。先在本地整合全部范围并完成验证，再一次性推送并创建 PR，避免提前开依赖 PR 或逐个推送中间状态。
- 需要远端结果时运行 `gh pr checks <number>`；失败在同一分支追加修复提交，不重写已推送历史。
- **合并前**必须同时确认：`CI result` 为 success，且 **CodeRabbit** commit status 为 success（非 pending / error）。推送/开 PR 后仍不阻塞等待；仅在用户要求“本轮合并”或维护者准备合入时轮询二者。`CI result` 先绿不等于可以立刻合并——CodeRabbit 常更晚才开始审查。
- **不把** CodeRabbit 配成 GitHub branch protection 的 required check（可能长时间 pending，不能挡死已通过的 `CI result`）。流程门禁与硬门禁分开；确需跳过兔子时，维护者须在 PR 注明原因（服务故障、明显队列异常等）。
- 默认由维护者合并；只有用户明确要求“本轮合并”时，才等待上述检查并在通过后合并。
- 只有确有独立审查 / 发布边界时才拆多个 PR；不要创建以另一个未合并 PR 为 base 的 stacked PR。依赖 PR 必须串行：当前 PR 合入后，从最新 `master` 建立下一个候选分支，再推送并创建 PR。若候选 PR 已提前堆叠，先等前项合入，再以新分支从最新 `master` 搬运后续提交，不改写已推送分支历史。
- PR 新 head 会重新触发 CI 与 CodeRabbit；自动审查按仓库配置运行（当前面向 base 为 `master` 的非 draft PR）。本地先完成并批量提交可减少无效运行，但修复或更新后重新验证不可省略。不得为减少 CI 次数而过滤必要 PR 检查、放宽 strict 分支保护或跳过审查。
- 若 GitHub Merge Queue 已启用且 CI 支持 `merge_group`，可用队列验证最新基线；仍遵循每个工作包一个 PR 的默认规则，合入前仍须 CodeRabbit success（除非维护者按上款书面跳过）。
- 不启用自动合并，也不因等待超时绕过分支保护或擅自跳过 CodeRabbit。

- 不修改或清理用户的无关改动，不使用破坏性 Git 命令；不得提交凭据、PAT 或磁盘镜像。

### 提交信息与 AI trailer

- 标题与正文使用中文；Conventional Commit 类型前缀与 Git trailer 键名保留英文，例如 `feat:`、`fix:`、`docs:`。
- 一次提交只表达一个可审查主题。
- AI 工具参与实质改动并执行提交时，在 message 末尾追加对应 `Co-authored-by` trailer，前方保留一个空行。主作者保持维护者身份。
- trailer 记录**工具来源**，不记录具体模型。

| 当前工具 | 必须追加的 trailer |
| --- | --- |
| Codex | `Co-authored-by: Codex <codex@openai.com>` |
| Claude Code | `Co-authored-by: Claude Code <noreply@anthropic.com>` |
| Cursor（含 Cursor Agent / Auto） | `Co-authored-by: Cursor <cursoragent@cursor.com>` |
| Google Jules | `Co-authored-by: Google Labs Jules <161369871+google-labs-jules[bot]@users.noreply.github.com>` |

Windows PowerShell 中不得在单个 `git commit -m` 字符串内嵌入 `\n`。正文与 trailer 使用独立 `-m` 参数：

```powershell
git commit -m "docs: 标题" -m "正文说明。" -m "Co-authored-by: Cursor <cursoragent@cursor.com>"
```

提交后必须执行：

```powershell
git show -s --format=%B HEAD | git interpret-trailers --parse
```

确认对应 `Co-authored-by` 出现在解析结果中。

### 仓库级署名校验

每个独立 clone 都应运行 `python3 scripts/install-git-hooks.py`，启用 [.githooks/commit-msg](../.githooks/commit-msg)。安装只设置该 clone 的 `core.hooksPath`。纯人工改动用 `Human-authored: true`；有 AI 参与不得混用该声明。CI 运行 hook 回归，不扫描或重写旧提交。
