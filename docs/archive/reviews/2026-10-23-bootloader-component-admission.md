# Phase 1：组件来源与离线准入验证记录

## 基线与范围

- 2026-10-23（Asia/Shanghai）：先 `git fetch origin master`，`gh pr view 20 --json state,mergedAt,mergeCommit` 确认 MERGED，合并时间 `2026-10-23T08:13:26Z`。本轮 origin/master 为 `fcc7330b81ba597699804cd42f9a59c28bb9dbe1`，从其新建 `codex/bootloader-component-admission`，不使用已合并分支。
- 实际宿主 Windows 10.0.26200 / AMD64，PowerShell 7.6.5，Git 2.53.0.windows.2，Python 3.14.2（使用原生 `python`；`python3` launcher 不提供可用版本输出），gh 2.92.0；PATH 中无原生 Docker。后续为复核旧 Shell 回归实际探测到 WSL Ubuntu 24.04 / Linux x86_64、Python 3.12.3、Git 2.43.0、Docker CLI 29.9.0 且 daemon 可访问；明确区分原生与 WSL，不把它计为真实 DSM 验收。
- 原工作树仅未跟踪 `vendor/`，切换后成为现有 gitlink；`vendor/arc` HEAD 与 source-lock 匹配且干净。保留既有研究基线，不下载、不替换；临时报告可读，仅作线索，所有采纳结论重新从对象/API 核查。
- 仅新增组件证据、门禁、夹具/CI 与必要文档。不导入完整引导器源码，不执行上游 img-gen/Taskfile/构建，不提交 release 资产、PAT、镜像、序列号或密钥，不改生产 Dockerfile/默认启动链。

## 证据方法与结论边界

正式 16 项一对一映射、完整组件状态和下一行动只维护于 [manifest](../../../research/bootloader/component-manifest.json)。本记录不复制另一套状态矩阵。主锁未修改：其 commit/tree/已有哈希继续为唯一事实。远端检查 commit/tree、tags、release 元数据、选定文本和查询结果只保存在[收据](../../../research/bootloader/evidence/github-observations-2026-10-23.json)，原始路径/模式/OID/大小的完整 tree 在[索引](../../../research/bootloader/evidence/remote-trees-2026-10-23.json)。

通过 `gh api repos/AuxXxilium/<repo>`、`commits/<default_branch>`、`git/trees/<完整 commit>?recursive=1`、`git/blobs/<oid>`、`tags?per_page=5`、`releases?per_page=2` 只读采集；branch 先解析完整 commit，再读固定 tree/blob。七棵 tree 均未截断。离线重建目录 tree 对象 SHA-1，文本校验 Git blob OID/SHA256/bytes；没有下载 release 资产或递归取得源码 blobs。完整 metadata 不等于完整源码。

### Buildroot Essential / Evo

分别重复认证仓库/tags/releases API、匿名 API 与公开 HTML，共每仓库五个入口均 404；同会话七个可访问组件 API 成功，说明不能将问题笼统归因于整个 GitHub 网络不可用。owner 范围公开 buildroot 搜索无结果；这不是所有历史、改名或私有仓库的穷举。404 本身不区分私有/删除/迁移/调用者权限，不能认定仓库不存在，也没有证实有效重定向。没有遇到可作为本次失败解释的限流响应；不能据此推断无限访问权限。

固定下载器实际将 `apex` 映射 Essential、`evo` 映射 Evo，并调用浮动 release tag。缺源码版本、defconfig、external tree、kernel/initrd config、patches、toolchain 和源码-资产关系；不能以 release 可下载代替这些证据。下一行动是请求维护者提供合法可访问源码或对应源码归档与完整构建材料。

### GRUB / disk seed

固定 `scripts/grub.sh` 的默认字符串是 `grub-2.14`，目标为 `i386-pc i386-efi x86_64-efi`，从 GNU FTP tar.gz 使用 `curl -k` 获取，无摘要。配方覆盖 `extra_deps.lst`，裁剪 locale/theme，引入宿主 unicode.pf2 和未锁定编译/磁盘工具；不能据此认证 tarball、具体编译器或既有 seed。没有执行任何 loop/mount/格式化。`SynoBootLoader.efi` 是零字节占位，不是有效 EFI 引导器。seed 与所有现有程序/两份压缩 kernel 模板仅从固定对象只读取哈希，没有解包或执行。

