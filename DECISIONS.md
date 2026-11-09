# Decisions

Decisions already made in this project, with the reason as it is recorded and where it is recorded. "Reason not
recorded" means no document or commit message gives one. Nothing here is a new decision.

## Boot and display

| # | Decision | Reason as recorded | Recorded in |
| --- | --- | --- | --- |
| 1 | Two boot paths. The Limine ISO (`build.py run-iso`) gives a 1024x768x32 framebuffer and the Borehole interface. QEMU `-kernel` (`build.py run` and the test harnesses) gives 80x25 VGA text and a shell prompt | Limine provides the framebuffer, and QEMU ignores the graphics request on `-kernel`, so the kernel falls back to VGA text there, "which is why the text-driven tests above still work". The ISO is built to be written to a USB stick, "not just QEMU's `-kernel` shortcut"; that is tested in QEMU only | `ARCHITECTURE.md` "Boot flow", `README.md` "What it does" and "Running programs", `ROADMAP.md` "Earlier notes" |

## Console and testing

| # | Decision | Reason as recorded | Recorded in |
| --- | --- | --- | --- |
| 2 | A COM1 serial console: a polled 16550 at `0x3F8`, 115200 8N1, carrying console output and shell input | "It is the basis of the scripted boot tests and the only debug output that survives a graphics-mode boot" | `ROADMAP.md` gap 1, `README.md` "Build & run", commit `b91ff0b` |
| 3 | Serial tests run in lock-step: send a line, wait for the prompt | The UART FIFO overflows while a command runs with interrupts off. Input bursts can lose bytes | `ROADMAP.md` gap 1, `ARCHITECTURE.md` "How to build, boot and test", commit `74258f5` |

## Programs

| # | Decision | Reason as recorded | Recorded in |
| --- | --- | --- | --- |
| 4 | Programs are flat binaries, up to 64 KiB, loaded one at a time at `0x00A00000` | Reason not recorded. `docs/architecture.md` points to `docs/memory-map.md` for why not `0x01000000`; that file records only that the heap starts there, above the program load area | `ARCHITECTURE.md` "Memory map" and "Syscall ABI", `docs/memory-map.md`, `programs/prog.ld` |
| 5 | Syscalls use `int 0x80` with arguments in a mailbox at `0x009F0000`, not registers | Mort's `asm()` takes one string and cannot bind operands | `ARCHITECTURE.md` "Syscall ABI", `BLOCKERS.md` "Language gaps", `README.md` "What it does", commit `ae13232` |
| 6 | `runtime.c` stays in C and the ISR stubs stay in `idt.s` | The compiler has no unmangled definitions for `memset` and friends, and no naked or interrupt functions | `BLOCKERS.md` "Language gaps", `ROADMAP.md` gap 17 |

## Storage

| # | Decision | Reason as recorded | Recorded in |
| --- | --- | --- | --- |
| 7 | ATA PIO on the primary master, polled, LBA28, no IRQs | ATA IRQ14 is masked at the PIC, and polling PIO does not need interrupts. Why PIO was chosen over DMA: reason not recorded | `docs/fs-design.md` section 1, `ARCHITECTURE.md` "Modules" |
| 8 | MortFS has at most 64 entries | 64 x 64 B fills exactly 8 sectors of table, and 64 lines of `ls` is already 2.5 screens at 80x25 | `docs/fs-design.md` section 2.4, `BLOCKERS.md` |
| 9 | MortFS files are at most 64 KiB, each in a fixed 128-sector extent from a bump pointer | 64 KiB equals the fixed file I/O buffer. Fixed extents make append safe and remove fragmentation logic | `docs/fs-design.md` sections 2.4 and 2.5 |
| 10 | `rm` does not reclaim space. Re-running `mkfs.py` compacts | "A deliberate v1 trade: reclamation is the single biggest source of filesystem bugs, and the whole FS state fits in two fixed buffers as-is" | `docs/fs-design.md` section 2.6, `README.md` "Roadmap" |

## Networking

| # | Decision | Reason as recorded | Recorded in |
| --- | --- | --- | --- |
| 11 | The only NIC driver is RTL8139, run under QEMU | Reason not recorded. The README states that QEMU emulates one, but does not give that as the reason | `README.md` "Networking", `docs/networking.md`, commit `6f57f8c` |

## Process model

| # | Decision | Reason as recorded | Recorded in |
| --- | --- | --- | --- |
| 12 | No scheduler, ring 3 or paging so far. Programs run to completion, one at a time, in ring 0 | Commands run inside the keyboard ISR, and "a scheduler cannot exist until this changes". The roadmap orders the work as commands out of the ISR, paging, ring 3, scheduler. A context switch needs naked functions or assembly | `BLOCKERS.md` "Process model", `ROADMAP.md` gaps 9 to 12, commit `ffaca90` |
| 13 | Shell commands, programs and disk I/O run inside the keyboard ISR, with interrupts off | Reason not recorded. The lost timer ticks are recorded as "accepted for v1" | `ARCHITECTURE.md` "Execution model", `docs/fs-design.md` section 1 |

## Interface

| # | Decision | Reason as recorded | Recorded in |
| --- | --- | --- | --- |
| 14 | The Borehole interface replaced the old GUI: launcher, wallpaper, top bar, framed windows, Files UI, Vex page, F-key switching and Settings UI | Reason not recorded. The documents describe Borehole, but not why the old interface was replaced | `docs/borehole-concept.md`, commits `95770a7` and `5c51c57` |

## Build and source

| # | Decision | Reason as recorded | Recorded in |
| --- | --- | --- | --- |
| 15 | The Mort compiler is pinned by `MORT_COMMIT`, not tracked from Mort's main branch | "So builds are reproducible" | `build.py`, `README.md` quickstart, `ROADMAP.md` gap 3, commit `cb18db2` |
| 16 | This repo is the authoritative kernel, and `Mort/kernel` is a stale snapshot. Whether to delete or vendor that copy is still open | This repo is ahead by a wide margin (`kmain.mx` 3,629 lines against 1,900 when measured). Otherwise reason not recorded | `ARCHITECTURE.md` "Two kernel copies", `ROADMAP.md` "Kernel copy drift" and gap 7 |
