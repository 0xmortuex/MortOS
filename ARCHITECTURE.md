# MORT OS architecture

This is an audited overview, measured on 2026-11-08 at commit `83ae7eb`. It covers the whole
system in one place. For deep detail it links to the existing references in
[`docs/`](docs/) (`docs/architecture.md`, `docs/memory-map.md`, `docs/programs.md`,
`docs/shell.md`, `docs/networking.md`, `docs/fs-design.md`, `docs/hardware.md`,
`docs/settings.md`, `docs/accounts.md`, `docs/testing.md`). What the OS lacks is ranked in
[`ROADMAP.md`](ROADMAP.md).

## System at a glance

| Fact | Value |
|---|---|
| Architecture | 32-bit x86, protected mode, no paging, ring 0 only |
| Language | Mort, transpiled to freestanding C, compiled by `zig cc` (`-target x86-freestanding-none`) |
| Boot protocol | Multiboot 1 (`boot.s`) |
| Execution model | No scheduler. After `sti` the kernel idles in `hlt`; IRQ handlers do all the work |
| Mort source in the kernel image | 5,977 lines (`kmain.mx` 3,629, `net/*.mx` 2,348) |
| Non-Mort source in the kernel image | 312 lines (table below) |

### Non-Mort source files

| File | Lines | Linked into | Purpose |
|---|---|---|---|
| `idt.s` | 226 | `kernel.elf` | GDT, IDT fill, PIC remap, 32 exception stubs, IRQ and syscall stubs |
| `boot.s` | 51 | `kernel.elf` | Multiboot header, 16 KiB stack, `_start` |
| `runtime.c` | 35 | `kernel.elf` and every program | `memset`, `memcpy`, `memmove` |
| **Total in the kernel image** | **312** | | |
| `programs/pstart.s` | 8 | every program, not the kernel | Program entry stub |
| `linker.ld` / `programs/prog.ld` | 19 / 13 | layout scripts, contribute no code | Load addresses and section order |

`font_data.mxinc` (264 lines) is Mort-syntax data that nothing includes, so it is not in the
image. The generated `build/kmain.c` is compiler output, not source. Limine ships on the ISO as
a third-party bootloader and is not part of the kernel image.

## Boot flow

```
BIOS/UEFI -> Limine (ISO path) or QEMU -kernel (Multiboot loader)
          -> _start (boot.s:42)            16 KiB stack, then:
             kernel_setup (idt.s:50)       load_gdt, remap_pic, load_idt
             mort_kmain(mbinfo)            kmain.mx:3593
```

`kmain` runs these in order: `heap_init`, `fb_init`, `ui_init` (if graphics), banner,
`fs_init`, `fs_ensure_layout`, `fs_populate_bin`, `acct_init`, `ensure_home`, `login_default`,
`cwd_init`, `run_script(1)`, prompt, `usb_boot_init`, `init_pit`, `ui_start` (if graphics),
`sti`, then `while true { asm("hlt"); }`.

| Path | Command | Display | First screen |
|---|---|---|---|
| Limine ISO | `build.py run-iso` | 1024x768x32 framebuffer | Borehole start screen (`docs/borehole-concept.md`). Enter gives a shell |
| QEMU `-kernel` | `build.py run`, test harnesses | VGA text 80x25 (QEMU ignores the graphics request) | Shell prompt |

## Execution model

Four interrupt sources drive everything after `sti`. All IDT gates use type `0x8E` (ring 0
interrupt gate, `idt.s:73`), so interrupts stay off for the whole handler.

| Source | Stub | Handler |
|---|---|---|
| IRQ1 keyboard | `keyboard_isr` `idt.s:139` | `on_key` `kmain.mx:3495` |
| IRQ0 timer, ~100 Hz | `timer_isr` `idt.s:149` | `on_tick` `kmain.mx:2617` |
| `int 0x80` | `syscall_isr` `idt.s:170` | `on_syscall` `kmain.mx:1864` |
| CPU exceptions 0-31 | `ISR_STUB` `idt.s:180` | `on_exception` `kmain.mx:2629`, then halt forever |