### LKM / Custom / Modules

LKM 完整 tree 只有 4 条目/3 blobs，README 表示发布 builds，无实现源码；tag 指向同一说明提交不能认证 rp-lkms.zip 的对应源码。Custom 完整 tree 6 条目/4 blobs，无 kernel 源码/config/patch，workflow 只 zip 外部 `*.tgz/*.gz`；README 的 5.10.55 声明不是已验证 ABI。

Modules tree 有 18,028 个 `.ko`，还有 firmware，没有 C/H 或 `src/`。compile workflow 引用缺失的 `src/`，并动态获取 pkgscripts-ng/SDK；build workflow 浮动 clone linux-firmware。`.gitmodules` 声明历史 igc 路径与仓库，但 tree 没有该 gitlink/源码，不能认为子模块已交付。每个模块仍需源码/config/vermagic/SDK/compiler 与许可关联，firmware 许可独立。

### 其他程序与材料

`genArc`、`sshx`、`kpatch`、`memtest` 的固定 bytes/哈希不认证名称所暗示的任何外部项目；没有猜测同名程序版本或许可。genArc/授权绕过/服务解锁不进入迁入 allowlist。Addons 混有 tgz/库/程序，eudev 编译容器只有 tag；Configs 动态获取 arc-dsm/new/data.yml 并包含须排除的 serials 文件；Patches 需逐目标/功能/权利审查；Theme 的字体与图稿需要独立权利及生成关联。

### 许可与门禁

既有 DockDSM MIT 不覆盖整个第三方树；根 GPLv3、README 非商业文字、MIT 文件头及其 `/LICENSE` 引用范围待有权主体/合格审查澄清。Buildroot/GRUB/Linux/模块/工具/字体/固件的声明与对应源码义务逐项处理，DSM/PAT 独立；未推定已授权。工具只校验固定事实、收据与技术 gate，不签发法律许可，不验证 reviewer 身份签名；同时伪造全部材料的写权限攻击需要人工审查/后续签名制度，不可由 SHA 校验解决。

三个 gate 分开：source_import 需要完整本地固定源码及范围/许可/权利证据；combined_build 还需固定工具链、无未锁依赖及重建关联；distribution 还需分发审查与主锁允许。手填 APPROVED 或 verified+LICENSE 不能通过，真实批准需组件/condition/identity/input 绑定的独立收据。严格模式没有例外绕过开关。

## 同日重复请求复核与门禁加固

- 再次 `git fetch origin master` 和查询 PR #20，确认 master 未变。接续时工作树干净，已有同范围的开放 PR #21（不是已合并旧分支），其 merge-base 正是已确认 master；复用这一独立 PR，不创建重复或 stacked PR，不改写既有提交。
- 重新只读查询主仓库及七个组件的固定 `/git/commits/<sha>`：返回 commit/tree 全部吻合原锁/收据。Essential/Evo 各重查已配置 gh 会话的仓库/tags/releases 及匿名 API/Web，仍均为 404；公开 owner 目录 40 仓库无 buildroot 名称匹配。新[复核收据](../../../research/bootloader/evidence/github-revalidation-2026-10-23.json)以文件摘要/JSON pointer 引用原事实源，不维护第二套组件状态，也不声称排除私有/迁移/权限可能。
- 发现并复现原门禁的四类证据绑定缺口：以 LICENSE 摘要冒充其他产物、本地文件冒充固定 Git 产物、两条 verified 收据互相引用、不同 owner 同名仓库冒充不可访问来源。四个新增用例修复前均因未拒绝伪证据而失败，修复后通过；另补重复/越界产物路径、零字节占位晋级用例。
- 门禁现将每个固定产物绑定到同路径 Git blob 与已有摘要/大小，并拒绝重复路径、空占位晋级和 verified 收据输入环；unresolved 来源必须精确匹配观测 URL，不只比较仓库末段。没有调整状态或放宽 strict，没有改变可信 Git reader 或生产路径。
- 原生 Windows 全量 35 tests、WSL 全量及 `unshare -Urn` 无网络 namespace 全量 35 tests 通过。实库 `--check`=0 / `--strict`=2，三个 gate 均无获准组件。Windows 首次辅助 JSON 捕获因子进程默认 GBK、父进程按 UTF-8 解码失败；显式 `-X utf8`/`PYTHONUTF8=1` 后复测通过，无须修改工具或降级检查。

