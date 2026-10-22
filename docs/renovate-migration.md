# Renovate 分阶段迁移

本文件定义迁移步骤与验收条件；当前执行状态只见 [CONTEXT.md](../CONTEXT.md)。机器可执行策略以 [renovate.json](../renovate.json) 为准，CI 与发布边界见 [ci.md](ci.md)。准备阶段只提供配置；依赖升级与远端设置按下述步骤另行验收。

## 管理范围与安全修复归属

- `github-actions` 只扫描 `.github/workflows/**`，保留完整 commit SHA 和版本注释；非主版本分组包含 `digest` / `pinDigest` / `pin` 更新，避免 SHA 更新游离于分组之外。
- `pip_requirements` 只扫描根目录 `requirements.txt`。其中 `dissect.cstruct` 与 `dissect.extfs` 用于生产镜像与合成夹具，不能按纯开发依赖降级验证。
- Dockerfile、Compose 镜像、QEMU、生产补丁和研究脚本继续人工管理。另禁用 `docker` 与 `github-runners` datasource，并排除 Actions manager 的 `python` 运行时依赖，避免顺带更新工作流容器、runner 和 Python 解释器版本。工作流 `run:` 中硬编码的 PyYAML / 工具版本不在本次自动更新范围。
- 保留 GitHub Dependency graph 与 Dependabot Alerts；安全修复 PR 继续由 GitHub Dependabot security updates 设置决定。`open-pull-requests-limit: 0` 只关闭普通版本 PR，不关闭安全更新。
- 显式关闭 Renovate 的 `vulnerabilityAlerts` 与 `osvVulnerabilityAlerts`，避免重复的专用安全修复 PR。普通版本 PR 仍可能包含漏洞修复，不承诺每个漏洞都可自动修复；外部告警需要维护者跟进。

