# DockDSM CI、检查与发布

## 设计原则

CI 验证仓库当前已有实现，不下载 DSM PAT、不启动真实 DSM、不用合成测试宣称 ARC 或 ARM64 loader 已支持。所有执行源码的常规 CI 使用只读权限，不注入仓库秘密；发布是独立人工操作。

## 三层流水线

| 层级 | 触发 | 检查 |
| --- | --- | --- |
| 常规 CI | 推送到 master、面向仓库的 PR、手动运行 | Plan、Docs、Lint、双架构合成、QEMU 补丁、research smoke、统一结果门禁 |
| 原生镜像 | 由 CI 保守路由，或 Native image checks 手动运行 | amd64 / arm64 原生构建、ELF/库/依赖、构建失败诊断、x86 命令、DC ZVA 回归 |
| 发布 | Publish image 手动输入版本 | 强制完整 CI，通过后才构建/推送 GHCR digest，并创建和检查双架构 manifest |

常规主流程为 [test.yml](../.github/workflows/test.yml)，原生镜像检查复用 [arm-qemu-build.yml](../.github/workflows/arm-qemu-build.yml)，静态检查复用 [check.yml](../.github/workflows/check.yml)。文件名保留以稳定徽章和外部调用；工作流角色不由旧名称推断。

### 范围路由

[scripts/ci-plan.py](../scripts/ci-plan.py) 读取 GitHub 事件 JSON 和完整 Git 历史，不把事件输入拼接进 shell：

- 初始化根提交、重写后的根提交、全零/缺失/不可解析基线：**完整检查**。
- push 比较事件的 before → 当前 HEAD；PR 比较 merge-base → checkout HEAD，使用关闭 rename 检测的路径集合，避免把代码改名成文档来漏检。
- 只有非空、完全由 Markdown、NOTICE 或 license.md 组成的差异才跳过镜像；常规检查仍全部运行。
- Dockerfile、依赖、源码、测试、Compose、workflow 或未知路径变更均运行镜像。
- 手动运行及可复用调用默认走完整检查；`full=true` 显式强制。发布调用固定 `full: true`，不能由文档路由省略发布前检查。

### 固定结果门禁

`CI result` 使用 `always()`，依赖 Plan 与全部检查，通过 [scripts/ci-result.py](../scripts/ci-result.py)汇总：

- Plan、Docs、Lint、双架构合成、补丁与 smoke 必须 success。
- 计划要求镜像时必须 success；只有明确的 images=false 才接受镜像 skipped。
- 失败、取消、缺失输出、非预期 skipped 或依赖集合漂移均返回非零。
- master 的 required check 使用稳定的 `CI result` 并绑定 GitHub Actions；不可只要求某个可能跳过的子 job。PR、最新基线、讨论解决与管理员约束遵循 [ADR 0007](ADR/0007-bot-collaboration.md)。
- 2026-10-22 经 GitHub API 核验：`master` 使用 classic branch protection（Rulesets 未启用），必需检查为 `CI result`（strict），要求线性历史、解决审查讨论、禁止强推与删除分支，`enforce_admins=true`；required approving reviews = 0，符合单维护者设计。规则变更时更新本行日期与内容。

普通功能分支 push 不触发常规 CI；PR 的每个新 head 会运行对应检查。普通 push/PR 的新提交可取消旧检查，但被取消前已经消耗的 runner 时间无法收回。手动运行不会主动取消同组旧检查，但 `master` push 可取消正在运行的手动 `test.yml`；发布运行不由较新提交取消。CI 不自动合并、提交或发布。

