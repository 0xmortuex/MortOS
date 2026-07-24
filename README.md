# MORT OS

![license](https://img.shields.io/badge/license-MIT-blue)
![arch](https://img.shields.io/badge/arch-x86%20(32--bit)-lightgrey)
![lang](https://img.shields.io/badge/kernel%20written%20in-Mort-8b5cf6)

**An operating-system kernel written in [Mort](https://github.com/0xmortuex/Mort) — my own programming language.** It boots on QEMU *and real hardware*, runs in 32-bit protected mode, and paints a **graphical desktop** — a **home launcher** (`F5`) and four apps, a Terminal, a Files manager, a Vex-styled browser, and a Settings control center, switched with `F1`–`F4`, all drawn to a linear framebuffer in a bitmap font. It has a **real hierarchical filesystem** with directories, ownership, and Unix-style permissions — write a file, reboot the machine, and it's still there — plus **users and `sudo`**, a shell with a **working directory, `$PATH` lookup, and environment variables**, and it **runs real, interactive compiled programs** (a `.mx` program compiled to a flat binary, loaded off the disk, talking to the kernel through `int 0x80` syscalls). It also **speaks TCP/IP**: the [mortnet](https://github.com/0xmortuex/mortnet) stack is vendored into the kernel, so MORT OS gets its own IP over DHCP and **runs a web server**. Everything above the boot stub — the framebuffer renderer, PS/2 keyboard driver, interrupt handlers, ATA disk driver, the filesystem, the syscall layer, the RTL8139 network driver, the shell — is written in Mort.

## A home screen with apps

Boot lands on a **keyboard-navigable home launcher** — a grid of drawn app icons (MORT OS has no mouse yet): Terminal, Files, Vex, Settings, and Power. Arrow keys move the highlight, Enter launches, `Esc` returns to the current app, and **`F5`** reopens it from anywhere. The **Settings** app is a real graphical control center with categories, search, accessibility options, and system diagnostics.

<img src="docs/mortos-home.png" alt="MORT OS home launcher: an app grid with Terminal, Files, Vex, Settings, and Power tiles" width="640" />

## Users, permissions &amp; sudo

MORT OS has accounts: `root` (uid 0) and a normal user, with hashed passwords and auto-login at boot into `/home/mortuex`. Files carry an **owner and Unix-style permission bits**, and the kernel enforces them — a normal user owns their home but can't touch root-owned `/etc` until they `sudo`. Commands: `whoami`, `su [user]`, `sudo <cmd>` (password prompt, then one command as root), `passwd`, `chmod <octal> <path>`, `chown <uid> <path>`.

<img src="docs/mortos-lock.png" alt="MORT OS lock screen asking for the account password" width="640" />

## Session &amp; power

A proper session layer, the way you'd expect from a desktop OS. The top bar carries a **live clock** (read from the CMOS RTC) and the `F5 home` / `F12 power` hints. **`F12`** opens a **power menu** — Lock, Sleep, Restart, Shut down — with arrow-key navigation; `Esc` cancels it non-destructively (the screen under it is saved and restored). **Lock** shows a password screen that checks your real account password; **Sleep** blanks the display until a key; **Shut down** powers the machine off (via ACPI on emulators, or an "It is now safe to turn off your computer" halt on bare metal). Everything is a shell command too: `lock`, `sleep`, `restart`, `shutdown`, `power`.

<img src="docs/mortos-power.png" alt="MORT OS power menu: Lock, Sleep, Restart, Shut down, with a live clock in the top bar" width="640" />

## Networking — it serves a web page

`net` brings up the RTL8139 NIC and leases an address over DHCP; `httpd` then serves an HTML page on port 80. This is the [mortnet](https://github.com/0xmortuex/mortnet) stack — NIC driver, ARP, IPv4, ICMP, UDP, DHCP, DNS, TCP, HTTP, all written from scratch in Mort — vendored into `net/` and compiled into the kernel.

![MORT OS networking: net leases 10.0.2.15 over DHCP, httpd serves on port 80](docs/mortos-net.png)

<sub>A web server, on an OS, over a TCP/IP stack — every layer in one language. Networking needs an RTL8139 NIC (QEMU emulates one; on real hardware, a ~$5 PCI card). The rest of the OS boots and runs on any machine.</sub>

![MORT OS graphical desktop](docs/desktop.png)

<div align="center">
<img src="docs/mortos.png" alt="MORT OS booted in QEMU" width="640" />
<br/><sub>MORT OS booted in QEMU — type <code>help</code>, then Enter.</sub>
</div>

## What it does

- **A graphical desktop with apps** — a multiboot linear framebuffer, an 8×16 bitmap font renderer, and a **window manager**: a home launcher on `F5` and `F1`–`F4` app switching between a **Terminal**, a **Files** manager (browse MortFS, open files), a **Vex-styled browser** app (local pages, a tribute to [Vex](https://github.com/0xmortuex/Vex)), and a **Settings** control center. The whole shell renders to the framebuffer because only the cell-drawing primitive changed; everything else is untouched. Falls back to VGA text mode when no framebuffer is present (the bare `-kernel` path).

![MORT OS Files app](docs/app-files.png)
- **A real filesystem (MortFS v2)** — an ATA PIO disk driver and an on-disk format, both written in Mort. **Hierarchical directories** (`mkdir`, `rmdir`, `.` and `..`, absolute and relative paths) with a seeded `/bin` `/etc` `/home` `/var` layout, and **per-file metadata**: type, owner, Unix permission bits, and an RTC modification time — `ls` shows all of it. `cat`, `write`, `rm`, and `run <file>` (execute a file of shell commands) are all path-aware, a v1 disk upgrades to v2 in place, and files **persist across reboots** — write a note, reboot QEMU, `cat` it back.
- **Users and enforced permissions** — an account table with hashed passwords, `whoami`/`su`/`sudo`/`passwd`/`chmod`/`chown`, write checks on every file and directory, and a lock screen backed by the real account password.
- **A kernel heap** — `kmalloc`/`kfree` and a freestanding memory runtime, so the kernel and vendored drivers can allocate without libc.
- **Hardware beyond the basics** — UHCI **USB enumeration** at boot (with multifunction PCI scanning), an **AC'97 PCM audio** driver, PC-speaker tones, and PCI hardware discovery. The reusable driver work lives in its own repo: [MortHardware](https://github.com/0xmortuex/MortHardware).
- **Runs real, interactive compiled programs** — `exec <file>` loads a Mort program (compiled to a flat binary) off the disk to `0x00A00000` and runs it. Programs share no symbols with the kernel; they call it through **`int 0x80` syscalls** (args passed via a fixed mailbox, since Mort's `asm()` takes no operands). A read-line syscall polls the keyboard directly, so programs can take input too — `exec ask.bin` asks your name and greets you. Sample programs are in [`programs/`](programs/).
- **Boots for real** — a BIOS+UEFI hybrid ISO (Limine bootloader) you can write to a USB stick and boot on actual hardware, not just QEMU's `-kernel` shortcut
- **Interrupt-driven keyboard** — a flat GDT, an IDT, remapped PICs; IRQ1 fires into a Mort handler (no polling)
- **A real shell** — a **working directory** (`cd`, `pwd`, a path-aware `~/sub $` prompt), **`$PATH` lookup** (type `hello` and the shell finds and runs `/bin/hello.bin`, gated on the execute bit), **environment variables** (`export`, `env`, `unset`, with `$VAR` expansion in every command line), full-symbol keyboard input, Backspace line editing, Shift-aware scancode→ASCII, and **command history** (Up/Down arrows, decoded from 0xE0 extended scancodes)
- **PIT timer on IRQ0** (~100 Hz) with an `uptime` command
- **CPU exception handlers** — per-vector stubs that report which fault occurred (try the `crash` command)
- **Terminal scrolling** and a cursor that tracks input (a drawn underline in graphics, the hardware cursor in text mode)
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
python test.py smoke      # boot + shell basics (text-mode -kernel path)
python test_fs.py         # the disk stack, incl. write-reboot-cat persistence
python test_exec.py       # build programs, seed, boot, exec, check syscall output
python test_gfx.py        # boot the ISO, screendump, assert the desktop + console rendered
```

The graphical desktop comes up on the ISO path (`run-iso`), where Limine
provides the framebuffer. The bare `-kernel` path has no framebuffer, so the
kernel falls back to VGA text mode there — which is why the text-driven tests
above still work.

### A real bootable ISO

```bash
python build.py iso       # -> build/mort.iso (BIOS + UEFI hybrid, Limine + xorriso)
python build.py run-iso   # build the ISO, then boot it in QEMU
```

Write `mort.iso` byte-for-byte to a USB stick (e.g. Rufus in "DD image" mode) and it boots on real hardware.

## Roadmap

- [x] Everything above (home launcher + four apps, users/permissions/`sudo`, MortFS v2 directories, working directory + `$PATH` + env vars, networking, USB/audio drivers, `exec`-ing real programs)
- [ ] `mpkg`, the package manager — its repository format and registry already exist: [mort-repo](https://github.com/0xmortuex/mort-repo)
- [ ] Space reclamation for `rm` (the extent leaks; re-mkfs to compact)
- [ ] More syscalls (file I/O from programs, spawn) and a richer program ABI
- [ ] A mouse (PS/2 IRQ12) and clickable window chrome — a real GUI

## Related

- [**Mort**](https://github.com/0xmortuex/Mort) — the language this kernel is written in: lexer, parser, type checker, and C code generator, from scratch in Python with zero libraries.
- [**mortnet**](https://github.com/0xmortuex/mortnet) — the TCP/IP stack vendored into `net/`: NIC driver, ARP, IPv4, ICMP, UDP, DHCP, DNS, TCP, HTTP, from scratch in Mort.
- [**MortHardware**](https://github.com/0xmortuex/MortHardware) — the reusable bare-metal drivers extracted from this kernel: PCI, RTL8139, AC'97, UHCI USB + HID, PC speaker.
- [**mort-repo**](https://github.com/0xmortuex/mort-repo) — the package repository format and registry for `mpkg`, the planned MORT OS package manager.
