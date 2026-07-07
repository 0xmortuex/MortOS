# MORT OS

![license](https://img.shields.io/badge/license-MIT-blue)
![arch](https://img.shields.io/badge/arch-x86%20(32--bit)-lightgrey)
![lang](https://img.shields.io/badge/kernel%20written%20in-Mort-8b5cf6)

**An operating-system kernel written in [Mort](https://github.com/0xmortuex/Mort) — my own programming language.** It boots on QEMU *and real hardware*, runs in 32-bit protected mode, and drops you into an interactive shell **with a real filesystem** — write a file, reboot the machine, and it's still there. It even **runs real, interactive compiled programs**: a `.mx` program compiled to a flat binary, loaded off the disk, talking to the kernel through `int 0x80` syscalls — one sample asks your name and greets you. Everything above the boot stub — VGA driver, PS/2 keyboard driver, interrupt handlers, ATA disk driver, the filesystem, the syscall layer, the shell — is written in Mort.

<div align="center">
<img src="docs/mortos.png" alt="MORT OS booted in QEMU" width="640" />
<br/><sub>MORT OS booted in QEMU — type <code>help</code>, then Enter.</sub>
</div>

## What it does

- **A real filesystem (MortFS)** — an ATA PIO disk driver and an on-disk format, both written in Mort. `ls`, `cat <file>`, `write <file> <text>`, `rm <file>`, and `run <file>` (execute a file of shell commands). Files **persist across reboots** — write a note, reboot QEMU, `cat` it back.
- **Runs real, interactive compiled programs** — `exec <file>` loads a Mort program (compiled to a flat binary) off the disk to `0x00A00000` and runs it. Programs share no symbols with the kernel; they call it through **`int 0x80` syscalls** (args passed via a fixed mailbox, since Mort's `asm()` takes no operands). A read-line syscall polls the keyboard directly, so programs can take input too — `exec ask.bin` asks your name and greets you. Sample programs are in [`programs/`](programs/).
- **Boots for real** — a BIOS+UEFI hybrid ISO (Limine bootloader) you can write to a USB stick and boot on actual hardware, not just QEMU's `-kernel` shortcut
- **Interrupt-driven keyboard** — a flat GDT, an IDT, remapped PICs; IRQ1 fires into a Mort handler (no polling)
- **A shell** — command parsing, Backspace line editing, Shift-aware scancode→ASCII, and **command history** (Up/Down arrows, decoded from 0xE0 extended scancodes)
- **PIT timer on IRQ0** (~100 Hz) with an `uptime` command
- **CPU exception handlers** — per-vector stubs that report which fault occurred (try the `crash` command)
- **Terminal scrolling** and a blinking hardware cursor that tracks input
- **Multiboot modules** — the bootloader passes ISO files as modules; `readme` prints one, and a second acts as a boot script the kernel runs at startup like an `/etc/rc`
- **Tested in CI-style headless runs** — `test.py` and `test_fs.py` boot the real kernel in QEMU, inject keystrokes through the monitor, and assert on VGA memory (including the write→reboot→cat persistence path)

## How it fits together

```
kmain.mx    the kernel, in Mort        ─┐
            │  mortc --freestanding      │  Mort -> freestanding C -> 32-bit object
            ▼                            │
boot.s      multiboot header + _start   ─┤  assembled to a 32-bit object
            │                            │
linker.ld   places it at 1 MB           ─┘  linked ->  build/kernel.elf
            │
            ▼
qemu-system-i386 -kernel build/kernel.elf
```

Why does a hobby language compile to C instead of running on an interpreter? **Because an interpreter can't boot.** Mort emits freestanding-friendly C, so `hello.mx` and this kernel go through the exact same compiler.

## Build & run

Requirements: Python 3, `pip install ziglang` (the C cross-compiler), and [QEMU](https://www.qemu.org/) for booting. The [Mort compiler](https://github.com/0xmortuex/Mort) is fetched automatically into `.mort/` on first build (or set `MORT_HOME`, or keep a `../Mort` checkout).

```bash
python build.py check     # build + verify it's a valid 32-bit multiboot ELF
python build.py run       # build, then boot it fullscreen in QEMU (with the disk)
```

`run` auto-creates `build/disk.img` (16 MiB, MortFS) and attaches it, so files
you `write` in the OS survive reboots. `python mkfs.py build/disk.img` wipes it
clean (add `--add host.txt:name.txt` to seed files). Try it:

```
> write notes.txt hello from mort os
> cat notes.txt
> write job.txt echo hi
> write job.txt uptime
> run job.txt
```

### Running programs

MORT OS runs real compiled programs, not just shell scripts. Sources live in
[`programs/`](programs/); `build.py disk` compiles them and seeds them onto the
image, so from the shell:

```bash
python build.py prog      # compile programs/*.mx -> build/*.bin
```
```
> exec hello.bin          # a real Mort program prints via syscall, then returns
> exec ask.bin            # an interactive program: it asks your name and greets you
```

Automated tests (all drive the real kernel headless in QEMU):

```bash
python test.py smoke      # boot + shell basics
python test_fs.py         # the disk stack, incl. write-reboot-cat persistence
python test_exec.py       # build programs, seed, boot, exec, check syscall output
```

### A real bootable ISO

```bash
python build.py iso       # -> build/mort.iso (BIOS + UEFI hybrid, Limine + xorriso)
python build.py run-iso   # build the ISO, then boot it in QEMU
```

Write `mort.iso` byte-for-byte to a USB stick (e.g. Rufus in "DD image" mode) and it boots on real hardware.

## Roadmap

- [x] Everything above (ATA driver, MortFS, and `exec`-ing real programs)
- [ ] Space reclamation for `rm` (v1 leaks the extent; re-mkfs to compact)
- [ ] More syscalls (file I/O from programs, spawn) and a richer program ABI

## Related

- [**Mort**](https://github.com/0xmortuex/Mort) — the language this kernel is written in: lexer, parser, type checker, and C code generator, from scratch in Python with zero libraries.