PR 推送后 CI 在后台运行，创建者无需保持会话等待；合并前用 `gh pr checks <number>` 确认 `CI result` 与 CodeRabbit 均为 success。CodeRabbit 是流程门禁，不是 branch protection 的 required check；细则见 [AI_RULES](AI_RULES.md#pr-推送与远端验证)。

默认每个工作包只创建一个直接面向 `master` 的 PR，可用多个 commit 保持改动可审查。依赖改动先在本地整合后一次性推送，避免 stacked PR 在前项合入后改 base / 同步新 head，导致 CI 和自动审查重复运行。确需多个 PR 时按顺序逐个创建：前项合入后，再从最新 `master` 建立并推送下一项。详细协作规则见 [AI_RULES](AI_RULES.md#pr-推送与远端验证)。

## 检查覆盖

- **Docs governance**：文档预算/链接、品牌与来源、署名 hook、全树编码/空白、CI 策略回归。
- **Lint**：Bash syntax、ShellCheck、Hadolint、JSON/YAML 重复键、校验下载的 Actionlint、整个根提交 whitespace。
- **Synthetic regression tests**：原生 amd64、arm64 runner 上的 PAT 获取策略、包诊断、Surveillance 安装门禁、clock、image/installer/runtime 等；夹具不下载 DSM，installer 在可丢弃 runner 上使用 sudo 恢复属主与特殊文件。
- **QEMU patch apply**：固定 QEMU v8.2.2，检查主来源及 GitHub mirror 回退、源码身份和补丁干净应用。
- **Research smoke**：研究脚本参数、平台和错误路径，不作为真实访客验收。
- **Production image build**：固定平台的原生 Docker 构建；架构/库/import、构建诊断、fake-QEMU x86 argv 和真实 patched-QEMU DC ZVA 合成验证。成功不代表 DSM 启动、KVM 或摄像头验收。

CI 策略由 [tests/ci-policy.py](../tests/ci-policy.py)回归，覆盖根提交、docs-only、混合/多提交变更、代码改名、缺失基线、发布强制与失败/取消/跳过门禁。

## 初始化提交与历史错误

重建历史会让所有文件成为根提交的新增内容。此前失败运行 [39720608177](https://github.com/Ben8368/DockDSM/actions/runs/39720608177) 的根因是 README、devcontainer JSON 和 power.sh 遗留尾随空格，不是 ARM64 或 ARC 启动失败；旧失败记录不等于当前 HEAD 失败。

[scripts/check-tree.py](../scripts/check-tree.py) 每次扫描所有 Git 跟踪文本的 UTF-8/LF/BOM 和尾随空格，不仅检查最近 diff。统一 diff 补丁允许格式必需的行尾空格；补丁本身仍须通过 apply 检查。`git show --format= --check HEAD` 继续保留，不靠忽略错误“变绿”。实际结果查当前提交 SHA 的 Actions/checks，而不是历史失败条目总数。

## 本地验证

以下在仓库根目录 Linux/WSL 执行；源码检查不依赖 GitHub Secrets：

```bash
python3 -m pip install PyYAML==6.0.3
python3 scripts/governance-docs-check.py
python3 tests/governance-docs.py
python3 tests/branding.py
python3 tests/ci-policy.py
python3 tests/arc-overlay.py
python3 tests/bootloader-source-audit.py
python3 scripts/check-tree.py
python3 scripts/check-config.py
python3 scripts/git-hooks-test.py
bash research/arm64/tests/smoke.sh
bash tests/production-x86-command.sh
bash tests/qemu-patches.sh
git diff --check
```

镜像检查的实际测试命令见可复用 workflow；本地执行前先构建镜像，不能只运行 host snapshot 便宣称 image regression 通过。

## Publishing

镜像目标为 `ghcr.io/ben8368/dockdsm`；只有维护者明确要求才手动运行 [Publish image](../.github/workflows/build.yml)。首次发布前优先从源码构建，仓库初始化不会自动发布镜像。

- 只允许从默认分支输入 `MAJOR.MINOR.PATCH` 版本；镜像名称来自小写 `github.repository`。
- `checks` 强制完整 CI 后，原生 amd64/arm64 job 构建带版本参数的镜像，按 digest 推送并验证。
- 两套 digest 都成功后才创建版本与 latest 多平台标签，并检查 manifest 的实际架构。
- 只有 publish/manifest job 有 `packages: write`；使用 `GITHUB_TOKEN`，不要求个人 PAT、Docker Hub 账户或邮件凭据。
- 新仓库与旧 GHCR package 的授权不是同一件事；实际发布前需核对包关联、写权限与公开可拉取性。本轮只验证构建，不执行发布。

构建输入身份与尚未解决的包仓库 / configure-time 下载边界记录于[依赖清单](dependency-locks.md)和[技术债](TECH_DEBT.md)。网络/源拉取失败须与编译、补丁或产品错误分开诊断。

## Repository automation

- **CodeQL**：独立扫描 Actions 与 Python；push、周计划和授权的同仓 PR，fork/Dependabot PR 不上传只读 token 无权写入的结果，合并后的 push 再扫。它不扫描 QEMU C、Bash 或 guest，不替代完整安全评审。
- **PR labeler**：pull_request_target 只读取 API 路径，不 checkout/执行 PR 代码；只加标签。
- **Stale**：90 天标记，不关闭；draft、依赖、安全、数据丢失、ARM/QEMU 等保护标签豁免。
- **Dependabot**：版本更新 PR limit=0，避免与 Renovate 重复；保留 Alerts 与 security updates，安全修复 PR 仍须 CI 和人工合并。
- **Renovate**：按[分阶段迁移](renovate-migration.md)准备受控接入；配置先要求所有普通更新经 Dashboard 批准，安全修复归属和切换条件由该文档定义。启用及验收状态只见 [CONTEXT](../CONTEXT.md)。
- **CodeRabbit**：自动审查面向 master 的非 draft PR；合入前须其 commit status 为 success，但不写入 branch protection required checks。低风险 PR 原生自动修复条件见[机器人操作约定](bot-automation.md)，实际启用与证据见 [CONTEXT](../CONTEXT.md)。
- **Jules / Codex**：维护者小任务表单经 [bot-dispatch](../.github/workflows/bot-dispatch.yml) 校验后派给 Jules；仅 issues:write、不 checkout，不执行外部输入。Codex 接管核心修复；机器人不递归派单，CI 修复不扩大任务范围。
- **Docker Hub description**：删除未使用的 workflow；项目发布渠道为 GHCR，README 变更不再触发无凭据的同步空任务。

不启用自动发布、自动合并、Release Please、Codecov 或重复依赖机器人。
