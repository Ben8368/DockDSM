# ADR 0009：统一 DockDSM Bootloader 与受控源码接管

- 状态：已接受
- 日期：2026-10-23
- supersedes：[ADR 0006](0006-runtime-profiles-and-container-first.md) 中性能先行作为所有源码接管工作的前置顺序、ARC 的长期独立功能身份和仅作为可选外部源码的维护方式。其旧平台兼容、Profile/Runtime 分层、容器优先、证据和数据隔离决定继续有效。

## 背景

维护者要求在 PR #19 合并后推进自主维护的统一 DockDSM 产品，最终由一个容器内的一个 QEMU VM 通过自有 Bootloader 引导 DSM。固定上游主仓库包含预编译文件及动态下载，不等于获得独立源码构建闭包。许可适用范围仍有阻断，具体证据见[源码审计](../bootloader-source-audit.md)。

## 决策

1. 产品与自有引导器身份为 DockDSM / DockDSM Bootloader；Arc 只作为第三方来源记录。保留作者、许可证、NOTICE、原路径映射及兼容所需的组件标识，不暗示继承代码均为原创。
2. 目标为 monorepo 中直接维护引导器源码，优先对经准入的可构建源码使用 subtree squash，并固定 commit/tree；若选择性 vendored snapshot 更适合排除来源不明的二进制，须有逐文件映射、摘要和选择理由。不得直接导入整个对象库或所有预编译文件。
3. PR #19 的 submodule 是临时研究入口。在组件许可、二进制来源及构建闭包关闭前保留它，不整体迁移、不捆绑争议组合产物。审计工具只读取固定 Git objects，不执行上游危险构建脚本。
4. 顺序改为 Phase 0 修复/合并 → Phase 1 源码准入与接管 → Phase 2 品牌与接口 → Phase 3 x86 Bootloader 构建及运行验收 → Phase 4 ARM64 Bootloader。缺少设备允许静态与合成工作；不能把阶段设计或构建通过提升为产品验收。
5. 保留 `DSM_PLATFORM=virtualdsm`、`rtd1619b`；新接口计划用 `full-x86_64`、未来 `full-arm64`，在实现及测试前不加入生产白名单。host/container/guest/DSM model/bootloader 架构分别记录。
6. 单容器管理单 QEMU VM；同一 VM 内 Bootloader 向 DSM 内核交接，不创建第二台嵌套 QEMU。loader 状态、DSM 数据盘、管理面和就绪证据分别隔离。新 profile 不接管旧盘，不扩大容器特权或默认远程端口。
7. 不迁入序列号伪造、授权绕过或服务解锁功能。x86 验收前不启动 ARM64 loader 移植，既有 DS124 direct boot 不受此目标阻塞。

## 后果

可以在既有性能和硬件基线未完成时推进安全的源码审计、接口静态工作，但实际执行路径切换仍受兼容、存储、冷启动、干净关机和硬件门禁约束。许可准入未关闭时源码迁移可以被阻断；自主维护目标不是发布争议组合的授权。

后续 PR 由维护者审查合并；本次仅授权合并 PR #19，不授权后续自动合并或正式镜像发布。

## 替代方案

- 永久依赖 submodule + overlay：难以直接维护 Buildroot 与引导源码，不符合自主维护目标。
- 全历史 subtree：shallow 本地证据不足，存储体量与二进制来源不明，不采用为首步。
- 两个 Docker 镜像 Compose 拼装：不形成统一源码或构建流程，不采用。
- 全平台立即替换引导链：ARM64 交接尚未实现且旧数据有风险，不采用。

## 关联文档

[源码接管审计](../bootloader-source-audit.md)、[来源](../PROVENANCE.md)、[实施计划](../implementation-plan.md)、[运行架构](../runtime-architecture.md)、[风险](../RISK_REGISTER.md)。
