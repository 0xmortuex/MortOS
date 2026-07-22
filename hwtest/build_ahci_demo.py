#!/usr/bin/env python3
"""Build the standalone AHCI driver verification kernel.

Reuses the kernel build's Mort compiler + exact flags (from ../build.py), so the
driver is exercised under the same -O2 codegen it ships with. Concatenates
net/ahci.mx with hwtest/ahci_demo.mx (which supplies its own PCI accessors and
serial log) and links them with the minimal demo_boot.s into a multiboot ELF at
hwtest/out/.

    python hwtest/build_ahci_demo.py

Then boot hwtest/out/ahci_demo.elf with an ich9-ahci controller + a test disk;
see run_ahci_demo.py.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import build as b  # noqa: E402

# Mort emits prototypes first, so cross-file calls resolve regardless of order.
SRC_ORDER = [os.path.join(ROOT, "net", "ahci.mx"),
             os.path.join(HERE, "ahci_demo.mx")]


def main():
    out = os.path.join(HERE, "out")
    os.makedirs(out, exist_ok=True)
    cc = b._zig()

    combined = ""
    for path in SRC_ORDER:
        with open(path, encoding="utf-8") as fh:
            combined += fh.read() + "\n"

    c_source = b.mortc.compile_to_c(combined, freestanding=True)
    c_file = os.path.join(out, "ahci.c")
    with open(c_file, "w", encoding="utf-8") as fh:
        fh.write(c_source)

    c_flags = ["-target", b.TARGET, "-ffreestanding", "-fno-builtin",
               "-fno-stack-protector", "-fno-pie",
               "-fno-asynchronous-unwind-tables", "-fno-unwind-tables",
               "-mno-sse", "-mno-sse2", "-mno-mmx", "-O2"]
    asm_flags = ["-target", b.TARGET, "-fno-pie"]

    demo_o = os.path.join(out, "ahci.o")
    runtime_o = os.path.join(out, "runtime.o")
    boot_o = os.path.join(out, "demo_boot.o")
    elf = os.path.join(out, "ahci_demo.elf")

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