Renovate 的漏洞修复 PR 在满足权限和告警前提后可默认生成，并绕过普通 schedule / PR 频率限制及 Dashboard 审批默认值，因此不能仅靠顶层限额控制安全更新。参见 [Renovate 配置说明](https://docs.renovatebot.com/configuration-options/#vulnerabilityalerts)与 [GitHub PR 限额说明](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference#open-pull-requests-limit)。

## 第一阶段：配置评审与受控试运行

1. 在独立变更中评审配置，保留 [.github/dependabot.yml](../.github/dependabot.yml) 的全部版本 PR 限额为 0。本阶段根级 `dependencyDashboardApproval: true` 使所有普通更新先等待 Dashboard 批准；`major` 中的同名设置为后续放开非主版本时保留。
2. 维护者决定启用试运行时，只给 [Renovate GitHub App](https://github.com/apps/renovate) 授权 DockDSM。检查 onboarding PR（若生成）；若默认分支已包含有效配置，App 可能直接使用它。不要让默认 onboarding 内容覆盖本配置的范围与门禁。
3. 确认仓库存在 `dependencies`、`pinned` 标签。Dashboard 使用这两个标签；现有 Stale workflow 豁免 `pinned` Issue，普通依赖 PR 已豁免 `dependencies`。检查标签实际生效。
4. 按 [ADR 0007](ADR/0007-bot-collaboration.md) 使用短期 PR 分支；它补充 ADR 0005 的初始化分支策略，保留 CI、人工审查和发布边界。配置 `master` 的 PR 合并要求与稳定必需检查 `CI result`，排除机器人的直接推送和规则绕过权限，不启用自动合并。
5. 核查 GitHub Dependency graph、Dependabot Alerts 和 security updates 的实际设置，记录安全修复负责人；仓库文件存在不证明这些服务已启用。只要求 `CI result` 为统一必需检查，避免把按事件合法跳过的 CodeQL job 设为无条件必需。
6. 查看 Dashboard 与 Mend 运行日志，确认提取到两个根 Python 包和工作流 Actions，且没有 Docker、runner 或 QEMU 更新。没有可用更新时保留日志证据，不通过故意降级依赖制造测试 PR。
7. 有合适候选时，维护者批准一个更新，核查 PR diff、release notes、SHA 固定与 `CI result`。验证 CodeRabbit 是否实际审查机器人 PR；配置文件与普通用户 PR 的表现不能证明其覆盖 Renovate PR。

`schedule` 是上海时区周一全天的允许窗口，不是保证准时执行的定时器；实际扫描由托管服务排队决定。`updateNotScheduled: false` 限制窗口外刷新已有分支；Dashboard 的显式操作可触发额外处理，验收时应记录是否人工触发。普通更新最多 3 个并发 PR、每小时 2 个新 PR；全局禁止自动合并。

本地验证只能证明配置可解析与仓库策略仍通过；不能证明 App 授权、Dashboard、PR、CodeRabbit、分支保护或云端 CI 已经运行。

## 第二阶段：验收后切换

进入条件：有 Dashboard / 提取日志证据、一次受控 PR 的差异与当前 SHA 的 `CI result`，并确认人工合并和分支保护有效。

1. 在单独变更中把根级 `dependencyDashboardApproval` 改为 `false`（或删除），保留 `major.dependencyDashboardApproval: true`。此时非主版本可按窗口自动提 PR，主版本仍先审批。
2. 再决定移除 Dependabot 的版本更新配置。现有文件在限额为 0 时不会重复生成普通版本 PR，可暂留用于安全更新定制；移除前核查对 security updates 分组、提交信息等设置的影响。
3. 如果删除 `.github/dependabot.yml`，同步修改 `tests/ci-policy.py` 中读取该文件并断言限额为 0 的检查，以及 Labeler 中对应路径。应改为验证新的依赖策略，不能删除整个双架构/机器人策略测试来规避失败。
4. 保留 Dependabot Alerts 与既定安全修复归属。未来若切换到 Renovate 处理安全修复 PR，先验证权限、漏洞提取和补丁 PR，再协调关闭 GitHub security updates，避免双重提交或修复空窗。

短期依赖分支已由 ADR 0007 允许；第二阶段仍须满足上述验收条件，不能直接把历史 ADR 的“暂停”改写成已迁移。

## 回退

- 暂停 Renovate 时设置根级 `enabled: false`，或由维护者暂停 App 的仓库访问。仅恢复 Dashboard approval 不保证停止已经批准的分支；已有 PR / 分支需单独检查、按需关闭，不批量删除未知分支。
- 保留 Dependabot Alerts 和安全修复责任。若需恢复 Dependabot 普通版本 PR，先停用 Renovate 普通更新，再显式恢复相应生态的限额、测试与分支策略。
- 配置迁移不包含依赖版本变更；后续依赖 PR 的回退通过独立 revert / 恢复版本处理，并重新运行其必要检查。

## 本地验证

在仓库根目录执行；Windows 使用实际 Python 解释器 `python`，Linux/WSL 使用 `python3`：

```text
npx --yes --package renovate@44.176.2 -- renovate-config-validator --strict --no-global renovate.json
python scripts/governance-docs-check.py
python scripts/check-config.py
python tests/ci-policy.py
python scripts/check-tree.py
git diff --check
```

Renovate CLI 版本固定为本次验证使用的版本；环境需满足该版本的 Node 要求，托管 App 版本由服务管理。`check-config.py` 与 `check-tree.py` 只扫描 Git 已跟踪文件，因此未加入索引的新配置还须用上面的官方 validator 和显式 UTF-8/LF 检查覆盖；不要把解析成功写成外部集成验收成功。

## 官方参考

- [托管服务范围与限制](https://docs.renovatebot.com/mend-hosted/overview/)：Community Cloud 免费适用于公开及私有仓库，存在资源和调度限制，不把免费额度写成永久承诺。
- [Dashboard 审批](https://docs.renovatebot.com/configuration-options/#dependencydashboardapproval)、[计划窗口](https://docs.renovatebot.com/configuration-options/#schedule)。
- [Actions SHA 固定](https://docs.renovatebot.com/modules/manager/github-actions/#digest-pinning-and-updating)、[官方配置验证器](https://docs.renovatebot.com/config-validation/)。
