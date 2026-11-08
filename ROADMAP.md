# MORT OS roadmap

Audited 2026-11-08 at commit `83ae7eb`, with the Mort compiler at `c17f6fe` (0.137.0, cloned
fresh by `build.py`). Every entry cites a command that was run or a file that was read. Host:
Windows 11, QEMU at `C:\Program Files\qemu\qemu-system-i386.exe`.

Audit method note: QEMU was always capped at 256 MB, headless, one at a time, with a watchdog.
The repo's scripts ran unmodified. An out-of-tree wrapper added `-m 256 -accel tcg,tb-size=32`
to the QEMU they spawn. The `run-iso` command ran through a PATH shim that forced `-display none`
and a time limit, so its normal GUI window was not exercised.

## Exit criteria status

| | Criterion | Status | Measured evidence |
|---|---|---|---|
| a | Boots in QEMU from a clean checkout with one command | **Pass** | Fresh worktree: `uv run --no-project --with ziglang --with cryptography python build.py run-iso`. Exit 0, 79.3 s total, of which 35.3 s was the capped QEMU run (about 44 s to build, including cloning Mort and downloading Limine and xorriso). Nothing undocumented was needed |
| b | Reaches a shell | **Pass** | The ISO boots to the launcher (screendump). Enter on Terminal gives a prompt; `echo iso-shell-ok`, `ls /bin`, `uptime` and `hello` all ran there. The `-kernel` path goes straight to the prompt |
| c | Runs 5+ userland programs | **Fail: 3 of 5** | `programs/` holds `hello`, `count`, `ask`. All 3 ran in a real boot (`test_exec.py` 11/11; `hello` and `count` by bare name). The other 38 commands are shell builtins |
| d | Automated boot tests that script shell commands and assert on serial output | **Fail** | Tests exist but use QEMU `sendkey` and VGA `memsave`. A 35 s boot with `-serial file:` wrote 0 bytes. No UART code in `boot.s`, `idt.s`, `kmain.mx` or `net/*.mx` |
| e | CI green running those boot tests | **Fail** | `gh run list -R 0xmortuex/MortOS -L 5` is empty, the API reports `total_count: 0`, and the repo has no `.github/`. Only Mort's CI touches this repo: job `MORT OS builds and boots` (success in run 42484439164) runs `python test.py smoke`, which is 4 checks |
| f | Docs: README quickstart, contributor guide, CHANGELOG | **Partial: 1 of 3** | README quickstart was followed and works. No `CONTRIBUTING*` or `CHANGELOG*` exist |

### Test harness results

| Command | Result |
|---|---|
| `python test.py smoke` | 4/4 passed |
| `python test_fs.py` | 22 passed, 0 failed |
| `python test_exec.py` | 11 passed, 0 failed |
| `python test_gfx.py` | **5 passed, 4 failed** (exit 1) |

The four `test_gfx.py` failures are the top-bar tab checks (`test_gfx.py:109,127,134,140`). They
assert a tab UI that the kernel no longer draws (`draw_tab` is unused, `kmain.mx:453`), so the
test is stale and the desktop is not broken. Separately, the `help` that test types goes to the
launcher, which ignores letters; only its Enter takes effect (`launcher_on_key`,
`kmain.mx:3398`). So the "console glyphs" check sees the banner, not `help` output.

## Kernel feature matrix

"Measured" means observed in a boot during this audit. "Read" means established from source.

