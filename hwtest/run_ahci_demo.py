#!/usr/bin/env python3
"""Boot the AHCI demo kernel with a test disk and verify it reads real sectors.

Writes a raw disk image with a known ASCII marker in sectors 0 and 1, boots the
demo under an ich9-ahci controller with that disk attached, captures the serial
log, and checks the driver read the markers back over DMA.

    python hwtest/build_ahci_demo.py && python hwtest/run_ahci_demo.py
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "out")
ELF = os.path.join(OUT, "ahci_demo.elf")
IMG = os.path.join(OUT, "ahci_test.img")

SECTOR0 = b"MORTOS-AHCI-SECTOR-00-XYZZY"
SECTOR1 = b"MORTOS-AHCI-SECTOR-01-PLUGH"

sys.path.insert(0, ROOT)
import build as b  # noqa: E402


def make_disk():
    os.makedirs(OUT, exist_ok=True)
    data = bytearray(1024 * 1024)               # 1 MiB raw disk
    data[0:len(SECTOR0)] = SECTOR0
    data[512:512 + len(SECTOR1)] = SECTOR1
    with open(IMG, "wb") as fh:
        fh.write(data)


def run_qemu():
    qemu = b._find_qemu()
    if not qemu:
        sys.exit("qemu-system-i386 not found")
    if not os.path.exists(ELF):
        sys.exit(f"demo not built: {ELF} (run build_ahci_demo.py first)")
    cmd = [
        qemu, "-display", "none", "-serial", "stdio", "-no-reboot",
        "-kernel", ELF,
        "-drive", f"id=disk0,file={IMG},if=none,format=raw",
        "-device", "ich9-ahci,id=ahci0",
        "-device", "ide-hd,drive=disk0,bus=ahci0.0",
        "-device", "isa-debug-exit,iobase=0xf4,iosize=0x04",
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        serial = res.stdout
    except subprocess.TimeoutExpired as e:
        serial = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
    print("----- serial log -----")
    print(serial.strip())
    print("----------------------")
    return serial


def check(serial):
    ok = True
    if "ready=y" not in serial:
        print("FAIL: driver did not report ready"); ok = False
    if SECTOR0.decode() not in serial:
        print("FAIL: sector 0 marker not read back"); ok = False
    if SECTOR1.decode() not in serial:
        print("FAIL: sector 1 marker not read back"); ok = False
    if ok:
        print("PASS: AHCI controller inited and DMA-read both markers off the disk")
    else:
        sys.exit(1)


if __name__ == "__main__":
    make_disk()
    serial = run_qemu()
    check(serial)
