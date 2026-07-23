#!/usr/bin/env python3
"""Boot the parallel x86-64 kernel and verify the real long-mode handoff."""

import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ELF64 = os.path.join(HERE, "build", "x86_64", "kernel.elf")


def find_qemu64():
    found = shutil.which("qemu-system-x86_64")
    if found:
        return found
    installed = r"C:\Program Files\qemu\qemu-system-x86_64.exe"
    if os.path.isfile(installed):
        return installed
    return None


def main():
    subprocess.run([sys.executable, os.path.join(HERE, "build.py"), "check64"],
                   check=True)
    qemu = find_qemu64()
    if not qemu:
        sys.exit("x86-64 test needs qemu-system-x86_64")

    cmd = [
        qemu,
        "-machine", "q35",
        "-m", "256M",
        "-display", "none",
        "-serial", "stdio",
        "-monitor", "none",
        "-no-reboot",
        "-kernel", ELF64,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
        output = result.stdout + result.stderr
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + (exc.stderr or "")
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")

    expected = [
        "MORT64: long mode active",
        "MORT64: kernel entry is compiled from Mort",
        "MORT64: Multiboot handoff received",
        "MORT64: Multiboot memory map accepted",
        "MORT64: physical frame allocator passed",
        "MORT64: bootstrap foundation ready",
    ]
    missing = [line for line in expected if line not in output]
    if missing:
        print(output)
        sys.exit("x86-64 boot test FAILED; missing: " + ", ".join(missing))

    print("OK: x86-64 long-mode boot entered Mort code")
    for line in expected:
        print("  " + line)


if __name__ == "__main__":
    main()