| Feature | Status | Evidence |
|---|---|---|
| GDT | Works | `idt.s:17-26`, 3 flat ring 0 descriptors. Every boot depends on it |
| IDT and interrupts | Works | `idt.s:78-114`. Measured: `crash` prints `*** CPU EXCEPTION #6 -- HALTED ***`. Exceptions are never recoverable |
| Physical memory manager | Missing | Read: no frame allocator. The multiboot map is only summed for `mem`. The heap base is hardcoded to 16 MiB (`kmain.mx:1043`) |
| Paging, virtual memory | Missing | Read: no `cr0` or `cr3` anywhere in `*.mx`, `*.s` |
| Kernel heap | Partial | `kmalloc`/`kfree`, `kmain.mx:1062,1098`. Measured: `memtest: PASS`, heap 239 MB. `memtest` is the only caller. Coalescing is forward-only |
| Timer | Partial | PIT at 100 Hz, `kmain.mx:2609`. Measured: `uptime` went 5 s to 8 s across a 12 s blocked program, so ticks are lost while commands run |
| Preemptive scheduler | Missing | Read: `on_tick` only counts and redraws the clock |
| Processes and threads | Missing | Read: no task structures. One synchronous program. Measured: `ps` gives `unknown command` |
| Syscall interface | Partial | `int 0x80` with a mailbox, 4 calls (`kmain.mx:1864`). Measured via `test_exec.py`. No file I/O, exit, or spawn |
| IPC | Missing | Read: nothing in source |
| Keyboard | Works | PS/2 on IRQ1. Measured in every harness. US layout, no Caps Lock |
| Serial | Missing | Measured: 0 bytes on COM1 |
| Framebuffer console | Works | Measured on the ISO: `iso_term` screendump shows the desktop and shell. `test_gfx.py` non-tab checks pass. Fixed 1024x768 layout |
| Block driver | Works | ATA PIO, polled (`kmain.mx:1198,1220`). `test_fs.py` persistence checks pass |
| Filesystem (read, write, directories) | Partial | Measured: `write`, `cat`, `mkdir`, `ls`, `rm`, `rmdir`, reboot persistence. Limits (read): `write` only appends, `rm` never reclaims, 64 entries, 64 KiB files |
| Executable loader | Partial | Flat binary at a fixed address, 64 KiB, one at a time (`kmain.mx:1896`). No ELF, no arguments |
| Ring 3 with separation | Missing | Read: no user GDT entries, no TSS, gates are DPL 0, programs enter by `call` on the kernel stack (`kmain.mx:1890`) |
| libc-equivalent in Mort | Missing | Read: each program re-declares `sys_print` by hand. `memset` and friends are in C |
| Shell: `ls`, `cat`, `echo` | Works | Measured |
| Shell: pipes | Missing | Measured: `echo hello \| cat` printed `hello \| cat` |
| Shell: `ps`, `kill` | Missing | Measured: `unknown command` |
| Editor | Missing | Measured: `edit foo` gives `unknown command`; none in source |
| NIC driver | Works | RTL8139, polled. Measured with `-device rtl8139`: DHCP lease |
| ARP | Partial | Replies only; `arp_build_request` is unused (read). Cannot resolve a peer itself |
| IP | Partial | Measured through DHCP and HTTP. No fragments, no routing, gateway not stored (read) |
| UDP | Partial | Used only for DHCP (read). No socket API |
| TCP | Partial | Measured: `curl` got `200 OK`, 721 bytes, twice. It is one server connection inside `net_httpd`: no retransmit, no RST, receive checksums unchecked (read) |

## Language features the OS needs

Tested by compiling snippets with `mortc.compile_to_c(..., freestanding=True)`.

