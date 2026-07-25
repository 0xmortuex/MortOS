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
        "-cpu", "max",
        "-m", "64M",
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
        "MORT64: canonical VexFS image validated",
        "MORT64: GDT TSS IDT and SYSCALL active",
        "MORT64: hardware entropy source active",
        "MORT64: IDT breakpoint self-test passed",
        "MORT64: PIT timer interrupts active",
        "MORT64: ELF64 loader mapped five isolated processes",
        "MORT64: syscall rejected supervisor pointer",
        "MORT64 USERSPACE OK",
        "MORT64 PROCESS 2 START",
        "MORT64: ring 3 Mort program invoked write",
        "MORT64: user CPU fault contained",
        "MORT64 PROCESS 3 OK",
        "MORT64 PROCESS 1 RESUMED",
        "MORT64: cooperative context switch passed",
        "MORT64: demand-paged process heap passed",
        "MORT64: protected Mort userspace passed",
        "MORT64: supervisor page fault isolation passed",
        "MORT64: scheduler continued after process fault",
        "MORT64: process lifecycle and PID ABI passed",
        "MORT64 PREEMPTED PROCESS OK",
        "MORT64: W^X JIT mapping transition passed",
        "MORT64: timer preemption context switch passed",
        "MORT64 CXX RUNTIME OK",
        "MORT64: ELF argc envp auxv startup passed",
        "MORT64: TLS errno and stack canary passed",
        "MORT64: canonical Vex asset filesystem passed",
        "MORT64: canonical Vex hierarchy stat passed",
        "MORT64: canonical Vex directory enumeration passed",
        "MORT64: private VexFS file mapping passed",
        "MORT64: lazy 1 GiB mmap arena passed",
        "MORT64: relative VexFS path resolution passed",
        "MORT64: getrandom entropy ABI passed",
        "MORT64: eventfd readiness passed",
        "MORT64: blocking epoll event loop passed",
        "MORT64: futex wait and wake passed",
        "MORT64: blocking poll timeout passed",
        "MORT64: blocking poll event wake passed",
        "MORT64: descriptor pipe IPC passed",
        "MORT64: shared-address-space thread passed",
        "MORT64: FS-base TLS and atomic ABI passed",
        "MORT64: freestanding C++ runtime passed",
        "MORT64: process address spaces reclaimed",
        "MORT64: bootstrap foundation ready",
    ]
    missing = [line for line in expected if line not in output]
    errors = [line for line in output.splitlines()
              if line.startswith("MORT64 ERROR:")]
    if missing or errors:
        print(output)
        details = []
        if missing:
            details.append("missing: " + ", ".join(missing))
        if errors:
            details.append("kernel errors: " + " | ".join(errors))
        sys.exit("x86-64 boot test FAILED; " + "; ".join(details))

    print("OK: x86-64 long-mode boot entered Mort code")
    for line in expected:
        print("  " + line)


if __name__ == "__main__":
    main()
