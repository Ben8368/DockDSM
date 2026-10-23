# PR #19：gitlink 与研究 overlay 回归

日期：2026-10-23。范围为 PR #19 原有固定源码研究入口，不改变 submodule 方案、生产镜像、平台契约或发布许可。当前状态只见 [CONTEXT](../../../CONTEXT.md)。

## 复核与修复

审查基线 `8083d4cb07e9dfac98dc5aed2f505bd98c2251f4`，上游仍为 `99195dbdf4e0a21c5304ddb06e07dc57419679bc`。3 条 CodeRabbit 意见均有效：

- `scripts/check-tree.py` 根据 Git index mode `160000` 识别 gitlink；只排除子仓库入口，普通文件缺失、编码、LF、BOM 和尾随空白检查继续生效。
- `research/arc/apply-patches.sh` 验证 checkout 存在后，将 `ARC_DIR` 转为绝对路径，再解析 `.git` 和调用 Git。
- PR 模板链接 AI_RULES 的维护者书面例外，保留 CI success 门禁；本轮不使用例外。

回归先在修复前运行：tree 测试 2 项失败，相对路径 overlay 测试 2 项失败。修复后全部通过。新增 overlay 回归加入现有 CI，不修改范围路由、汇总判定或豁免。

## 环境与隔离

- Windows x64，Intel Core i7-10700，PowerShell 7.6.5；本机 PATH 无 Docker/QEMU 可执行文件。
- WSL Ubuntu 24.04，Linux `6.6.87.2-microsoft-standard-WSL2`，x86_64；Git 2.43.0、Python 3.12.3、Docker daemon 29.9.0、ShellCheck 可用。
- WSL 可见 `/dev/kvm`，未运行 KVM 初始化或 guest；不能据此确认硬件加速。宿主与 WSL 视图分别记录。
- 原 `C:/DockDSM` 的 master 分叉及未跟踪 vendor 保留；修改在独立 worktree，Linux 测试在 `/var/tmp/dockdsm-pr19-validation` 可丢弃 clone。
- 真实 overlay 仅对本地 Git objects 克隆出的固定源码副本应用；未运行上游构建脚本，未使用 DSM/PAT、生产磁盘或凭据。

## L0/L1 命令与结果

以下在 Linux 验证 clone 根目录执行，均通过：

```bash
python3 tests/arc-overlay.py                 # 8 项
python3 tests/ci-policy.py                   # 20 项
python3 scripts/governance-docs-check.py
python3 tests/governance-docs.py
python3 tests/branding.py                    # 5 项
python3 scripts/check-tree.py
python3 scripts/check-config.py
python3 scripts/git-hooks-test.py
python3 tests/bot-dispatch.py                # 12 项
mapfile -d '' scripts < <(git ls-files -z '*.sh')
for script in "${scripts[@]}"; do bash -n "$script"; done
shellcheck -x "${scripts[@]}"
bash research/arm64/tests/smoke.sh
bash tests/production-x86-command.sh
bash tests/qemu-patches.sh
git diff --check
git diff --cached --check
```

Windows 另执行 `python tests/ci-policy.py`（20 项）、治理、tree 和配置检查，通过。

真实上游源码副本的验证命令：

```bash
bash research/arc/apply-patches.sh vendor/arc
bash research/arc/apply-patches.sh "$PWD/vendor/arc"
bash -n vendor/arc/files/initrd/opt/arc/arc-functions.sh
git -C vendor/arc diff --check
python3 scripts/check-tree.py
```

首次应用成功，第二次报告 already applied；语法和 whitespace 通过。应用时存在 Git 文件 mode 警告，不影响补丁内容校验；研究脚本原有 `core.filemode=false` 保持不变。

未运行 L2 DSM 冷启动/安装/持久化，以及 L3 指定宿主加速/性能；Mac ARM64 和 RK3588 本轮未运行。远端 CI、CodeRabbit、threads 与合并证据以 [PR #19](https://github.com/Ben8368/DockDSM/pull/19) 最新 HEAD 为准，本地通过不能代替远端合并门禁。

此前的 CI/部署验证继续见 [2026-10-22 CI 记录](2026-10-22-ci-redesign.md)。
