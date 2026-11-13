# Wi-Fi 与蓝牙（Intel Wireless 8265）

## Wi-Fi：AirportItlwm（Sequoia 版，alpha）

- 驱动来自 [laobamac/itlwm](https://github.com/laobamac/itlwm) 的 `AirportItlwm-Sequoia-v2.4.0-RELEASE-alpha-7204c69`。官方 OpenIntelWireless 版本只支持到 Sonoma 14.4。这个分支不用打 OCLP 的 root patch，SIP 也可以保持开启。
- config 里限定了 `MinKernel 24.2.0` / `MaxKernel 24.99.99`，所以只会在 Sequoia 上加载。升级到 Tahoe 前，要先换成 Tahoe 版的 kext。
- 用起来就是系统自带的 Wi-Fi 菜单，扫描、连接、切换网络都可以。
- 有这些限制：
  - 只开 WPA3 的网络和强制开启 PMF 的网络连不上；WPA2，以及 WPA2/WPA3 混合模式都没问题；
  - 不支持 AirDrop 和 AWDL；
  - 因为是 alpha 版，要多观察几天看稳不稳定。
- 如果从 itlwm 换过来之后，网络设置里残留了旧的 "Ethernet Adapter (en1)" 服务，先建一个新的 Wi-Fi 服务，再删掉旧的：
  ```
  sudo networksetup -createnetworkservice Wi-Fi en1
  sudo networksetup -removenetworkservice "Ethernet Adapter (en1)"
  ```
- **回退方案**：换回 [itlwm 2.3.0](https://github.com/OpenIntelWireless/itlwm/releases)（把 Kexts 和 config 里的 `AirportItlwm.kext` 改成 `itlwm.kext`，不用限定内核版本），然后用 [HeliPort](https://github.com/OpenIntelWireless/HeliPort) 管理 Wi-Fi。
- Wi-Fi 默认会用随机的私有地址。如果要在路由器上按 MAC 绑定 IP，在网络详情里把"私有 Wi-Fi 地址"关掉。

## 蓝牙：IntelBluetoothFirmware + 两个 NVRAM 变量

Kext 有三个，都排在 Lilu 后面：`BlueToolFixup`、`IntelBluetoothFirmware`、`IntelBTPatcher`。

光有 kext 还不行。在 Sequoia 上，`bluetoothd` 启动时会去 NVRAM 里找"内置蓝牙控制器信息"，找不到就把这张卡当成苹果自家的芯片来处理，然后一直重复：

```
[bm3_usb][IOThreadFunc] -- USB -- Can't obtain vendorID and productID -- try again
```

大约 15 秒后它会崩溃并重新启动，系统里看到的就是 `Address: NULL`、`State: Off`、`Chipset: BCM_4350C2`。

解决办法是在 `NVRAM › Add › 7C436110-AB2A-4BBB-A880-FE41995C9F82` 下加两个变量，并且在 `NVRAM › Delete` 的同一个 GUID 下也写上这两个键名，这样每次开机 OpenCore 都会重新写入：

| 键 | 类型 | 值 |
|---|---|---|
| `bluetoothExternalDongleFailed` | Data | `00` |
| `bluetoothInternalControllerInfo` | Data | `0000000000000000000000000000`（14 字节） |

改完后蓝牙会被识别为外接 USB 适配器，`Chipset: THIRD_PARTY_DONGLE`，能正常配对。来源：[IntelBluetoothFirmware#513](https://github.com/OpenIntelWireless/IntelBluetoothFirmware/issues/513)，那里有人在同一张 8265（`8087:0A2B`）上验证过。
