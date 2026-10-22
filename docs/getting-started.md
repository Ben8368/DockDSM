# DockDSM 部署指南

本指南覆盖**当前已有**的 Virtual DSM / DS124 路径，不是 ARC 安装手册。ARC 计划见 [路线](arc-integration.md)。

## 1. 准备环境

- Linux Docker Engine 与 Compose v2；构建需访问基础镜像、Debian 源、QEMU 和构建工具来源。
- Docker 容器与 guest CPU 架构分开确认；KVM 只加速同架构 guest，且需要宿主允许虚拟化、设备权限和必要的嵌套虚拟化。
- 预留独立存储目录。确认 DSM EULA、硬件及使用条件；勿把实际凭据、PAT、磁盘或日志提交到仓库。

## 2. 本地构建与默认 x86

以下命令在仓库根目录的 Linux shell 执行：

```bash
docker compose -f compose.local.yml config
docker compose -f compose.local.yml build
docker compose -f compose.local.yml up -d
docker compose -f compose.local.yml logs -f
```

配置默认 `DSM_PLATFORM=virtualdsm`、`KVM=N`、`NETWORK=user`，使用 TCG，不请求特权设备；镜像本地标签仍为 `virtual-dsm:local`，这只是兼容性内部标识，不是上游镜像。管理端口绑定 `127.0.0.1:5000/5001`，SSH 转发端口为 `5022`，但转发不代表 DSM 已启用 SSH。

系统文件准备完成后，从 [HTTP 管理页](http://127.0.0.1:5000) 或 [HTTPS 管理页](https://127.0.0.1:5001)继续 DSM 官方安装、建卷与账户配置。

## 3. 选择实验性 DS124 ARM64

先阅读 [精确 PAT 准备要求](arm64-auto-install.md)，再使用一个**全新且不含现有数据**的目录：

```bash
DSM_PLATFORM=rtd1619b DSM_STORAGE=./storage-ds124 docker compose -f compose.local.yml build
DSM_PLATFORM=rtd1619b DSM_STORAGE=./storage-ds124 docker compose -f compose.local.yml up -d
DSM_PLATFORM=rtd1619b DSM_STORAGE=./storage-ds124 docker compose -f compose.local.yml logs -f
```

仅支持文档指定的 DS124 DSM 7.2.2-72806 官方 PAT 和 SHA256。不要为同一目录在 `virtualdsm` / `rtd1619b` 间切换。amd64 宿主模拟 ARM64 使用 TCG，启动可能很慢。已存在的 DS124 运行盘不自动替换；单盘、网络、关机与升级限制见 [platforms](platforms.md)。

## 4. 显式启用 KVM

仅在宿主与 guest 架构匹配、`/dev/kvm` 存在且容器具有权限时使用。将以下内容保存为仓库外或未跟踪的本地 override，并与 `compose.local.yml` 组合：

```yaml
services:
  dsm:
    environment:
      KVM: "Y"
    devices:
      - /dev/kvm:/dev/kvm
```

例如 `docker compose -f compose.local.yml -f /your/path/kvm.yml config`，复核后再 `up -d`。这不会为 x86 guest 在 ARM64 宿主上开启硬件加速；启动日志和实际 QEMU 加速器才是证据。不要用无必要的 `privileged: true` 代替设备/权限诊断。

## 5. 停止、更新与备份

1. 从 DSM UI 执行关机，确认 guest 退出；之后对同一套 Compose/环境变量执行 `docker compose -f compose.local.yml stop`。
2. 备份整个持久化目录与所用配置；保持 guest 平台、DSM 版本和旧目录不变。
3. 更新源码后重新 build，再以相同配置启动；镜像更新不等同于 DSM 升级。
4. 不删除旧盘“修复”安装问题；重装和 ARC PoC 使用新目录，恢复流程由备份验证。

`stop_grace_period` 超时后的强制退出属于非干净关机。CI 构建和 HTTP 200 不替代卷持久性、干净关机或包安装验收。

## 6. 注册表部署

`compose.yml`、`kubernetes.yml` 是未来/已发布镜像的部署模板；它们指向 `ghcr.io/ben8368/dockdsm:latest`。仓库改名和重建不会自动创建该包。先检查实际发布记录；发布前用本地构建。注册表模板的端口与权限也应按环境收紧，不能直接当作本地安全默认值。发布规则见 [CI / Publishing](ci.md#publishing)。
