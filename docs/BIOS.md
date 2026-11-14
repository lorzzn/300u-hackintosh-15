# BIOS 设置（HC HCAR357-MI，AMI Aptio V 5.14）

当前设置值是从 SPI ROM 里读出来的：先用 UEFIExtract 解出 Setup / AmdCbs / AmdPbs 模块，再用 IFRExtractor 解析出 IFR 菜单定义，最后对照 NVRAM 里实际存的值得到。

## 需要改的

| 设置 | 位置 | 改成 | 说明 |
|---|---|---|---|
| Hide AMD CBS Item | Advanced › AMD CBS | **Disabled** | 默认是 Enabled，这时 Zen / DF / UMC / NBIO / FCH 这几个子菜单都被隐藏了 |
| IOMMU | Advanced › AMD CBS › NBIO Common Options › NB Configuration | **Disabled** | 默认是 Auto，实际效果等于开启 |

改完按 F10 保存。从 macOS 里可以确认是否生效：`nvram 3A997502-647A-4C82-998E-52EF9486A247:AmdSetup` 的第 `0xDA` 字节应该是 `0`。

## 改不了的项

| 设置 | 情况 | 怎么处理 |
|---|---|---|
| Above 4G Decoding | 在 PCI Subsystem Settings 里，这个菜单被 `Hide CRB Items` 永久隐藏了 | config 的 boot-args 里加了 `npci=0x3000`，两者只能用其中一个 |
| 串口 COM1 | Super IO 菜单同样被隐藏 | 不改也能用 |

## 保持默认就行的

| 设置 | 当前值 |
|---|---|
| CSM Support | Disabled |
| Fast Boot | Disabled |
| Secure Boot | 这块板子没有这个功能 |
| SVM Mode | Enabled（RyzenHV 要用） |
| XHCI Hand-off | Enabled |
| Integrated Graphics | Forces |
| Graphics Memory Size (UMA) | 2G（只能选 Auto、1G、2G 三档；NootedRed 要求大于 512 MB，1G 也够用，但目前的测试都是在 2G 下做的） |
| PSPP Policy | Auto（改成 Performance 也许能让 NVMe 从 Gen2 升到 Gen3，我没测过） |

## 进 BIOS 的方法

开机时连按 **Del**。在 Linux 里用 `systemctl reboot --firmware-setup` 进不去 BIOS：固件会把这个请求标记清掉，但还是照常启动系统。
