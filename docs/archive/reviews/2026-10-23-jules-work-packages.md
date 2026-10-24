# Jules 受控工作包扩容：本地实现与验证

## 范围与环境

- 宿主：macOS / arm64 / zsh；Python 回归使用已有 `/private/tmp/dockdsm-fix-validation-venv/bin/python`（Python 3.11.15、PyYAML 6.0.3），Node 22。
- Shell smoke：外层 macOS，已有 `virtual-dsm:phase4b-arm64` 镜像内 Linux aarch64；只读挂载仓库、禁用网络、可执行临时 tmpfs。
- 本轮完善既有额度与维护者触发文档，新增 ADR 0010、Tooling 精确路径准入、显式验收和占用确认、Issue/PR 文件冲突及容量检查、轻量环境脚本与回归。未修改产品源码、生产镜像、依赖锁、发布或分支保护。
- 原有两处未提交改动（CONTEXT、bot-automation）作为本轮起点保留并完善。未提交、推送或创建真实派单；远端默认分支尚未部署本轮规则。

## Audit Report

- **总体：🟡 本地 L0/L1 通过；远端与云端环境待验收。**
- **🔴：** 未发现范围内新增生产写入或外部命令执行。Actions 不 checkout，不执行 Issue 内容；只增加 `pull-requests:read` 查询权限。
- **🟡：** RISK-008 保留 Jules 环境快照、Tooling、真实队列和停止/交接验证；TD-005 记录单 pending run 可被替换及重触发限制。应用写权限不构成文件级沙箱。

## 命令与结果

以下历史 `python` 命令使用上述已有 venv；历史 `python3` 命令（包括 `python3 tests/jules-setup.py`）的解释器绑定未知，不能确认其结果使用上述 venv、Python 3.11.15 或 PyYAML 6.0.3。历史执行命令保持原样记录；本轮如有重新验证，将另列实际解释器和结果。

| 命令 | 结果 |
| --- | --- |
| `python tests/bot-dispatch.py` | 19 项通过；执行实际 workflow JavaScript，API 全部 mock，无真实标签写入 |
| `python3 tests/jules-setup.py` | 4 项通过；在临时夹具执行真实 Bash 控制流，覆盖非 Linux、错误参数、check 不安装、安装/门禁失败保留退出码 |
| `python tests/ci-policy.py` | 21 项通过；缺失 Git object 的 fatal 文本来自预期失败场景，套件结果 OK |
| `python3 scripts/governance-docs-check.py` | 通过 |
| `python3 tests/governance-docs.py` | 11 个场景通过 |
| `python scripts/check-config.py` | 跟踪 JSON/YAML 校验通过 |
| `python3 scripts/check-tree.py` | 跟踪文本 UTF-8/LF/空白通过；新增文件另行检查编码与空白 |
| `bash -n scripts/jules-setup.sh` | 通过 |
| `shellcheck scripts/jules-setup.sh` | 通过 |
| `/private/tmp/dockdsm-jules-actionlint/actionlint .github/workflows/bot-dispatch.yml .github/workflows/test.yml` | Actionlint 1.7.12 通过 |
| `git diff --check` | 通过 |

Actionlint 使用与 CI 相同版本的官方 darwin/arm64 包，执行前匹配官方 checksums，归档 SHA256 为 `aba9ced2dee8d27fecca3dc7feb1a7f9a52caefa1eb46f3271ea66b6e0e6953f`。GitHub 的新 `queue: max` 字段试验被该版本拒绝，最终实现未使用该字段，也未降低校验。

Linux smoke 命令：

```bash
docker run --rm --network none --read-only --tmpfs /tmp:exec \
  -v /Users/ben/Project/Code/DockDSM:/workspace:ro -w /workspace \
  --entrypoint /bin/bash virtual-dsm:phase4b-arm64 \
  -c 'uname -sm; bash research/arm64/tests/smoke.sh'
```

结果为 `Linux aarch64`、platform tests passed、`ARM research smoke checks passed.`。首次未指定 `:exec` 时临时 fake-QEMU 不可执行，退出 126；仅调整容器临时挂载后通过，不是产品修复或真实 QEMU/DSM 启动。

## 既有回执与未覆盖项

- [Issue #22 接单回执](https://github.com/Ben8368/DockDSM/issues/22#issuecomment-6368743907) 与 [PR #24](https://github.com/Ben8368/DockDSM/pull/24)证明既有文档任务接单/交付；不证明本轮 Tooling 或扩容流程验收。
- 环境脚本测试使用工具桩，不代表真实 Jules VM 已安装依赖或保存快照。实际 Configuration → Run and Snapshot、云端 Docker 能力未运行。
- 未运行真实权限/分页/并发事件、额度计量、自动重触发或 Tooling 实现；workflow 只检查 GitHub 在途记录，账户与本地编辑仍由派单者核验。
- 未运行完整原生双架构镜像构建、DSM L2、KVM L3 或硬件验收；CI 路由与生产门禁保持原要求。

## PR #23 审查修复复核（2026-10-24）

历史 `python3` 命令的解释器绑定仍未知。本轮重新执行 `python3 tests/jules-setup.py` 时，实际解释器为 macOS arm64 上的 Python 3.11.15，6 项通过；新增测试用工具桩验证 venv Python 3.10 被拒绝、3.11 在 `--check` 下成功且不安装依赖。其他重新验证命令仍保留其实际调用形式，未将历史结果改写为新结果。

国家检测移除 curl 的 TLS 跳过参数并保留 5 秒超时。生产 runtime 的 apt 安装清单显式增加 `ca-certificates`，让国家服务请求使用系统 CA bundle；影响为增加该 runtime 系统包。完成目标镜像构建后仍需检查 `/etc/ssl/certs/ca-certificates.crt` 存在且 curl 默认验证启用。由于本轮 Docker daemon socket 不可用，未检查实际生产镜像或构建镜像。

本轮命令与结果：

| 命令 | 结果 |
| --- | --- |
| `python3 tests/jules-setup.py` | Python 3.11.15，6 项通过；含 venv 3.10 拒绝和 3.11 接受回归 |
| `PATH=/opt/homebrew/bin:$PATH /opt/homebrew/bin/bash tests/pat-acquisition.sh` | 通过；包含 TLS 证书校验失败时依次回退并选择全局镜像的离线回归 |
| `PATH=/opt/homebrew/bin:$PATH /opt/homebrew/bin/bash research/arm64/tests/smoke.sh` | 通过；ARM research smoke 与源码摘要断言通过 |
| `shellcheck -x src/pat.sh scripts/jules-setup.sh` | 通过 |
| `python3 scripts/governance-docs-check.py` | 通过 |
| `python3 tests/governance-docs.py` | 11 个场景通过 |
| `git diff --check` | 通过 |
| `docker image inspect qemux/qemu:7.50 --format '{{.Id}}'` | 未能检查；当前 Colima Docker socket 不存在，生产 runtime CA bundle 未获镜像级验证 |

以上为 macOS arm64 / zsh 宿主上的本地合成验证；不构成 DSM L2、KVM L3 或镜像运行验收。
