# ARC 上游源码与 DockDSM overlay

`vendor/arc` 是指向 [AuxXxilium/arc](https://github.com/AuxXxilium/arc) 的 Git submodule，固定在上游 `main` 的快照 `99195dbdf4e0a21c5304ddb06e07dc57419679bc`（ARC 4.1.2）。ARC 的源码历史由上游维护；DockDSM 的修改单独放在 `patches/arc/`，避免把改动误写进 ARC 上游或 DockDSM 的 MIT 来源树。

在 Windows + WSL 的 bash 环境中初始化并应用研究补丁：

```bash
git submodule update --init --recursive vendor/arc
bash research/arc/apply-patches.sh
```

`patches/arc/` 保存按序幂等应用的研究 overlay：`0001` 为型号选择器增加架构列，受限列表按 host arch 筛选，“Show all” 选择不匹配架构时显示警告，并在 ARM64 上检查 `/proc/cpuinfo` 的 `Features`；既有配置缺省 `x86_64`。`0002` 为 GRUB 菜单增加 ARM64 `Image-*` 路径、可选板级串口/内核参数，并把可见引导菜单品牌改为 DockDSM；`0003` 为 `arm64-efi` 指定 AArch64 交叉工具链，并在 FAT 启动分区的 MBR 表中设置 EFI 类型（`0xef`），x86 默认分区保持原值；`0004` 将运行时标题、启动横幅和操作界面改为 DockDSM，保留 ARC 来源标注、内部配置键与上游 API 标识；`0005` 把 `arm64-efi` 加入内嵌 GRUB 镜像的生成工作流；`0006` 把 ARM64 EFI GRUB 模块纳入更新包。

当前 ARC 配置表仍没有 ARM 型号；ARM 镜像还需提供 `/Image-${system_version}`、ARM64 Buildroot kernel/userspace、DSM kernel/initrd 和目标板 `grubenv` 参数。GRUB 工作流补丁只覆盖 EFI GRUB 程序的编译与打包，不会生成 ARC ARM runtime、DSM model/PAT，也没有完成 ARM kexec 验收。应用后 `vendor/arc` 工作树会显示本地修改，重置该 submodule 可还原上游快照。

ARC 不会随 DockDSM 镜像构建或发布；本目录只提供固定源码入口和隔离 overlay。上游 README 声明禁止商业使用，仓库 `LICENSE` 标记 GPL-3.0，部分源文件另有 MIT 头部。各声明存在适用范围不一致，必须在捆绑源码、构建产物或发布 ARC profile 前审清；该集成不构成许可证意见或商业使用授权。DSM/PAT 使用限制也独立适用。当前仅验证补丁对固定源码的应用及静态检查，不代表 ARC DSM 启动已验收。