Shell commands run inside the keyboard ISR: `on_key` calls `run_command` (`kmain.mx:3557`) with
interrupts off. Programs, syscalls and network loops therefore run with interrupts off too.
Measured consequence: across a program blocked for 12 s host time in syscall 4, `uptime` went
from 5 s to 8 s, so timer ticks are lost while any command runs.

## Memory map

All addresses are physical. Source: `docs/memory-map.md`, confirmed against `kmain.mx`,
`linker.ld` and `programs/prog.ld`.

| Address | Size | Use |
|---|---|---|
| `0x000B8000` | 4,000 B | VGA text buffer |
| `0x00100000` | image (ELF is 566 KiB) | Kernel, including the 16 KiB stack in `.bss` |
| `0x00800000` | 512 B | `SECBUF` sector scratch |
| `0x00801000` | 4,608 B | `TABCACHE`: superblock and file table |
| `0x00810000` | 64 KiB | `FILEBUF`: whole-file reads |
| `0x009F0000` | 0x180 B | Syscall mailbox and line buffer |
| `0x00A00000` | 64 KiB | Program load area, one program at a time |
| `0x01000000` to top of RAM | dynamic | `kmalloc` heap (239 MB under `-m 256`) |
| from multiboot info | width x height x 4 | Framebuffer (`g_fb`) |

There is no physical frame allocator and no paging. The kernel and programs share one flat
address space and one stack.

## Modules

| Area | Location | Notes |
|---|---|---|
| GDT, IDT, PIC, stubs | `idt.s` | 3 descriptors, ring 0 only, no TSS |
| Console | `kmain.mx:333-602` | `put_cell_at` `:505` is the one write path for VGA and framebuffer |
| Keyboard | `kmain.mx:606`, `on_key:3495` | PS/2, US QWERTY, Shift only |
| Shell | `kmain.mx:2099-2606` | 38 builtins in an `if streq` chain, `$VAR`, history, `$PATH` lookup |
| Heap | `kmain.mx:1041-1131` | First fit with forward coalescing; only `memtest` calls it |
| ATA PIO | `kmain.mx:1142-1242` | Primary master, polled, LBA28, one sector per command |
| MortFS v2 | `kmain.mx:1244-1760`, host `mkfs.py` | 64 entries, 64 KiB extents, directories, modes, no reclaim |
| Accounts | `kmain.mx:2852-3009` | Two in-memory accounts; see `docs/accounts.md` |
| Programs | `exec_file` `kmain.mx:1896`, `programs/` | Flat binaries; see `docs/programs.md` |
| Interface | `ui/borehole.mx`, `docs/borehole-concept.md` | Borehole: surface, shell gallery, Objects, core sample, Machine, Terminate, lock, sleep |
| Networking | `net/*.mx`, bridge in `net/netapp.mx` | RTL8139, ARP reply, IPv4, ICMP echo, UDP, DHCP, TCP server, HTTP |
| PCI, USB, audio | `net/hardware.mx`, `net/hci_usb.mx`, `net/audio.mx` | `docs/hardware.md` |

## Syscall ABI

A program writes the number and `arg0` to a fixed mailbox, then raises `int 0x80`. No registers
carry arguments, because Mort's `asm()` cannot bind operands.

| Address | Field | Direction |
|---|---|---|
| `0x009F0000` | syscall number | to kernel |
| `0x009F0004` | arg0 | to kernel |
| `0x009F000C` | return value | to program |
| `0x009F0010` | program entry (kernel-internal) | kernel only |
| `0x009F0100` | syscall 4 line buffer, 120 chars + NUL | to program |

