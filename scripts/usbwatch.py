#!/usr/bin/env python3
"""Log USB plug/unplug on macOS: controller, port, port type (USB2/USB3) and negotiated speed.

Usage: usbwatch.py [seconds]   (no argument or 0 = print the current devices once)
A USB3 device in a working USB3 port shows "USB3 port" and "5Gb/s Super".
"""
import plistlib
import subprocess
import sys
import time

SPEED = {0: "1.5Mb/s Low", 1: "12Mb/s Full", 2: "480Mb/s High (USB2)",
         3: "5Gb/s Super (USB3)", 4: "10Gb/s Super+ (USB3.1)"}


def snapshot():
    raw = subprocess.run(["ioreg", "-a", "-l", "-w0", "-r", "-c", "AppleUSBHostPort"],
                         capture_output=True).stdout
    out = {}

    def walk(port, node, hub):
        # Interfaces also carry idVendor; only IOUSBHostDevice nodes are devices. Recurse through every node
        # (hub ports included) so devices behind a hub are found too.
        for c in node.get("IORegistryEntryChildren", []):
            if c.get("IOObjectClass") in ("IOUSBHostDevice", "AppleUSBDevice"):
                key = (c.get("locationID", 0) & 0xFFFFFFFF, c["idVendor"], c["idProduct"])
                ctl = "XHC1" if (port.get("locationID", 0) & 0xFFFFFFFF) >> 28 == 8 else "XHC0"
                kind = "USB3 port" if "30" in port["IOObjectClass"] else "USB2 port"
                where = f'{ctl} {port["IORegistryEntryName"]} [{kind}{" via hub " + hub if hub else ""}]'
                dev = f'{c.get("USB Product Name", "?")} {c["idVendor"]:04x}:{c["idProduct"]:04x}'
                out[key] = (where, dev, SPEED.get(c.get("Device Speed"), str(c.get("Device Speed"))))
                walk(port, c, hub or c.get("USB Product Name", "hub"))
            else:
                walk(port, c, hub)

    for p in plistlib.loads(raw):
        walk(p, p, None)
    return out


def main():
    dur = float(sys.argv[1]) if len(sys.argv) > 1 else 0
    prev = snapshot()
    if dur == 0:
        for v in prev.values():
            print(" | ".join(v))
        return
    print(time.strftime("%T"), "watching", int(dur), "s", flush=True)
    end = time.time() + dur
    while time.time() < end:
        time.sleep(1)
        cur = snapshot()
        for k in cur.keys() - prev.keys():
            print(time.strftime("%T"), "PLUG  ", " | ".join(cur[k]), flush=True)
        for k in prev.keys() - cur.keys():
            print(time.strftime("%T"), "UNPLUG", " | ".join(prev[k]), flush=True)
        prev = cur


if __name__ == "__main__":
    main()
