# 2026-10-22 运行架构规划审查

## 范围与输入

- 用户要求同步远端，延续项目分析形成可执行规划，本轮不开发功能；新增约束为 RK3588 仅 Docker 验证、Mac 兼容 KVM 并评估最佳容器化性能。
- `C:\DockDSM` 初始为空目录，未发现已有 Git 或用户文件；从 `https://github.com/Ben8368/DockDSM.git` clone 到该目录。
- `git rev-parse HEAD` 与 `git ls-remote origin refs/heads/master` 均为 `2bebdb27af7b9d0185ce93b96a4b4eb0525b9331`。初始工作树干净；仅本地文档变更，未 commit/push/publish。
- 关联聊天读取工具仅返回占位符；经用户提供的[分享链接](https://chatgpt.com/share/6ad9a9ea-a228-83ea-9c94-b4c2aaadc0fa)在 Codex 浏览器读到完整建议：保留兼容成果、先性能后半重构、ARC 可选。
- 阅读当前平台/状态/治理、入口与平台脚本、健康/关机、Dockerfile、生产补丁和历史 ARM 证据；官方参考核对集中列于 [Mac 选型](../../mac-container-evaluation.md)、[性能协议](../../performance-baseline.md)及 [ARC 路线](../../arc-integration.md)。

## 规划决定

- [实施计划](../../implementation-plan.md)定义 G0–G5、工作包、依赖、责任域和退出/回退条件；[架构契约](../../runtime-architecture.md)定义后续实现边界。
- [ADR 0006](../../ADR/0006-runtime-profiles-and-container-first.md)替代 ADR 0004 的统一 ARC 目标及优先顺序，保留历史重建与归属决定。
- x86、M5、RK3588 为主矩阵；RK 测试均在 Docker 内，Mac 以 Colima/VZ 为比较基准，Apple container、Desktop VZ/VMM 先筛资格再测性能。
- 既有 ENV、QEMU 四补丁、启动脚本、Dockerfile、Compose、测试和 CI 均未修改。新接口/选项均明确标为拟议。
- TD-002/003 记录实际供应链与编排妥协；RISK-002/006 更新执行路线，RISK-007 记录 Mac 新后端未验收。

## 本地验证

使用 Windows PowerShell / Python 3.14.2，Python 命令显式 `-X utf8`。新 clone 按仓库要求运行 `python -X utf8 scripts/install-git-hooks.py`，仅设置本仓库 hooksPath，成功。

首轮全树检查发现 Git for Windows 全局 `core.autocrlf=true` 将 74 个新克隆文件转换为 CRLF。已仅设置此 clone 的 `core.autocrlf=false`，将检出内容恢复为 LF；转换前确认所有非 Markdown 文件规范化后与 HEAD 完全相同，没有修改源码内容。修复后重新验证通过。

| 检查 | 结果 |
| --- | --- |
| `python -X utf8 scripts/governance-docs-check.py` | 通过；预算、文档链接与 ADR 头部 |
| `python -X utf8 scripts/check-tree.py`，另查新增 Markdown 的 UTF-8/LF/空白 | 通过；新增文件复用 check-tree 的 check 函数逐项检查 |
| `python -X utf8 tests/branding.py` | 5/5 通过；品牌、来源、内部兼容与 ARC 未混入生产 |
| `git diff --check` | 通过 |
| 改动路径审计：仅 Markdown，现有产品代码/测试/配置未变 | 通过；12 个已有文档更新、7 个新增文档，共 19 个 Markdown |

范围审计通过 `git diff --name-only -z` 与 `git ls-files --others --exclude-standard -z` 的并集检查：全部为 `.md`，并逐个执行编码/空白检查。新增文件没有被仅扫描 tracked files 的全树命令遗漏。未创建分支或执行提交，规划保留为可审阅的本地变更。

## 未覆盖

本轮没有连接三台设备、构建镜像、下载 PAT、启动 DSM、执行 KVM/性能/网络/恢复测试或云端 CI。Mac 官方文档说明能力选项，不等于 DockDSM 验收；没有宣称哪一候选最快。x86 OS/CPU、RK 板型/内核/资源、Mac 软件版本在 W00 实施时登记。
