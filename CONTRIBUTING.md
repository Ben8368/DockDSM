# 贡献指南

## 范围与事实源

先读 [当前状态](CONTEXT.md)与[产品范围](docs/PRODUCT.md)。当前代码仍是 Virtual DSM x86 和实验性 DS124 ARM64；ARC 接入和 ARM64 loader 移植不能仅凭构建或重命名宣称完成。

## 分支与提交

- 主分支为 `master`；工作分支默认使用 `codex/` 前缀，一个 PR 只表达一个可审查主题，合并后删除已合入分支。
- Conventional Commit 类型前缀保留英文，标题与正文用中文。
- AI 工具参与须附工具级 `Co-authored-by`；纯人工使用 `Human-authored: true`。详细规则只在 [AI_RULES](docs/AI_RULES.md) 维护。
- 安装本地钩子：`python3 scripts/install-git-hooks.py`。文件保存为 UTF-8、LF。
- 不提交凭据、PAT、磁盘、长串口日志或临时研究产物；源码归属与许可说明不能因历史重建而删除。

## 验证与审查

```bash
python3 scripts/governance-docs-check.py
python3 scripts/git-hooks-test.py
python3 tests/branding.py
python3 tests/ci-policy.py
python3 scripts/check-tree.py
bash research/arm64/tests/smoke.sh
```

配置测试需要 PyYAML；完整合成、补丁与镜像命令以 [CI 设计](docs/ci.md) 和 [质量门禁](docs/QUALITY.md)为准。修改产品源码需在完整验证前输出 `🚦 Audit Report`；运行时能力另需目标环境证据，不能用合成测试替代。

PR 使用仓库模板，写明命令、结果、未覆盖项及必要的风险/技术债/ADR。`CI result` 是统一自动门禁：不允许必需任务失败、取消或意外跳过。只有文档变更能按策略跳过原生镜像检查；发布必须强制完整检查。CodeQL、标签和 stale 不代替人工审查。
