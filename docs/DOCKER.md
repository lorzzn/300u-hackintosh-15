# Docker Desktop（RyzenHV 0.7.8）

macOS 自带的 Hypervisor.framework 只支持 Intel VT-x 和苹果芯片，所以 AMD 机器上 `kern.hv_support` 是 0，Docker、UTM、Parallels 这些都跑不起来。[RyzenHV](https://github.com/OverlordDev/ryzen-hypervisor.framework) 是一个 kext，它用 AMD SVM 实现了这个框架，补上了这块。

**它的状态**：实验项目，作者只在 Ryzen 7 5800H 上测试过。在这台 300U（Zen+）上，hello-world、长时间运行的容器、4 vCPU / 6 GB 内存都能跑。

## 1. EFI（已经包含在默认 config 里）

- `RyzenHV.kext` 放在 Kernel › Add 的最后，`Arch = Any`
- boot-args：`rhv_enable_svm=1 rhv_allow_users=1 amfi_get_out_of_my_way=0x1 rhv_hv=1 rhv_selftest=1 ipc_control_port_options=0`
  - `rhv_hv=1`：native 模式。kext 直接替代 AppleHV，Docker.app 的文件一个都不用改
- **`csr-active-config = 03080000`**（SIP 部分关闭）

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

从 release 页下载 `ryzenhv-0.7.8-macos-x86_64.tar.gz`，解压后执行：

```
xattr -dr com.apple.quarantine .
./rhv doctor                       # 应该显示 All good
./bin/rhv-info                     # 开机时只显示 "SVM ... active on 1"
./bin/rhv-info hv rescan           # 补齐到 4/4（第一次创建虚拟机时 kext 也会自动扫描）
./bin/rhv-info selftest            # 应该显示 4 of 4 CPUs ok
sudo ./libexec/hv-sysctl-daemon.sh install   # 每次开机自动把 kern.hv_support 设为 1，并清理过期的 hyperkit.pid
```

## 3. Docker Desktop 4.97.0（build 244584，Intel 版）

```
RHV_YES=1 ./rhv docker-desktop get   # 会从 desktop.docker.com 下载，国内可能连不上，可以手动下载后放到 ~/.ryzenhv/dl/Docker-244584.dmg
./rhv docker-desktop                 # native 模式下只会把 UseVirtualizationFramework 设成 false
```

0.7.8 有个 bug：如果 `~/Library/Group Containers/group.com.docker/settings-store.json` 还不存在，`rhv docker-desktop` 会报错。先手动写入下面的内容：

```json
{ "UseVirtualizationFramework": false }
```

推荐在 `settings-store.json` 里加上这些设置：

| 键 | 值 | 原因 |
|---|---|---|
| `UseVirtualizationFramework` | `false` | 用 HyperKit 引擎 |
| `UseResourceSaver` | `false` | 空闲时 Resource Saver 会停掉 HyperKit，但留下 `hyperkit.pid`。下次启动时报 `Failed to set up pidfile`，直接退出 |
| `AutoDownloadUpdates` | `false` | 其他版本的 HyperKit 不一定能被补丁识别 |
| `AutoStart` | `true` | 登录后自动启动 |
| `MemoryMiB` / `Cpus` | `6144` / `4` | |

第一次启动时，Docker 会弹 osascript 密码框，把 docker 命令链接到 `/usr/local/bin`，这是正常的。

### 过期 pid 文件的清理

HyperKit 一旦崩溃，就会留下 `hyperkit.pid`，导致下次启动失败。RyzenHV 0.7.8 的开机服务只在开机时清理一次。`scripts/` 目录里的 LaunchAgent 每 60 秒检查一次：

```
mkdir -p ~/.hackintosh && cp scripts/hyperkit-pid-clean.sh ~/.hackintosh/
cp scripts/local.hackintosh.hyperkit-pid-clean.plist ~/Library/LaunchAgents/
sed -i '' "s|__HOME__|$HOME|g" ~/Library/LaunchAgents/local.hackintosh.hyperkit-pid-clean.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/local.hackintosh.hyperkit-pid-clean.plist
```

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
- Docker 设置 `AutoStart=true`。

## 回退

用 `extras/config-no-ryzenhv.plist`：不带 RyzenHV，SIP 是 `00000000`。换掉 config 后删掉 `Kexts/RyzenHV.kext`，然后执行 `sudo ./libexec/hv-sysctl-daemon.sh remove`。
