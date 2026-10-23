# DockDSM Bootloader 源码接管与构建门禁

本文件记录源码接管范围、固定输入和迁移依据；当前执行状态见 [CONTEXT](../CONTEXT.md)，产品阶段见[实施计划](implementation-plan.md)，长期选择见 [ADR 0009](ADR/0009-owned-bootloader-source.md)。不构成法律意见或分发许可。

## 固定源码与可重复审计

审计禁止 lazy fetch 和 Git transports；partial clone 缺失对象时失败，不自动补齐下载。读取的是固定 Git objects，工作树 overlay 不替代原始证据。

采用 AuxXxilium/arc commit `99195dbdf4e0a21c5304ddb06e07dc57419679bc`，Git tree `fd34c2ca01dc6f97a81dbd462d421396e3606928`。源码证据、SHA256、条目数和未锁定依赖由 [source-lock.json](../research/bootloader/source-lock.json)维护，避免复制一份哈希表。

```bash
python3 scripts/audit-bootloader-source.py --source vendor/arc
python3 tests/bootloader-source-audit.py
```

审计只读取固定 Git objects，不执行上游脚本、不复制源码、不下载、不改工作树；HEAD/tree/文件数/大小和证据哈希不匹配即失败。即使工作树已应用研究 overlay，也从固定原始 blob 验证许可证。JSON 中 local_history/local_storage 只描述所选 clone；shallow 不能代表完整上游历史。输出不包含 Git remote 凭据或完整 Git stderr。

## 规模与维护方式

固定快照有 76 条目、22,988,687 bytes；`grub.img.gz` 12,065,296 bytes、`sshx` 7,263,008 bytes、`genArc` 2,355,384 bytes，另有 kpatch、memtest 和压缩 kernel 模板。这不是纯 Shell 源码树。所查本地 clone 的 pack 为约 1.69 GiB，且 shallow 可达提交数为 1；不能据此断言完整历史只有一个提交，或宣称已完成全历史审计。GitHub repository size 元数据也不是固定快照大小。

| 方案 | 判断 | 条件与回退 |
| --- | --- | --- |
| Monorepo + subtree squash | 接管可构建源码闭包的优先方案 | 记录上游 commit/tree 与原始来源；独立维护，可按清单人工导入后续更新。squash 控制历史体积，但不会自动剔除二进制；合并前完成逐组件准入 |
| 全历史 subtree | 暂不采用 | 当前 clone 不完整且对象库大；需独立完整历史和 blob 审计，不能凭一次 shallow clone 估算维护成本 |
| 可审计 vendored snapshot | 允许作为备选 | 仅导入经准入的源码、许可证/NOTICE、上游路径映射和逐文件清单，保留修改归属；需说明为何比 subtree 更易控制内容 |
| 现有 submodule | 准入关闭前保留的研究入口 | 不作为最终自主维护架构；固定提交与 overlay 可回退，生产路径不依赖它 |

目前不执行整体 subtree 导入：已知混合许可范围、预编译来源与构建闭包尚未确认。避免先把所有二进制复制进主库，再将来源和许可补成事后手续。未来 `vendor/bootloader/` 直接可编辑；`patches/bootloader/` 仅保留外部组件补丁，不以无限 overlay 代替源码所有权。

## 构建链与供应链发现

| 输入/入口 | 固定源码可见事实 | 接管前必须解决 |
| --- | --- | --- |
| `img-gen.sh` | 开头执行 `sudo git clean -fdx`；使用 loop device、固定 `/tmp/p1`/`p3` mount 和递归删除；从 gzip disk seed 生成镜像 | 不在用户工作树运行；重写为隔离构建目录、明确资源归属、可中断清理和不接触现有盘的产物生成 |
| `scripts/functions.sh` | Buildroot kernel/initrd 来自 `arc-buildroot-essential` / `arc-buildroot-evo` release；addons/modules/configs/patches/custom/LKM/theme 同样选择浮动 release | 获取真实源码及 toolchain、固定 commit、资产 SHA256 与依赖闭包；下载 release 不是从源码构建 Buildroot |
| 同一下载辅助函数 | 部分 `curl -k` 关闭 TLS 校验，release 版本选择与产物哈希未在本仓库锁定 | DockDSM 下载器强制 TLS 和摘要校验，断网/错误摘要失败；不继承上游 token/自动发布脚本 |
| `.github/workflows/build.yml` | checkout 使用 `@main`，工具下载 `latest`，构建时间参与产物 | 不复制为 DockDSM workflow；复用本仓库固定 Actions/digest 与人工发布门禁，定义可复现时间输入 |
| `scripts/grub.sh` / `grub.img.gz` | GRUB 下载默认版本但无独立摘要；源码脚本存在不证明预编译 disk seed 可重建 | 审核 GRUB 源码/修改、toolchain、EFI/BIOS 模块与 disk seed 来源，生成自己的可校验 boot image |
| runtime update/menu | 内置上游 release URL；README 宣传 serial/MAC 生成与服务 patch 选项 | 自主版本和更新渠道；任何移植清单排除序列号生成、授权绕过与服务解锁功能；仅静态审查，不执行这些功能 |

仅固定 arc 主仓库无法宣称独立维护 Buildroot、modules、addons 或可重复镜像。未取得的组件源码与版本继续列在 lock 的 unlocked_dependencies 中，不能用猜测填充。

## 许可证与分发准入

| 对象 | 已读声明 | 门禁 |
| --- | --- | --- |
| DockDSM 既有代码 | [MIT](../license.md)、原作者归属和 [PROVENANCE](PROVENANCE.md) | 保留原有条款；新名称不重新许可第三方组件 |
| arc 根 LICENSE | GPL version 3 文本 | 须明确适用组件、修改与源码交付义务；不能直接把整树标为 DockDSM MIT |
| 同提交 README | 明确禁止商业使用，DSM 独立版权 | 与根 LICENSE/文件头适用关系待权利人或合格审查确认；当前阻断争议组合分发 |
| 个别 Shell/workflow 文件 | MIT 文件头同时指向根 `/LICENSE` | 文件级声明记录保留，不能自行推定根许可证已被其覆盖 |
| Buildroot/GRUB/kernel/modules/addons/二进制 | 当前主仓库没有完整对应源码和逐组件许可闭包 | 获取版本、源码、补丁、构建说明、许可证与 NOTICE；二进制不因在 Git 中就取得再分发许可 |
| DSM/PAT | 独立的 Synology 权利及使用条件 | 不提交、不捆绑专有系统镜像；测试使用用户合法取得的精确输入和独立空卷 |

本地读取公开源码、静态审计和离线合成测试可以继续。组合产物发布、整体搬入有争议内容、商业授权结论和真实 DSM 安装不能由本审计自动放行。阻断和关闭证据统一见 [RISK-006](RISK_REGISTER.md#risk-006p1arc-集成尚无运行与许可边界证据)。

## 下一工作包的准入

先确认许可证范围与各预编译 blob 的可重建源码，建立 Buildroot/GRUB/模块依赖的固定输入清单，再在独立 PR 导入准入源码。之后才实现 DockDSM 品牌和 provider 接口；运行时用 `full-x86_64` / `full-arm64` 中立命名，旧 `virtualdsm` / `rtd1619b` 保留。ARM64 loader 研究等待 x86 工作链验收，已有 direct boot 证据不转移。
