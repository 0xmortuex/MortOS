# Canonical Vex on MortOS

The goal is to run the canonical
[`0xmortuex/Vex`](https://github.com/0xmortuex/Vex) application on MortOS with
its current renderer, CSS, JavaScript, behavior, and Chromium web content. A
look-alike written against the old kernel framebuffer does not satisfy this
goal.

The audited application baseline is Vex 2.28.1 at commit `1b10ec5`. Its entry
point is `src/main.js`; its package starts Electron directly. The current
Windows package is only one host build. MortOS will become another host target:
`x86_64-mortos`.

## What “the actual Vex” means

- The canonical Vex repository remains the application source of truth.
- `src/renderer/**`, including the existing HTML, CSS, and JavaScript UI, is
  loaded rather than redrawn in Mort kernel UI code.
- Real Chromium renderer processes display pages and execute web content.
- Vex's Electron main/preload/renderer separation and IPC security boundaries
  are preserved.
- MortOS-specific work belongs below Vex, in the OS, C library, Node, Chromium,
  and Electron ports. Application changes are limited to platform build
  support or genuinely platform-specific behavior.
- The old `net/browser.mx` implementation is a compatibility prototype, not
  the canonical browser.

## Current verified foundation

`python build.py check64` builds two related artifacts:

- `build/x86_64/kernel64.elf`: a genuine x86-64 ELF64 kernel payload whose
  entry calls Mort-generated code.
- `build/x86_64/kernel.elf`: the small ELF32 Multiboot trampoline required by
  QEMU's direct loader, with the ELF64 payload embedded at 2 MiB.

`python test_x86_64.py` boots the image, enables PAE and long mode, installs an
identity map, crosses the 32-to-64-bit boundary, and verifies serial output
from `arch/x86_64/kernel64.mx`. It also loads four independently linked Mort
ELF64 executables into different page-table roots, assigns PIDs, dispatches
them at ring 3, exercises SYSCALL/SYSRET, rejects a supervisor pointer, and
continues scheduling after containing a deliberate user page fault. A PIT IRQ
also preempts and resumes non-cooperative user work from a complete register
context while driving the monotonic clock.

The same build locates a clean canonical Vex checkout at commit `1b10ec5`
(override with `MORTOS_VEX_SOURCE`), packages its real Electron application
files into deterministic VexFS, verifies every file digest, and embeds the
result in the kernel payload. The boot test opens and reads the real Vex
`package.json` from ring 3 and confirms version 2.28.1 with `src/main.js` as
the entry point. This makes the canonical source available to the future
Electron runtime; it does not claim that Electron is running yet.

This is only the architectural bootstrap. It does not yet run Vex.

## Port layers

| Layer | Required result | Status |
| --- | --- | --- |
| 64-bit architecture | Long-mode boot, page tables, 64-bit Mort entry | Boot-tested foundation |
| Kernel isolation | GDT/TSS/IDT, NX, ring 3, supervisor/user page protection, user-fault containment | Boot-tested across distinct process roots |
| Process runtime | Validating ELF64 ET_EXEC loader, W^X PT_LOAD mappings, demand-paged heap, lazy 1 GiB mmap arena, anonymous/file-backed `mmap`/`mprotect`/`munmap` with executed RW→RX JIT transition, shared-address-space tasks with PID/TID identity, futex wait/wake/deadlines, blocking thread join and scheduler-slot reclamation, descriptor tables with `fcntl` nonblocking/cloexec control, bounded pipe IPC, eventfd counters, blocking/timed `poll` and `epoll`, interruptible idle, cooperative and PIT-preemptive full contexts, terminal address-space reclamation | Boot-tested foundation; transferable handles and richer IPC next |
| MortOS ABI | Stable syscalls for files, memory, time, networking, graphics, input, audio, and entropy | File/memory/thread IPC, CMOS-anchored realtime plus monotonic clocks, fail-closed hardware `getrandom`, and RTL8139 PCI/DMA Ethernet with real ARP, IPv4/UDP/DHCP, bounded compressed-name DNS, and a validated TCP three-way handshake boot-tested; socket API and remaining device APIs in progress |
| C/C++ platform | System V `argc`/`argv`/`envp`/auxv startup, freestanding constructors, C allocation, C++ `new`/`delete`, atomics, FS-base TLS, thread-local errno, stack canaries, protected pthread create/join with prompt stack/TLS reclamation, futex-backed mutexes/conditions/read-write locks/POSIX semaphores with absolute timed waits, `pthread_once`, per-thread keys and exit destructors, realtime/monotonic clocks and scheduler-backed sleep, installed `poll`/`epoll`/`eventfd` interfaces, then LLVM target, full libc/libc++, build tools | Reusable headers, `crt1.o`, and `libmortos.a` sysroot boot-tested; full platform in progress |
| Application filesystem | Deterministic, hash-verified packaging and read-only access to the canonical Vex Electron tree | 159-file VexFS image, normalized relative lookup, hierarchy metadata, directory enumeration, and private file mappings boot-tested |
| Node/V8 | V8 JIT permissions, libuv event loop, Node filesystem/network/process APIs | JIT memory, pthread/timers/event-loop foundation, bidirectional Ethernet, ARP, DHCP, DNS A-record resolution, and a real TCP three-way handshake are boot-tested; stateful POSIX sockets and the full Node build remain |
| Chromium | Sandbox, renderer/GPU processes, Skia, fonts, image/media codecs, TLS/PKI, accessibility | Planned |
| Electron | `x86_64-mortos` host integration, windows/views, sessions, IPC, clipboard, dialogs, downloads | Planned |
| Canonical Vex | Build and run the upstream application tree, then pass its tests and UI comparisons | Planned |

## Audited Vex platform surface

The current main process imports Electron's `app`, `BrowserWindow`, `session`,
`ipcMain`, `protocol`, `globalShortcut`, `Menu`, `net`, `shell`, `dialog`,
`webContents`, `safeStorage`, and `clipboard` services. It additionally uses
desktop capture, screen/work-area information, `WebContentsView`, Widevine
components, and Electron Updater.

Its Node surface includes filesystem and path APIs, URLs, cryptographic random
data, TCP/TLS networking, child processes, ZIP handling, QR generation, and
package persistence. Renderer pages depend on Chromium DOM/CSS/JavaScript,
`<webview>`, preload scripts, context isolation, and IPC bridges.

This audit is why the port is staged below the application. Replacing only
`BrowserWindow` or copying the renderer assets would not provide the same
browser.

## Acceptance gates

The canonical port is complete only when all of these are true:

1. MortOS boots the 64-bit kernel on QEMU and supported physical x86-64
   hardware.
2. ELF64 ring-3 programs run in isolated address spaces and survive fault
   containment tests.
3. The C/C++ runtime passes its conformance subset and Node/V8 pass their
   platform tests.
4. Chromium's multiprocess browser, renderer, network, and GPU/software
   compositor paths run on MortOS.
5. The canonical Vex tree starts through the MortOS Electron target.
6. Vex's own automated tests pass on MortOS.
7. Reference screenshots and interaction tests match the same Vex revision on
   the existing desktop build, allowing only font rasterization and
   hardware-dependent media differences.