## 🚦 Audit Report

**总体评价：🟡 可通行（仅本工作包；迁移/组合构建/分发保持阻断）**

**1. 🔴 阻断项：** 不存在生产/数据路径改动；组件自身阻断保留，RISK-006 不关闭。

**2. 🟡 跟进项：** 权利范围、缺失对应源码、工具链/依赖/产物关联见 manifest 与 RISK-006。任何证据哈希/版本不符失败关闭。外部来源无法访问即交付阻断，不无限等待。

**3. 验证计划与结果：** 下表记录实际命令；离线夹具覆盖原用户数据/对象/config/index/mtime 不变、Git 环境污染、partial clone 缺对象不 lazy fetch、链接/路径越界、未知状态、缺字段/重复 ID/键、错误摘要和逐条件撤销的 mutation。CI 只在现有两架构合成 job 追加轻量回归，没有减弱原镜像/门禁。

| 命令（仓库根） | 结果 |
| --- | --- |
| `python tests/bootloader-component-admission.py` / WSL `python3 tests/bootloader-component-admission.py` | 复核加固后 35 tests，Windows/WSL 均完整通过 |
| `python tests/bootloader-source-audit.py` | 11 tests 通过 |
| `python scripts/check-bootloader-admission.py --check` | exit 0；如实报告阻断 |
| `python scripts/check-bootloader-admission.py --strict` | exit 2，预期拒绝；非回归失败 |
| WSL `unshare -Urn env PYTHONDONTWRITEBYTECODE=1 python3 tests/bootloader-component-admission.py` | 独立无网络 namespace 中全部通过 |
| `python scripts/governance-docs-check.py` / `python tests/governance-docs.py` | 通过 |
| `python tests/ci-policy.py` / `python tests/branding.py` | 最终 21 / 5 tests 通过 |
| `python scripts/check-config.py` / `python scripts/check-tree.py` / `git diff --check` | 通过（包含暂存新增文件） |
| `python scripts/install-git-hooks.py` / `python scripts/git-hooks-test.py` | hook 已启用；Codex/Cursor/Claude/Jules/human 五类通过 |
| WSL `python3 tests/arc-overlay.py` | 8 tests 通过；只对临时夹具应用补丁 |
| WSL `bash research/arm64/tests/smoke.sh` | 通过；假 QEMU/合成参数不是真机证据 |

补充异常记录：原生 `python tests/arc-overlay.py` 首次及 UTF-8 复测均失败（8 errors），因为 Windows 的 `bash` 指向 WSL，警告为 UTF-16 且脚本路径是 Windows 格式；确认 WSL 后在 Linux 路径下复测通过，未为此修改旧脚本或放宽测试。PowerShell 截断 JSON 管道的首轮 `$LASTEXITCODE` 不可靠，后改用 `subprocess.run` 直接捕获，确定 strict=2。

未运行：真实第三方重建、DSM 冷启动/存储/设备/KVM、Docker 双架构镜像。这些不属于本工作包；CI 的双架构和镜像结果另由远端实际运行确认，不以本地门禁代替。无自动合并、镜像发布或分支保护变更。

## 后续工作与回退

目前没有合法可立即迁移的组件。最小下一包是**缺失来源与许可确认的证据收集**；候选的、不含 serials/动态 data 的平台配置 allowlist 也必须先获准，不能先搬源码再补许可。GRUB 隔离生成器、真实源码迁移、品牌接口和后续 x86/ARM64 均另行授权和验收。撤回本工作包提交即可回到 PR #20 门禁，不影响现有生产数据或研究 submodule。
