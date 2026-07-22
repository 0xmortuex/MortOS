#!/usr/bin/env python3
"""Build the standalone ACPI discovery verification kernel.

Reuses the kernel build's Mort compiler + flags (from ../build.py). Concatenates
net/acpi.mx with hwtest/acpi_demo.mx and links with demo_boot.s into a multiboot
ELF at hwtest/out/. Then boot it (see run_acpi_demo.py).

    python hwtest/build_acpi_demo.py
"""
import os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import build as b  # noqa: E402
SRC_ORDER = [os.path.join(ROOT, "net", "acpi.mx"), os.path.join(HERE, "acpi_demo.mx")]

def main():
    out = os.path.join(HERE, "out"); os.makedirs(out, exist_ok=True)
    cc = b._zig()
    combined = ""
    for p in SRC_ORDER:
        with open(p, encoding="utf-8") as fh:
            combined += fh.read() + "\n"
    c_source = b.mortc.compile_to_c(combined, freestanding=True)
    c_file = os.path.join(out, "acpi.c")
    with open(c_file, "w", encoding="utf-8") as fh:
        fh.write(c_source)
    c_flags = ["-target", b.TARGET, "-ffreestanding", "-fno-builtin",
               "-fno-stack-protector", "-fno-pie", "-fno-asynchronous-unwind-tables",
               "-fno-unwind-tables", "-mno-sse", "-mno-sse2", "-mno-mmx", "-O2"]
    asm_flags = ["-target", b.TARGET, "-fno-pie"]
    demo_o = os.path.join(out, "acpi.o"); runtime_o = os.path.join(out, "runtime.o")
    boot_o = os.path.join(out, "demo_boot.o"); elf = os.path.join(out, "acpi_demo.elf")
    subprocess.run([*cc, *c_flags, "-c", c_file, "-o", demo_o], check=True)
    subprocess.run([*cc, *c_flags, "-c", os.path.join(ROOT, "runtime.c"), "-o", runtime_o], check=True)
    subprocess.run([*cc, *asm_flags, "-c", os.path.join(HERE, "demo_boot.s"), "-o", boot_o], check=True)
    subprocess.run([*cc, "-target", b.TARGET, "-nostdlib", "-static", "-no-pie",
        "-Wl,-T," + os.path.join(ROOT, "linker.ld"), "-Wl,--build-id=none",
        "-o", elf, boot_o, demo_o, runtime_o], check=True)
    print("built", os.path.relpath(elf, ROOT))

if __name__ == "__main__":
    main()
