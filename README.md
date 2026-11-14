# 300u-hackintosh-15

AMD Athlon PRO 300U 小主机（Zen+ / Picasso，Vega 3 核显）的 macOS **Sequoia 15** OpenCore EFI，可以用 Docker Desktop（通过 [RyzenHV](https://github.com/OverlordDev/ryzen-hypervisor.framework)）。

> ⚠️ 实验性配置。显卡加速、Wi-Fi、Docker 依赖的都是社区驱动，其中 AirportItlwm 是 alpha 版，RyzenHV 是实验项目。要跑 Docker，**必须部分关闭 SIP，并放宽 AMFI 签名检查**（原因见 [docs/DOCKER.md](docs/DOCKER.md)）。不要在会运行不可信代码的机器上用这份配置。

## 硬件

| 部件 | 型号 |
|---|---|
| 主板 | HC HCAR357-MI，AMI Aptio V 5.14（2020-03） |
| CPU | AMD Athlon PRO 300U，2 核 4 线程（family 0x17 model 0x18） |
| 核显 | Radeon Vega 3（`1002:15d8`），UMA 2 GB |
| 内存 | 16 GB（UMA 划走 2 GB，macOS 可用约 14 GB） |
| 硬盘 | aigo NVMe SSD DP35 512 GB（YEESTOR GMT1000，无 DRAM） |
| 有线网卡 | Realtek RTL8111（`10ec:8168`） |
| 无线网卡 | Intel Wireless 8265（`8086:24fd`，蓝牙 `8087:0a2b`） |
| 声卡 | Realtek ALC269VC（未驱动，见下文） |

## 工作情况（macOS 15.8.3）

| 功能 | 状态 | 说明 |
|---|---|---|
| 核显加速 | ✅ | NootedRed（[lorzzn 修改版](https://github.com/lorzzn/NootedRed)，`-NRedDisplayFix`），Metal 3，1080p；Chrome 硬件加速可用 |
| 有线网 | ✅ | 千兆全双工 |
| Wi-Fi | ✅ | AirportItlwm（alpha），系统原生 Wi-Fi 菜单；不支持只开 WPA3 的网络和 AirDrop |
| 蓝牙 | ✅ | 需要 config 里的两个 NVRAM 变量，见 [docs/WIRELESS.md](docs/WIRELESS.md) |
| NVMe | ✅ | 顺序读写约 1.6 / 1.4 GB/s（PCIe Gen2 x4） |
| USB | ✅ | 4 个 USB3 口均为 5 Gb/s；未做 USB 映射 |
| HDMI 音频 | ✅ | |
| 3.5mm 模拟音频 | ❌ | 没加 AppleALC |
| Docker Desktop | ✅ | RyzenHV 0.7.8 + Docker Desktop 4.97.0 Intel 版，见 [docs/DOCKER.md](docs/DOCKER.md) |
| 睡眠 | ⚠️ | macOS 能正常睡眠和唤醒，但 Docker 的虚拟机会在睡眠时崩溃，所以服务器用途下关闭了睡眠 |

## 目录结构

```
EFI/                          直接拷到 U 盘或内置盘的 EFI 分区
  BOOT/BOOTx64.efi
  OC/
    OpenCore.efi              OpenCore 1.0.8 DEBUG
    config.plist              默认配置：带 RyzenHV，SIP 部分关闭（430A0000）
    ACPI/                     SSDT-EC、SSDT-USBX
    Drivers/                  OpenRuntime、HfsPlus、ResetNvramEntry
    Kexts/                    NootedRed、ForgedInvariant 需要你自己放进来
extras/
  config-no-ryzenhv.plist     不需要 Docker 时用：不带 RyzenHV，SIP 全开（这种组合下 NootedRed 修改版未测试）
docs/
  BIOS.md                     BIOS 设置
  WIRELESS.md                 Wi-Fi / 蓝牙
  DOCKER.md                   RyzenHV + Docker Desktop
scripts/
  hyperkit-pid-clean.sh       清理 Docker HyperKit 过期的 pid 文件
  local.hackintosh.hyperkit-pid-clean.plist
  usbwatch.py                 查看每个 USB 口协商出来的速度
```

## 使用步骤

### 1. 自己放入 NootedRed 和 ForgedInvariant（必需）

本仓库**没有包含**这两个 kext，需要你按各自的许可证自己下载。`config.plist` 里已经有它们的条目，只缺文件本身。

- NootedRed（核显驱动，必需）：用修改版 <https://github.com/lorzzn/NootedRed/releases/tag/v0.9.0-pre-release.15-identity.1>，下载 `NootedRed-0.9.0-RELEASE.zip`，可用 release 里的 `SHA256SUMS` 校验。它基于 [steve12311/NootedRed](https://github.com/steve12311/NootedRed)，非官方版本，许可证是 TSNPL 1.5（仅限非商业用途）。
  - 为什么不用官方版：官方 0.8.10 和 0.9.0 在这台机器上，Chrome 一开 GPU 加速，几十秒内 GPU 就卡死，几分钟后 `IPI timeout` panic。修改版靠 boot-args 里的 `-NRedDisplayFix` 修好了这个问题，在 macOS 15.8.3（24H241）上测试通过（Chrome 普通网页、B 站视频、WebGL 都正常）。
  - 修改版只在 macOS 15 上测过；系统小版本更新后如果补丁没装上，Chrome 卡死的问题会回来，见下面「已知问题」。
- ForgedInvariant（TSC 同步）：<https://github.com/ChefKissInc/ForgedInvariant/releases>（测试时用的是 1.5.0）

解压后，把 `NootedRed.kext` 和 `ForgedInvariant.kext` 复制到 `EFI/OC/Kexts/`。

### 2. 生成你自己的 SMBIOS（必需）

`config.plist` 里的序列号是占位值。用 [GenSMBIOS](https://github.com/corpnewt/GenSMBIOS) 或 OpenCore 自带的 `macserial` 生成 **MacBookPro16,2** 的三项值，填进 `PlatformInfo › Generic`：

| 键 | 值 |
|---|---|
| `SystemSerialNumber` / `MLB` | macserial 生成的序列号和 MLB，二者配对使用 |
| `SystemUUID` | 随机 UUID |
| `ROM` | 有线网卡的 MAC 地址（6 字节） |

**一定要去 <https://checkcoverage.apple.com> 查一下序列号，结果必须是"无效"**。如果这个序列号属于一台登记在企业名下的真 Mac，设置向导会卡在 "Remote Management / This Mac is owned by: Unknown" 页面。我第一个、第二个生成的序列号都撞上了真机。

### 3. BIOS

最少要改两处：关闭 IOMMU，确认 SVM 是开着的。这块主板隐藏了 Above 4G Decoding，所以 config 里用 `npci=0x3000` 代替。详见 [docs/BIOS.md](docs/BIOS.md)。

### 4. 制作安装 U 盘

1. 用 OpenCore 自带的 `Utilities/macrecovery` 下载 Sequoia 的 recovery：
   ```
   python macrecovery.py -b Mac-937A206F2EE63C01 -m 00000000000000000 download
   ```
2. U 盘格式化成 FAT32（GPT），把 `EFI/` 和生成的 `com.apple.recovery.boot/` 放到同一个分区的根目录。
3. 用 U 盘启动。在 OpenCore 菜单里按**空格**显示隐藏条目，选 `… (external) (dmg)` 进入 Recovery。

### 5. 安装

在磁盘工具里选择"显示所有设备"，把整块 NVMe 抹成 APFS + GUID 分区图，然后选"重新安装 macOS Sequoia"。安装过程中会在线下载约 15 GB，期间会自动重启几次，OpenCore 会自己选中 `macOS Installer`，不用手动选。

### 6. 把 EFI 拷到内置盘

```
sudo diskutil mount disk0s1              # 先用 diskutil list 确认 EFI 分区
cp -R /Volumes/<U盘>/EFI /Volumes/EFI/
sudo diskutil unmount disk0s1
```

然后在 BIOS 里把内置盘设为第一启动项。

### 7. 装完以后

- 跑 Docker：照 [docs/DOCKER.md](docs/DOCKER.md) 操作，包括 RyzenHV 工具、Docker Desktop 4.97.0、**关闭睡眠**。
- 不跑 Docker：用 `extras/config-no-ryzenhv.plist` 替换 `EFI/OC/config.plist`（替换前记得把你的 SMBIOS 填进去），再删掉 `Kexts/RyzenHV.kext`。这样 SIP 可以保持全开。

## 配置要点

- **AMD 内核补丁**：[AMD_Vanilla](https://github.com/AMD-OSX/AMD_Vanilla)，四条 `cpuid_cores_per_package` 补丁的核心数填 `02`。**换成其他 CPU 时要改成对应的物理核心数。**
- **ACPI**：DSDT 里没有 EC 设备，所以用 [SSDTTime](https://github.com/corpnewt/SSDTTime) 生成了 SSDT-EC（台式机 FakeEC）和 SSDT-USBX。不要用 FixHPET。
- **Quirks**：按 Dortania 指南 [Ryzen and Threadripper (17h/19h)](https://dortania.github.io/OpenCore-Install-Guide/AMD/zen.html) 设置；`ResizeAppleGpuBars = -1`，因为这块 BIOS 没有 ReBAR 选项。
- **SecureBootModel**：`Disabled`。
- **当前 boot-args**：`-v keepsyms=1 debug=0x100 npci=0x3000 rhv_enable_svm=1 rhv_allow_users=1 amfi_get_out_of_my_way=0x1 rhv_hv=1 rhv_selftest=1 ipc_control_port_options=0 -NRedDisplayFix`
- **`csr-active-config`**：`430A0000`。Docker 至少需要 `03080000`（见 [docs/DOCKER.md](docs/DOCKER.md)），`430A0000` 在此基础上多放开了 0x40（NVRAM）和 0x200（未经批准的 kext），NootedRed 修改版的作者推荐这个值，测试也是在这个值下做的。

### 调试设置（稳定后可以关掉）

这份配置仍然是调试状态：
- 用的是 OpenCore **DEBUG** 版；
- `Misc › Debug › Target = 67`，每次开机都会在 EFI 分区根目录写一个约 256 KB 的 `opencore-*.txt` 日志；
- boot-args 里有 `-v keepsyms=1 debug=0x100`，开机时会滚动显示启动文字。

稳定以后可以这样改：从 OpenCore 1.0.8 RELEASE 包里取出 `BOOTx64.efi`、`OpenCore.efi` 和各个驱动，替换掉现在的文件；`Target` 改为 `3`；从 boot-args 里删掉 `-v keepsyms=1 debug=0x100`。

## 已知问题

- **Chrome 卡死整机（只在用官方 NootedRed 时出现）**：Chrome 的 GPU 进程一启动，几十秒内 GPU 就卡死（`GFX event timeout` / `gpuRestart`），WindowServer 跟着卡死，几分钟后 `IPI timeout` panic。用修改版并加上 `-NRedDisplayFix` 就不会出现。补丁装没装上，可以用 `ioreg -l -w0 | grep NRedSubmitGuard` 看：应该有 `NRedSubmitGuardWindowServerApplied = 1`，而且没有 `...DynamicRejected = 1`。如果补丁没装上（比如 macOS 更新以后），在 Chrome 设置里关掉"使用图形加速功能"就能避开。
- **开机时 RyzenHV 只在 1 个 CPU 上开启了 SVM**：OpenCore 注入 kext 时，其余核心还没上线。kext 会在第一次创建虚拟机时自动重新扫描，补齐到 4/4；也可以手动执行 `rhv-info hv rescan`。
- **睡眠**：一睡眠，正在运行的 HyperKit 就会崩溃（`VmRun: SVM was turned off under us`）。所以服务器用途下关掉了系统睡眠。
- **NVMe 链路速率**：`system_profiler` 显示的 2.5 GT/s 是开机时读到的旧值，实测速度对应 Gen2 x4。把 BIOS 里 AMD CBS › NBIO › PCIe › PSPP Policy 改成 Performance 也许能升到 Gen3，但我没测过。
- **`shutdown_stall` 诊断报告**：每次关机都会生成一份，可以忽略。里面只有正常最后退出的系统进程，偶尔还会有 AppleSpell 自己死锁（苹果自身的 bug）。
- **USB**：主板 ACPI 把两个 USB-A 口标成了 Type-C，只是标签不对，不影响使用。背板上的两个 USB2 口接在主板上的 Genesys USB2.0 集线器后面，硬件本身就只有 USB2 速度。

## 组件与许可证

| 组件 | 版本 | 来源 |
|---|---|---|
| OpenCore (DEBUG) | 1.0.8 | [acidanthera/OpenCorePkg](https://github.com/acidanthera/OpenCorePkg) |
| HfsPlus.efi | — | [acidanthera/OcBinaryData](https://github.com/acidanthera/OcBinaryData) |
| Lilu | 1.7.2 | [acidanthera/Lilu](https://github.com/acidanthera/Lilu) |
| VirtualSMC | 1.3.8 | [acidanthera/VirtualSMC](https://github.com/acidanthera/VirtualSMC) |
| NVMeFix | 1.1.3 | [acidanthera/NVMeFix](https://github.com/acidanthera/NVMeFix) |
| RestrictEvents | 1.1.6 | [acidanthera/RestrictEvents](https://github.com/acidanthera/RestrictEvents) |
| BlueToolFixup | 2.7.2 | [acidanthera/BrcmPatchRAM](https://github.com/acidanthera/BrcmPatchRAM) |
| RealtekRTL8111 | 3.0.4（release v3.0.0） | [Mieze/RTL8111_driver_for_OS_X](https://github.com/Mieze/RTL8111_driver_for_OS_X) |
| AppleMCEReporterDisabler | 1.2 | [acidanthera/bugtracker 附件](https://github.com/acidanthera/bugtracker/files/3703498/AppleMCEReporterDisabler.kext.zip) |
| IntelBluetoothFirmware / IntelBTPatcher | 2.4.0 | [OpenIntelWireless/IntelBluetoothFirmware](https://github.com/OpenIntelWireless/IntelBluetoothFirmware) |
| AirportItlwm (Sequoia) | 2.4.0-alpha (7204c69) | [laobamac/itlwm](https://github.com/laobamac/itlwm/releases/tag/v2.4.0-alpha) |
| RyzenHV | 0.7.8 | [OverlordDev/ryzen-hypervisor.framework](https://github.com/OverlordDev/ryzen-hypervisor.framework) |
| NootedRed（修改版） | v0.9.0-pre-release.15-identity.1 | [lorzzn/NootedRed](https://github.com/lorzzn/NootedRed/releases/tag/v0.9.0-pre-release.15-identity.1)，需自行下载，见步骤 1 |
| ForgedInvariant | 1.5.0 | [ChefKissInc/ForgedInvariant](https://github.com/ChefKissInc/ForgedInvariant/releases)，需自行下载，见步骤 1 |

各组件按各自的许可证分发。本仓库自己写的文档和脚本只是附带的说明。
