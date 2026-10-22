# Renovate 配置准备验证记录

- 日期：2026-10-22
- 范围：新增 `renovate.json` 与迁移文档，补充 CI 文档路由和 Context；保留进入任务前的其他未提交规划改动。
- 执行边界：未提交、推送、创建远端资源或安装 GitHub App；未改依赖版本、workflow、Dependabot 配置或产品源码。

## 审查结论

本轮目标是准备可评审的第一阶段配置，不是完成远端迁移。全局 Dashboard approval 与关闭 Renovate 专用安全修复 PR 保留受控试运行边界；非主版本自动提 PR、旧配置删除和分支策略变更仍按[迁移步骤](../../renovate-migration.md)执行。

机器配置仅允许工作流 Actions 与根 Python requirements；保留 SHA pinning，屏蔽 Docker / runner datasource，无自动合并。没有改变生产 QEMU、磁盘或运行时行为；Python 依赖后续升级仍必须走完整 CI。

## 客观验证

环境：Windows PowerShell；Node v24.13.0、npm 11.6.2、Python 3.14.2、PyYAML 6.0.3。

| 命令 | 结果 |
| --- | --- |
| `npx --yes --package renovate@44.176.2 -- renovate-config-validator --strict --no-global renovate.json` | exit 0；`Config validated successfully against 1 file(s)` |
| `python -X utf8 scripts/governance-docs-check.py` | exit 0；治理文档检查通过 |
| `python scripts/check-config.py` | 已跟踪 JSON/YAML 解析及重复键检查通过 |
| `python tests/ci-policy.py` | 16 tests，OK；缺失 Git 对象的 fatal 输出来自故意构造的无效基线夹具，测试最终通过 |
| `python scripts/check-tree.py` | 已跟踪文本 UTF-8/LF/空白检查通过 |
| `python -X utf8 -`（下述 stdin 检查） | 新增配置及本轮文档 UTF-8/LF/空白、JSON 重复键检查通过 |
| `git diff --check` | exit 0，无输出 |

stdin 检查复用 `runpy.run_path('scripts/check-tree.py')['check']`，逐一检查本轮文件的原始字节；另以 `json.loads(..., object_pairs_hook=unique_pairs)` 拒绝 `renovate.json` 重复键。新文件尚未加入索引，因此不依赖 `git ls-files` 的全树扫描覆盖它们。

官方 validator 的环境警告：Windows 上可选 `re2` 模块不可用，回退 RegExp；退出码仍为 0。本配置未引入自定义正则。npm 安装期间也输出传递依赖 deprecated 提示；这些是验证工具缓存依赖，没有加入项目 requirements 或新增项目锁文件。此记录不将该次验证描述为无警告运行。

## 未运行与证据边界

- 未进行 App 授权、onboarding / Dependency Dashboard、真实依赖 PR、CodeRabbit 对机器人 PR 的审查或 `master` 分支保护验收；本地文件不能证明这些设置生效。
- 未运行云端 `CI result`、原生镜像构建或设备测试：本轮无产品/依赖版本变更，且用户仅授权本地准备；后续提交配置仍由现有 CI 保守路由执行完整检查。
- GitHub Dependency graph、Dependabot Alerts / security updates 的实际启用状态未查询或修改，不能由现有 YAML 推断。
- 准备阶段未修改长期决策或风险/技术债台账；启用临时机器人分支和自动提 PR 前，按迁移文档补充 ADR 0005 对应策略。
