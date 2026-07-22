#!/usr/bin/env python3
"""Boot the ACPI demo; verify discovery + a real ACPI poweroff.

The demo prints what it discovered, then powers off via ACPI S5. A clean QEMU
exit (code 0) means the discovered PM1a_CNT + S5 value are correct; the
isa-debug-exit fallback (code 1) fires only if the poweroff did not take.

    python hwtest/build_acpi_demo.py && python hwtest/run_acpi_demo.py
"""
import os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ELF = os.path.join(HERE, "out", "acpi_demo.elf")
sys.path.insert(0, ROOT)
import build as b  # noqa: E402

def main():
    qemu = b._find_qemu()
    if not qemu:
        sys.exit("qemu-system-i386 not found")
    if not os.path.exists(ELF):
        sys.exit(f"demo not built: {ELF}")
    cmd = [qemu, "-display", "none", "-serial", "stdio", "-no-reboot",
           "-kernel", ELF,
           "-device", "isa-debug-exit,iobase=0xf4,iosize=0x04"]
    rc = None
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        serial, rc = res.stdout, res.returncode
    except subprocess.TimeoutExpired as e:
        serial = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
    print("----- serial log -----"); print(serial.strip()); print("----------------------")
    print("qemu exit code:", rc)
    ok = True
    if "present=y" not in serial:
        print("FAIL: ACPI not present"); ok = False
    if "pm1a_cnt=00000000" in serial or "pm1a_cnt=" not in serial:
        print("FAIL: no PM1a control register discovered"); ok = False
    if "s5=y" not in serial:
        print("FAIL: S5 sleep value not parsed from DSDT"); ok = False
    if "poweroff FAILED" in serial or rc != 0:
        print("FAIL: ACPI poweroff did not power the machine off cleanly"); ok = False
    if ok:
        print("PASS: ACPI tables discovered and the machine powered off via ACPI S5")
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