| # | Call | Argument | Returns |
|---|---|---|---|
| 1 | Print and newline | string pointer | none |
| 2 | Print inline | string pointer | none |
| 3 | Uptime | none | seconds |
| 4 | Read line, polling PS/2 | none | pointer to `0x009F0100` |

Unknown numbers are ignored. Programs load at `0x00A00000`, are entered by a plain `call`
(`exec_enter`, `kmain.mx:1890`), and run in ring 0 on the kernel stack. There is no exit
syscall (a program returns), no argv, no file I/O, no exit status.

## Build pipeline

`build.py` compiles each piece with the Mort compiler and Zig.

1. The Mort compiler comes from `$MORT_HOME`, else `../Mort`, else a fresh
   `git clone --depth 1` of Mort's default branch into `.mort/` (`build.py:32-44`). The version
   is not pinned.
2. `net/*.mx` (sorted) plus `kmain.mx` are concatenated into one translation unit and passed to
   `mortc.compile_to_c(..., freestanding=True)`, giving `build/kmain.c` (`build.py:109-122`).
3. `zig cc` compiles C with `-mno-sse -mno-sse2 -mno-mmx -O2` and assembles `boot.s` and `idt.s`.
4. Link with `linker.ld` into `build/kernel.elf`.
5. The ISO path downloads Limine (`v8.x-binary` branch) and xorriso (`master` branch) as Windows
   `.exe` files into `tools/`, so `iso` and `run-iso` work only on Windows (`build.py:219-271`).
6. `programs/*.mx` are built the same way, linked at `0x00A00000` and `objcopy`'d to `.bin`
   (`build_program`, `build.py:274`), then seeded once into `build/disk.img` by `ensure_disk`.

## How to build, boot and test

Requirements: `uv`, git, QEMU (`C:\Program Files\qemu\qemu-system-i386.exe` is found
automatically). One-command build and boot, tested from a clean worktree:

```bash
uv run --no-project --with ziglang --with cryptography python build.py run-iso
```

| Command | Purpose |
|---|---|
| `python build.py check` | Build and validate the multiboot ELF |
| `python build.py run` / `window` | Build, boot `-kernel` with a disk (GUI window) |
| `python build.py iso` / `run-iso` | Build, and boot, the Windows-built ISO |
| `python test.py smoke` | Boot and shell basics |
| `python test_fs.py` | Disk stack and persistence |
| `python test_exec.py` | Compiled programs |
| `python test_gfx.py` | ISO Borehole interface by screendump |
| `python test_serial.py` | COM1 console, on the text and ISO paths |

The harnesses other than `test_serial.py` type through the QEMU monitor (`sendkey`) and read VGA
memory (`memsave`), or screendumps in `test_gfx.py`. `test_serial.py` drives the shell over COM1,
the 16550 UART console in `kmain.mx`.

Serial boot tests must not write several bytes at once to QEMU's stdio backend on Windows. That
backend drops a byte instead of waiting when the guest's receive FIFO is at its trigger level, and
it can outrun a halted guest, so a one-shot write loses bytes. Pace stdio input byte by byte, as
`test_serial.py` does. The backend also strips CR, so stdio lines end in LF.

A TCP serial port does not make large bursts safe. The kernel drains the UART even when its
512-byte receive ring is full, so TCP backpressure never reaches the sender, and a burst over about
512 bytes can lose bytes. Measured: a single 1,080-byte TCP write ran 21 of 40 lines with
`ring-lost 438`, while 540 bytes was fine. Pace the sender, or wait for the prompt after each
command. The `serial` command counts what was dropped.

On low-memory machines cap QEMU. With only `-m 256`, a run reached a 1.4 GB working set on this
Windows host; the audit runs added `-m 256 -accel tcg,tb-size=32`. The test scripts have no
option for this today.

## Two kernel copies

`MortOS` (this repo) is authoritative. `Mort/kernel` is a stale snapshot; see the drift section
of [`ROADMAP.md`](ROADMAP.md).
