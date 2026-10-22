# CI 重设计本地验证记录

日期：2026-10-22。环境：Windows Python 3.14；WSL Ubuntu 24.04 amd64 / Python 3.12。此记录仅描述本地验证，不代表最终提交的云端 CI 结果。

## 范围

README、部署/贡献指南、CI 权威文档、ADR 0005；范围规划、全树编码/空白检查与 fail-closed 结果门禁。未修改 DSM 启动实现、生产 QEMU 补丁、基础镜像或依赖版本。

## 命令与结果

下列命令在仓库根目录执行，均以退出码 0 通过；Linux 命令在 WSL 中运行。

| 命令 | 结果 |
| --- | --- |
| `python scripts/governance-docs-check.py` | 文档预算、路由与链接通过 |
| `python tests/branding.py` | 5 项通过；来源与 ARC 未集成边界保留 |
| `python tests/ci-policy.py` | 16 项通过；根提交、docs-only、混合/多提交、改名、未知基线、失败/取消/跳过、发布和 workflow wiring |
| `python scripts/check-tree.py` | 暂存新增/删除后，全树 UTF-8/LF/BOM/空白检查通过 |
| `python scripts/check-config.py` | 跟踪 JSON/YAML 解析及重复键检查通过 |
| `python scripts/git-hooks-test.py` | Codex/Cursor/Claude/人工署名路径通过 |
| `git diff --cached --check` | 无空白错误 |
| `actionlint -color` | 校验官方 release checksum 后使用 v1.7.12；全部 workflow 通过 |
| `git ls-files -z '*.sh' | xargs -0 shellcheck -x` | 全部跟踪 shell 文件通过 |
| `bash tests/qemu-patches.sh` | 固定 QEMU v8.2.2 身份及生产补丁干净应用通过 |
| `QEMU_SOURCE_OVERRIDE=https://github.com/qemu/qemu.git bash tests/qemu-patches.sh` | 固定 GitHub mirror 路径通过 |
| `bash research/arm64/tests/smoke.sh` | 平台、存储、参数、错误路径通过 |
| `bash tests/production-x86-command.sh` | host fake-QEMU argv/退出码回归通过；不是镜像运行结果 |

安装 `requirements.txt` 和 PyYAML 6.0.3 后，在临时 WSL venv 中执行以下命令，均通过；ARM installer 在 root 下运行，以恢复合成夹具属主与特殊文件：

```bash
bash tests/pat-acquisition.sh
python tests/package-readiness.py
python tests/surveillance/readiness.py
python tests/surveillance/install.py
python tests/guest-integrations.py
bash tests/guest-clock.sh
python tests/image-validation.py
python tests/arm-installer.py
python tests/arm-runtime.py
python tests/x86-installer-regression.py
python tests/proprietary-artifacts.py
```

## 限制与外部证据

- 没有下载 DSM PAT、运行真实 DSM、验证 ARC、ARM64 ARC、摄像头或新的 KVM 环境；相关缺口仍见 RISK-003/005/006。
- amd64/arm64 原生镜像、patched-QEMU DC ZVA 和 CodeQL 由最终提交的 GitHub Actions 验证，不能由上述 host 测试替代。
- 旧失败 [39720608177](https://github.com/Ben8368/DockDSM/actions/runs/39720608177) 的日志确认根提交遗留尾随空格；保留旧记录，不删除失败 run。
- 重写前根提交 `aab43a41353fac1678d5c0cd5263994def112d89` 已在仓库外保存完整 bundle 并通过 `git bundle verify`；归档仓库与辅助 detached worktree 均保留。
