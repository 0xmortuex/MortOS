#!/usr/bin/env python3
"""Build the standalone E1000 driver verification kernel.

Reuses the real kernel build's Mort compiler and exact C/link flags (imported
from ../build.py) so the driver is exercised under the same -O2 codegen it ships
with. Concatenates only the pure network files it needs -- endian + eth (framing),
rtl8139 (PCI config accessors) -- then net/e1000.mx and hwtest/e1000_demo.mx, and
links them with the minimal demo_boot.s into a multiboot ELF at hwtest/out/.

    python hwtest/build_e1000_demo.py

Then boot hwtest/out/e1000_demo.elf with `-device e1000` and a filter-dump; see
run_e1000_demo.py.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import build as b  # noqa: E402  (reuse the kernel build's compiler + flags)

# Dependency order: helpers before the driver, driver before the demo main.
NET_ORDER = ["endian.mx", "eth.mx", "rtl8139.mx", "e1000.mx"]


def main():
    out = os.path.join(HERE, "out")
    os.makedirs(out, exist_ok=True)
    cc = b._zig()

    combined = ""
    for name in NET_ORDER:
        with open(os.path.join(ROOT, "net", name), encoding="utf-8") as fh:
            combined += fh.read() + "\n"
    with open(os.path.join(HERE, "e1000_demo.mx"), encoding="utf-8") as fh:
        combined += fh.read()

    c_source = b.mortc.compile_to_c(combined, freestanding=True)
    c_file = os.path.join(out, "demo.c")
    with open(c_file, "w", encoding="utf-8") as fh:
        fh.write(c_source)

    c_flags = ["-target", b.TARGET, "-ffreestanding", "-fno-builtin",
               "-fno-stack-protector", "-fno-pie",
               "-fno-asynchronous-unwind-tables", "-fno-unwind-tables",
               "-mno-sse", "-mno-sse2", "-mno-mmx", "-O2"]
    asm_flags = ["-target", b.TARGET, "-fno-pie"]

    demo_o = os.path.join(out, "demo.o")
    runtime_o = os.path.join(out, "runtime.o")
    boot_o = os.path.join(out, "demo_boot.o")
    elf = os.path.join(out, "e1000_demo.elf")

    subprocess.run([*cc, *c_flags, "-c", c_file, "-o", demo_o], check=True)
    subprocess.run([*cc, *c_flags, "-c", os.path.join(ROOT, "runtime.c"),
                    "-o", runtime_o], check=True)
    subprocess.run([*cc, *asm_flags, "-c", os.path.join(HERE, "demo_boot.s"),
                    "-o", boot_o], check=True)
    subprocess.run([
        *cc, "-target", b.TARGET, "-nostdlib", "-static", "-no-pie",
        "-Wl,-T," + os.path.join(ROOT, "linker.ld"),
        "-Wl,--build-id=none",
        "-o", elf, boot_o, demo_o, runtime_o,
    ], check=True)
    print("built", os.path.relpath(elf, ROOT))


if __name__ == "__main__":
    main()
