# Docker Desktop（RyzenHV 0.7.9-compat.1）

macOS 自带的 Hypervisor.framework 只支持 Intel VT-x 和苹果芯片，所以 AMD 机器上 `kern.hv_support` 是 0，Docker、UTM、Parallels 这些都跑不起来。[RyzenHV 修改版](https://github.com/lorzzn/ryzen-hypervisor.framework) 是一个 kext，它用 AMD SVM 实现了这个框架，补上了这块。

这是实验项目。在这台 300U（Zen+）上，此前 0.7.8-compat.1 已验证 hello-world、长时间运行的容器、4 vCPU / 6 GB 内存、驱动独立初始化和 Docker 目录共享。当前 0.7.9-compat.1 包含上游 0.7.9-beta，已通过构建和回归测试，尚待实机启动验证。

## 1. EFI（已经包含在默认 config 里）

- `RyzenHV.kext` 放在 Kernel › Add 的最后，`Arch = Any`
- boot-args `rhv_enable_svm=1 rhv_allow_users=1 amfi_get_out_of_my_way=0x1 rhv_hv=1 rhv_hv_sysctl=1 rhv_selftest=1 ipc_control_port_options=0`
  - `rhv_hv=1`：native 模式。kext 直接替代 AppleHV，Docker.app 的文件一个都不用改
  - `rhv_hv_sysctl=1` 让驱动在启动时初始化 `kern.hv_support`
- **`csr-active-config = 03080000`**（SIP 部分关闭）。这是 Docker 需要的最低值；默认 config 用的是 `430A0000`，它包含 `03080000` 的全部位，是 NootedRed 修改版推荐的值

### 为什么要关 SIP

kext 会在 HyperKit 运行时，改掉它内存里两处判断 CPU 是不是 Intel 的代码（vendor check 和 verify_gla）。改过的内存页和签名对不上，所以必须让 AMFI 不检查签名，靠的是 `amfi_get_out_of_my_way=0x1`。但 **SIP 全开时 macOS 会忽略这个参数**，结果就是：

```
client fix-ups: signing flags of com.docker.hyperkit: ..., enforcement ON, hard on, kill on
CODE SIGNING: process ...[com.docker.hyper]: rejecting invalid page ...
```

HyperKit 被系统杀掉，Docker 报 "unable to start"。参考 RyzenHV 的 issue #10。SIP 改成 `03080000` 后，日志变成 `enforcement off`，HyperKit 就能正常运行。

`ipc_control_port_options=0` 是为了绕开 SIP 放宽后 Firefox 这类程序出的问题，参考 issue #13。

**代价**：SIP 部分关闭，而且 AMFI 对**所有进程**都不再检查签名，系统的安全性会明显下降。RyzenHV 的 PR #16（把补丁打到磁盘文件上再重新签名）合并之后，应该可以把 SIP 恢复全开。

## 2. RyzenHV 工具

固定发布地址为 [v0.7.9-compat.1](https://github.com/lorzzn/ryzen-hypervisor.framework/releases/tag/v0.7.9-compat.1)。CI 发布完成后，可下载 [完整 tar.gz 包](https://github.com/lorzzn/ryzen-hypervisor.framework/releases/download/v0.7.9-compat.1/ryzenhv-0.7.9-compat.1-macos-x86_64.tar.gz)及其 [SHA256 校验文件](https://github.com/lorzzn/ryzen-hypervisor.framework/releases/download/v0.7.9-compat.1/ryzenhv-0.7.9-compat.1-macos-x86_64.tar.gz.sha256)。

包内驱动版本为 `0.7.9d1`，对应源码提交 `430b15e46b351d0510ffed965fbe603387b9dcc5`。EFI 中的驱动来自该提交的本地构建，CI 使用同一提交打包。解压后执行下面的命令。

```
xattr -dr com.apple.quarantine .
./rhv doctor                       # 应该显示 All good
./bin/rhv-info                     # 开机时只显示 "SVM ... active on 1"
./bin/rhv-info hv rescan           # 补齐到 4/4（第一次创建虚拟机时 kext 也会自动扫描）
./bin/rhv-info selftest            # 应该显示 4 of 4 CPUs ok
sysctl kern.hv_support             # 驱动启动初始化后应为 1
```

## 3. Docker Desktop 4.97.0（build 244584，Intel 版）

```
RHV_YES=1 ./rhv docker-desktop get   # 会从 desktop.docker.com 下载，国内可能连不上，可以手动下载后放到 ~/.ryzenhv/dl/Docker-244584.dmg
./rhv docker-desktop                 # native 模式下只会把 UseVirtualizationFramework 设成 false
```

上游 0.7.9-beta 已修复 Docker 设置文件缺失或为空时的配置失败，当前版本包含此修复。

推荐在 `settings-store.json` 里加上这些设置：

| 键 | 值 | 原因 |
|---|---|---|
| `UseVirtualizationFramework` | `false` | 用 HyperKit 引擎 |
| `UseResourceSaver` | `false` | 空闲时 Resource Saver 会停掉 HyperKit，但留下 `hyperkit.pid`。下次启动时报 `Failed to set up pidfile`，直接退出 |
| `AutoDownloadUpdates` | `false` | 其他版本的 HyperKit 不一定能被补丁识别 |
| `AutoStart` | `false` | 使用下面的登录任务，等待默认 socket 链接就绪后启动 |
| `MemoryMiB` / `Cpus` | `6144` / `4` | |

首次安装系统集成时，Docker 可能请求管理员授权。如果每次开机都为 `set-docker-socket` 弹出密码框，可使用下面的启动顺序。

### 等待默认 socket 链接后启动

Docker 官方的 `com.docker.socket` LaunchDaemon 在开机时创建
`/var/run/docker.sock -> ~/.docker/run/docker.sock`。这台机器上曾出现 Docker
先检查到链接缺失、再请求管理员授权重新配置的情况。

在 Docker 的 General 设置中关闭 **Start Docker Desktop when you sign in to your computer**，
并在 Advanced 设置中开启 **Allow the default Docker socket to be used**。然后安装登录任务。

```sh
mkdir -p ~/.hackintosh ~/Library/LaunchAgents
cp scripts/docker-autostart.sh ~/.hackintosh/
cp scripts/local.hackintosh.docker-autostart.plist ~/Library/LaunchAgents/
sed -i '' "s|__HOME__|$HOME|g" ~/Library/LaunchAgents/local.hackintosh.docker-autostart.plist
plutil -lint ~/Library/LaunchAgents/local.hackintosh.docker-autostart.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/local.hackintosh.docker-autostart.plist
```

更新已经加载的同名任务时，先执行
`launchctl bootout gui/$(id -u)/local.hackintosh.docker-autostart`，
再重新执行上面的安装命令。

任务每两秒检查链接本身及其目标路径。正确的链接即使暂时没有实际 socket 也可通过，
实际 socket 会在 Docker 启动后创建。等待时每分钟记录一次日志，启动 Docker 后任务退出。
打开 Docker 失败时，launchd 按失败退出策略重试。

日志位于 `~/.hackintosh/docker-autostart.log`。脚本可通过
`DOCKER_SOCKET_LINK` 指定检查路径，回归测试使用临时路径隔离运行。
测试命令为 `python3 -m unittest discover -s tests -v`，在 macOS 上执行。

回退时执行下面的命令，然后在 Docker 的 General 设置中重新开启自带的登录启动选项。

```sh
launchctl bootout gui/$(id -u)/local.hackintosh.docker-autostart
rm "$HOME/Library/LaunchAgents/local.hackintosh.docker-autostart.plist"
```

冷启动后是否消除授权弹窗，需要实际重启验证。

### 虚拟化初始化、PID 恢复与目录共享

`rhv_hv_sysctl=1` 让驱动在启动时设置 `kern.hv_support=1`。驱动为 HyperKit 安装私有兼容钩子，通过生命周期锁安全回收过期 PID 文件，并通过 fileserver FD 交接处理目录共享及路径别名。

此前 0.7.8-compat.1 已在移除 `com.overlorddev.ryzenhv.hvsysctl` 和 `local.hackintosh.hyperkit-pid-clean` 两个旧任务后，验证独立开机初始化、目录双向读写、中文与空格路径、原子替换及只读挂载。旧 PID 清理脚本和对应 LaunchAgent 已从仓库移除。

## 4. 关闭系统睡眠（必须）

睡眠时 kext 会关掉 SVM，正在运行的 HyperKit 会因此崩溃（`VmRun: SVM was turned off under us`，SIGABRT）。macOS 本身睡眠唤醒都正常，网卡、蓝牙、RyzenHV 也都能恢复，但 Docker 不行。

```
sudo pmset -a sleep 0 disksleep 0 standby 0 powernap 0 hibernatemode 0 autopoweroff 0
sudo pmset -a displaysleep 10
```

## 5. 国内拉镜像

macOS 直连 `registry-1.docker.io` 会超时。在 `~/.docker/daemon.json` 里加上镜像源（用的是第三方服务，自己判断能不能信任）：

```json
{ "registry-mirrors": ["https://docker.m.daocloud.io", "https://docker.1ms.run"] }
```

## 6. 无人值守开机

如果要求断电重启后自动恢复服务，需要：
- 开启自动登录（FileVault 必须是关的）。注意自动登录的密码是以简单混淆的方式存在 `/etc/kcpassword` 里的。
- Docker 设置 `AutoStart=false`，安装上面的等待 socket 链接登录任务。

## 回退

使用 `extras/config-no-ryzenhv.plist`，SIP 为 `00000000`。换掉 config 后删掉 `Kexts/RyzenHV.kext`。从旧版迁移且仍装有 hvsysctl 服务时，可在旧版工具包中执行 `sudo ./libexec/hv-sysctl-daemon.sh remove`。