| Gap | Measured result | What it blocks | Workaround today |
|---|---|---|---|
| `asm()` operand binding, outputs and clobbers | `asm("...", x)`: `expected ')', got ','`. Colon constraints: `expected ')', got ':'`. Grammar takes one string (`parser.py:449-455`) | CR3/CR0 access, context switch, register-based syscalls, `ltr`, `rdtsc` | Move values through a fixed address: `asm("movl 0x9F0020, %eax; movl %eax, %cr3")` compiles, but the `%eax` clobber is undeclared, so it needs an isolated function like `exec_enter` |
| Naked or interrupt functions | `@interrupt` and `naked fn` rejected | Moving ISR stubs and `iret` paths out of `idt.s`; context-switch entry; ring 3 entry | Keep the stubs in assembly |
| `volatile` access | `volatile` and `read_volatile` rejected. `*(addr as *u32)` emits a plain C dereference (`build/hello.c`). The only `volatile` in `build/kmain.c` is on inline asm | Reliable MMIO, DMA and ISR-shared state; scheduler run queues | Works at `-O2` today, with no guarantee (ordinary memory access around `asm`) |
| Packed layout, alignment, sections | `@packed`, `@align(4096)`, `@section` rejected | Declaring GDT, IDT, TSS, page tables and packet headers as types | Raw offsets (the kernel's current idiom; it declares no structs) and allocation at aligned physical addresses |
| Unmangled definitions | `@export` rejected; definitions emit `mort_` names | Rewriting `runtime.c` in Mort, since the C compiler calls plain `memset` | Keep `runtime.c` |
| Pointer ergonomics | `p + 1` on `*u32` and `p.a` through a pointer rejected. No `usize` | Nothing outright; slows every driver | `(*p).a` and integer casts (148 lines of `kmain.mx` contain `as u64`) |
| Atomics | `atomic_add` undefined | SMP only | `cli`/`sti` on one CPU |
| `import` through `compile_to_c` | `imports require file-based compilation` | Splitting the kernel through the path `build.py` uses | Concatenation in `build.py`. The file-based `mortc` path was not tested |

These already work and need no compiler change: `outb/inb/outw/inw/outl/inl`, function pointers,
`extern fn`, and taking a function's address (`(&g) as u32`, which emits `(uintptr_t)(&mort_g)`).
So serial, physical memory management and the GDT/IDT/PIC setup code in Mort are not blocked by
the language.

## Kernel copy drift

`git diff --no-index --ignore-space-at-eol`, `MortOS` compared with `Mort/kernel`:

| Item | Result |
|---|---|
| Ahead | **`MortOS`, by a wide margin** |
| `kmain.mx` | 3,629 lines here, 1,900 in Mort: 1,790 lines absent from Mort, 61 only in Mort |
| `build.py` | 109 lines only in Mort, 150 only here |
| `mkfs.py` | 17 / 27 |
| `test.py`, `test_exec.py`, `test_fs.py`, `test_gfx.py` | 4/3, 5/6, 6/9, 1/1 |
| `font_data.mxinc` | 6 lines only here |
| Identical (ignoring line endings) | `boot.s`, `idt.s`, `linker.ld`, all of `programs/` |
| Only in `MortOS` | all 18 `net/*.mx`, `runtime.c`, 9 docs |

The last real sync in Mort's history is `89b3cc6` (2026-07-22); the only later commit touching
`kernel/` is a README edit.

## Ranked gaps

Highest impact first, in dependency order. Sizes are rough estimates in hours.

### 1. Serial console (blocks criteria d and e)

- **Missing:** a COM1 driver and a line-oriented console stream.
- **Why:** it is the basis of the scripted boot tests and the only debug output that survives a
  graphics-mode boot.
- **Design:** `put_cell_at` writes cells by position, so it cannot produce a stream. Mirror at
  the `print`/`feed` level. For input, poll the UART in `on_tick`; this needs no new assembly and
  no PIC mask change. Tests must run lock-step (send a line, wait for the prompt), because the
  UART FIFO overflows while a command runs with interrupts off.
- **Size:** 4-8 h. **Depends on:** nothing; `outb`/`inb` exist.
- **Files:** `kmain.mx` (new serial section, `feed`, `print_*`, `on_tick`, `run_command`).

### 2. Serial boot-test suite (criterion d)

- **Missing:** a harness that sends shell commands over serial and asserts on serial output.
- **Why:** replaces per-key `sendkey` and VGA scraping, runs far faster, and covers the ISO path.
  Should also cover networking via `hostfwd`, which no test touches today.
- **Include:** fix the 4 stale `test_gfx.py` checks, and add `-m 256 -accel tcg,tb-size=32`.
- **Size:** 4-6 h. **Depends on:** 1.
- **Files:** new `tests/boot/`, `test.py`, `test_gfx.py`.

### 3. CI in MortOS (criterion e)

- **Missing:** any workflow here, and a pinned toolchain.
- **Why:** Mort's CI runs only 4 smoke checks, and only on Mort's own CI triggers. `build.py` follows
  Mort's default branch, Limine's `v8.x-binary` and xorriso's `master`, so builds are not
  reproducible.
- **Note:** Linux CI can run the `-kernel` path now. The ISO path needs a Windows runner, or a
  Linux path in `iso()`.
- **Size:** 3-5 h. **Depends on:** 2.
- **Files:** new `.github/workflows/ci.yml`, `build.py:32-44,65-66`.

### 4. Program ABI and a Mort userland library (criterion c)

- **Missing:** argv, exit status, file syscalls, and one shared syscall library. Programs copy
  their syscall wrappers by hand.
- **Why:** with 4 syscalls, new programs can only print and read lines.
- **Size:** 6-10 h. **Depends on:** nothing. Fixed-address mailbox stays until 10.
  Multi-file programs need concatenation in `build_program` or file-based `import`.
- **Files:** `kmain.mx:1864`, `build.py:274`, new `programs/lib`.

### 5. Reach 5+ real programs (criterion c)

- **Missing:** at least 2 more executables. Good candidates: `cat`, `ls`, `echo` moved out of the
  builtins, plus `wc`.
- **Size:** 3-5 h. **Depends on:** 4.
- **Files:** `programs/*.mx`, `test_exec.py`.

### 6. Contributor guide and CHANGELOG (criterion f)

- **Missing:** `CONTRIBUTING.md`, `CHANGELOG.md`.
- **Size:** 1-2 h. **Depends on:** better after 2 and 3, so the guide can name the real test
  command.

### 7. One source of truth for the kernel

- **Missing:** a resolution of the two copies. `Mort/kernel` is about 1,790 lines behind.
- **Why:** Mort's CI still builds and packages the stale copy (`ci.yml:97,148,307`), so a green
  check there says little about the real OS.
- **Size:** 1-3 h. **Depends on:** a decision to delete the copy or vendor it; the job at
  `ci.yml:242` already tests the real repo.
- **Files:** `Mort/kernel/`, `Mort/.github/workflows/ci.yml`, `Mort/CLAUDE.md`.

### 8. Fix known memory-safety bugs

- **Missing:** bounds checks on paths and prompts. Reachable overflows are documented in
  `fs_parent_of`, `path_of`, `draw_prompt`, `read_line` and `sudo` (`BACKLOG.md:1043,930,980,881,1292`).
- **Also seen in this audit:** `ls` prints `ui0` instead of `uid  0` for 4-digit sizes (screendump),
  and `cat` of a binary spills across the screen.
- **Why:** with no memory protection, any overflow corrupts the kernel.
- **Size:** 3-5 h. **Depends on:** 2 to guard against regressions.
- **Files:** `kmain.mx:709,1425,1448,1810,2435`.

### 9. Run commands outside the keyboard ISR

- **Missing:** a main loop that takes queued command lines, so commands run with interrupts on.
- **Why:** today commands block interrupts, losing ticks (measured), and `httpd` takes the
  keyboard away permanently. A scheduler cannot exist until this changes.
- **Size:** 4-8 h. **Depends on:** 2 to verify. No language feature, but `volatile` is advisable
  for the queue.
- **Files:** `kmain.mx:3551-3568,3625-3628`, `idt.s`.

### 10. Physical memory manager and paging

- **Missing:** a frame allocator from the multiboot map, then page tables and per-process
  address spaces.
- **Why:** foundation for isolation and for more than one program.
- **Size:** 6-10 h for the allocator, 10-20 h for paging. **Depends on:** 9. **Language:** `asm`
  operand binding (or the mailbox workaround) for CR3; `volatile` strongly advised; alignment by
  placement until an align attribute exists.
- **Files:** `kmain.mx:1041`, `linker.ld`, new paging module.

### 11. Ring 3 and a real syscall boundary

- **Missing:** user GDT entries, TSS, DPL 3 syscall gate, `iret` entry, user-pointer validation.
- **Why:** programs now run in ring 0 and can overwrite the kernel.
- **Size:** 10-16 h. **Depends on:** 10. **Language:** naked or interrupt functions, else more
  assembly; `asm` operands for register-based syscalls.
- **Files:** `idt.s:17-26,69-76`, `kmain.mx:1864-1924`, `programs/pstart.s`.

### 12. Scheduler, processes, threads, `ps`, `kill`

- **Missing:** task structures, context switch, blocking, wait and exit; the two commands.
- **Size:** 20-40 h plus 3-5 h for the commands. **Depends on:** 9, 10, and 11 for user
  processes. **Language:** context switch needs naked functions or assembly; `volatile` for shared
  state.
- **Files:** new scheduler module, `idt.s` timer stub, `kmain.mx:2617`.

### 13. IPC and shell pipes

- **Missing:** kernel pipes, per-process stdin and stdout, parsing `|`.
- **Why:** program output goes straight to the console (`print_inline`, `kmain.mx:1788`), so there
  is nothing to redirect yet.
- **Size:** 8-16 h. **Depends on:** 4, 12.
- **Files:** `kmain.mx:1788,2099-2606`.

### 14. MortFS: reclaim and rewrite

- **Missing:** space reclaim on `rm`, overwrite and truncate, more than 64 entries, files over
  64 KiB.
- **Size:** 8-16 h. **Depends on:** 2. An on-disk format change needs a migration like the v1 to
  v2 path in `fs_init`.
- **Files:** `kmain.mx:1296,1533,1686,1736`, `mkfs.py`.

### 15. Text editor

- **Missing:** any editor.
- **Size:** 6-12 h. **Depends on:** 4 and 14 (needs overwrite, not append).
- **Files:** new `programs/edit.mx`.

### 16. General networking

- **Missing:** ARP requests and table, gateway and DNS from DHCP (requested but discarded), a
  routing decision, receive checksum checks (the `*_verify` functions exist unused), TCP
  connection table, retransmit, RST, NIC interrupts, a socket syscall API.
- **Size:** 20-40 h. **Depends on:** 9, and 12 for blocking sockets. **Language:** `volatile` for
  DMA.
- **Files:** `net/netapp.mx`, `net/netcfg.mx`, `net/rtl8139.mx`, `net/arp.mx`, `net/tcp.mx`.

### 17. Shrink the non-Mort code

- **Missing:** Mort versions of the GDT, IDT fill and PIC remap in `idt.s`, and of `runtime.c`.
- **Why:** this is the project's stated goal, and 312 lines remain outside Mort.
- **Size:** 4-8 h for setup code (`outb` and `&fn as u32` exist; `lgdt` and `lidt` can use a fixed
  address). The ISR stubs stay until the compiler gains naked functions. `runtime.c` needs
  unmangled definitions.
- **Depends on:** 2 to verify.
- **Files:** `idt.s`, `boot.s`, `runtime.c`, `mortc` (language work).

### 18. Compiler work for the OS (schedule alongside 10-12)

In order of value: `asm` operands and clobbers; `volatile` loads and stores; naked or interrupt
functions; packed and aligned layout; unmangled exports; pointer ergonomics. Roughly 20-40 h in
`Mort/mort/{parser,typechecker,codegen}.py`, each with a conformance test and a kernel build
check.

## Earlier notes corrected or confirmed

| Note | Finding |
|---|---|
| 32-bit x86; Limine gives a framebuffer, `-kernel` gives VGA text | Confirmed |
| Four harnesses | Confirmed; `test_gfx.py` fails 4 of 9 |
| ATA PIO + MortFS | Confirmed |
| Flat binaries at `0x00A00000`, `int 0x80`, memory mailbox | Confirmed |
| Shell with history, window-manager layer | Confirmed; the "window manager" is four hardcoded apps with no general window abstraction |
| `asm()` has no operand binding | Confirmed, still true in 0.137.0 |
| README: clean build takes about 10 s with a warm uv cache | Not reproduced: about 44 s here, which included cloning Mort and downloading Limine and xorriso |
