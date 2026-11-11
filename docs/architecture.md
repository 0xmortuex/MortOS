# MORT OS — Architecture

How the pieces fit together, from power-on to the running shell. This is a
map for navigating the source, not a spec — where behavior is detailed
elsewhere ([`docs/memory-map.md`](memory-map.md), [`docs/shell.md`](shell.md),
[`docs/networking.md`](networking.md), [`docs/fs-design.md`](fs-design.md)),
this document links out instead of repeating it.

## Boot chain

MORT OS never leaves 32-bit protected mode — there is no long-mode/64-bit
transition anywhere in the source. Two boot paths exist, both landing in the
same kernel entry point:

1. **`qemu-system-i386 -kernel`** (the `-kernel` shortcut used by `test.py`,
   `test_fs.py`, `test_exec.py`): QEMU's built-in Multiboot1 loader reads the
   header in `boot.s:19-30`, loads the kernel at 1 MiB already in 32-bit
   protected mode, and jumps to `_start`. It ignores the header's graphics
   request (`boot.s:23-30`), so the kernel falls back to VGA text mode.
2. **The Limine ISO** (`build.py iso` / `run-iso`): Limine honors the
   graphics request and hands the kernel a linear framebuffer, which
   `fb_init()` (`kmain.mx:347-366`) detects via the multiboot info struct's
   bit 12 (`kmain.mx:349`) and 32-bpp direct-RGB check (`kmain.mx:352-355`).

From `_start` (`boot.s:39-51`):

1. `mov $stack_top, %esp` sets up a 16 KiB stack (`boot.s:34-37`).
2. `call kernel_setup` (`idt.s:50-54`) does three things in order:
   `load_gdt` installs a flat null/code/data GDT (table at `idt.s:17-26`,
   loaded and CS/segment-registers reloaded at `idt.s:56-66`), `remap_pic`
   moves the two 8259 PICs off their real-mode vectors to `0x20`/`0x28` and
   masks everything except IRQ0 (timer) and IRQ1 (keyboard)
   (`idt.s:116-135`), and `load_idt` fills 256 gates — the 32 CPU exception
   stubs (`isr_table`, `idt.s:40-44`), the keyboard gate at vector `0x21`
   (`idt.s:98-101`), the timer gate at `0x20` (`idt.s:103-106`), and the
   syscall gate at `0x80` (`idt.s:108-111`) — then `lidt`s it (`idt.s:113`).
3. `push %ebx; call mort_kmain` hands the multiboot info pointer (left in
   `%ebx` by the bootloader) to `kmain(mbinfo)` in `kmain.mx:3763`.
4. If `kmain` ever returns, `_start` does `cli; hlt` in a loop rather than
   running off into undefined memory (`boot.s:47-50`).

`linker.ld` places `.multiboot` first (so it lands in the required first
8 KiB) and everything else after, with the whole image based at 1 MiB
(`linker.ld:8-13`) — the address `docs/memory-map.md` calls the kernel load
address.

## Build pipeline (`build()`, `build.py:139-190`)

Before any of the above can boot, `python build.py build` (or `check`/`run`)
turns the Mort source into the multiboot ELF that the boot chain loads:

1. **Concatenate, then compile to C.** `kmain.mx` isn't compiled alone —
   `build()` first reads every `net/*.mx` and `ui/*.mx` file (sorted, so
   output is deterministic) and prepends that combined source to `kmain.mx`
   before handing the whole thing to `mortc.compile_to_c(..., freestanding=True)`
   as **one translation unit** (`build.py:143-157`). Mort emits forward
   prototypes, so it doesn't matter that these files are compiled before the
   `kmain.mx` code that calls into them.
2. **Cross-compile to 32-bit x86.** The generated C is compiled for
   `x86-freestanding-none` (`build.py:79`) via Zig's C compiler
   (`_zig()`, `build.py:130-136` — the reason `pip install ziglang` is a
   build requirement). Two flags are load-bearing rather than cosmetic:
   `-ffreestanding`/`-fno-builtin` (no hosted libc — see step 3) and
   `-mno-sse -mno-sse2 -mno-mmx` — the kernel runs with SSE disabled
   (`CR4.OSFXSR=0`), and at `-O2` the compiler can otherwise vectorize a
   `memset`/zero-init into an `xorps` instruction, which would fault
   (`#UD`) on real hardware; forbidding vector codegen keeps the network
   buffers scalar (`build.py:162-167`).
3. **Link in the freestanding runtime.** `runtime.c` (repo root) supplies
   `memset`/`memcpy`/`memmove` — the primitives the optimizer reaches for
   when lowering Mort array initialization or copies — since MortOS links
   no hosted C library (`runtime.c:1-4`). It's compiled and linked into the
   kernel exactly like `kmain.c`, `boot.s`, and `idt.s` (`build.py:174-189`).
4. **Link into the multiboot ELF.** `boot.o`, `kmain.o`, `runtime.o`, and
   `idt.o` are linked `-nostdlib -static -no-pie` with `linker.ld`
   (`build.py:183-189`) into `build/kernel.elf` — the file the boot chain
   above actually boots. `python build.py check` then re-parses that ELF's
   header to confirm it's a valid 32-bit multiboot image before reporting
   success (`check()`, `build.py:193-225`).

`check()` does more than a one-line magic-number check. Its internal
`require()` closure raises via `sys.exit` rather than `assert`, specifically
so the checks can't be silently skipped by running under `python -O`
(`build.py:199`-`201`). It confirms the ELF magic bytes, that the ELF class
is 32-bit (`ELFCLASS32`, `data[4] == 1`), and that `e_machine` is `EM_386`
(`0x03`, `build.py:203`-`206`); then it scans every 4-byte-aligned offset in
the first 8 KiB of the file for the multiboot magic `0x1BADB002` — the
alignment and 8 KiB bound are what the multiboot spec itself requires, and
once a candidate is found it validates the *whole* 12-byte header rather
than just the magic word: `flags` must be exactly `0x7`
(`ALIGN|MEMINFO|GRAPHICS`, the same three bits `boot.s:8`-`11` sets) and
`magic + flags + checksum` must wrap to zero mod 2^32 (`build.py:208`-`222`).
It prints the file offset the header was found at, then suggests
`python build.py run`.

`programs/*.mx` go through the same four-step recipe but linked
differently (a fixed load address, no kernel symbols) — see
[`docs/programs.md`](programs.md)'s build pipeline section for that path.

## Kernel entry (`kmain`, `kmain.mx:3763-3809`)

In order: `heap_init()` carves the dynamic-memory heap out of high RAM,
`fb_init()` looks for a framebuffer, `serial_init()` (COM1 — everything
printed from here on is mirrored to it, see [`docs/testing.md`](testing.md)),
`fs_init()`/`fs_ensure_layout()`/`fs_populate_bin()` mount MortFS and seed
`/bin /etc /home /var` on a fresh disk, `acct_init()`/`ensure_home()`/
`login_default()` build the two built-in accounts (`root` and `mortuex`)
and auto-log-in as the latter — see [`docs/accounts.md`](accounts.md) —
`run_script(1)` runs the boot script from a multiboot module if one was
passed in, and the prompt is drawn. Only after all of that does `kmain` call
`usb_boot_init()` (a one-shot, polling-only UHCI enumeration — see
[`docs/hardware.md`](hardware.md)), `init_pit()` (arms the ~100 Hz PIT on
IRQ0), and optionally `ui_start()` on the graphics path. Everything up to
this point runs with interrupts off.

`kmain` then enters its final loop (`kmain.mx:3800-3808`), which is not a
bare `hlt` forever — each iteration re-enables interrupts just long enough
to admit one pending IRQ (`asm("sti; hlt")` when no serial byte is waiting,
so a keyboard or timer IRQ can still fire and wake it; `asm("sti; nop; cli")`
instead when `serial_pending()` is true, so the loop doesn't block on `hlt`
waiting for a hardware IRQ that may not come), disables them again, and
calls `serial_service()` (`kmain.mx:710-714`, whose own header comment states
it runs "from the idle loop with interrupts off, the same context `on_key`
runs commands in") to drain up to 8 buffered COM1 bytes into the shell
before looping. Keyboard and timer IRQs still do their real work inside
their own ISRs; COM1 input is drained by this polling loop rather than a
UART IRQ of its own.

## Execution model: no scheduler, no processes

There is no scheduler, no task list, and no preemption anywhere in this
codebase — the repo has exactly one flow of control besides interrupts.
Shell and UI state lives in global variables at the top of `kmain.mx`
(e.g. `g_row` at `kmain.mx:10`, `g_uid` at `kmain.mx:25`, `g_gfx` at
`kmain.mx:62`), and four interrupt sources drive all behavior once
`kmain`'s main loop starts admitting interrupts (see Kernel entry above —
it's a repeating `sti`/`cli` toggle now, not a single one-time `sti`):

- **IRQ1 (keyboard)** → `keyboard_isr` (`idt.s:137-145`) → `mort_on_key` →
  `on_key()` (`kmain.mx:3688`), a thin wrapper that reads the scancode off
  port `0x60` and hands it to `key_event(sc)` (`kmain.mx:3692`), which does
  the actual work: in graphics mode it offers the scancode to `ui_on_key()`
  first; keys the interface doesn't take reach the shell's scancode-to-ASCII
  path. `key_event()` has a second caller too — `serial_service()`
  (`kmain.mx:735`) feeds it bytes decoded from COM1, so a command typed over
  the serial line runs through the exact same function as one typed on the
  keyboard.
- **IRQ0 (timer, ~100 Hz)** → `timer_isr` (`idt.s:147-155`) → `mort_on_tick` →
  `on_tick()` (`kmain.mx:3458-3463`), which bumps `g_ticks` (backs the
  `uptime` command) and, in graphics mode, calls `ui_tick()`, which drives
  the interface's motion and clock; see [The Borehole interface](#the-borehole-interface)
  and [`docs/settings.md`](settings.md) for the RTC read's caveats.
- **`int 0x80` (syscall)** → `syscall_isr` (`idt.s:170-174`) → `on_syscall()`
  (`kmain.mx:2574`), described below.
- **CPU exceptions (vectors 0-31)** → each vector gets its own stub
  (`ISR_STUB`, `idt.s:180-184`) that pushes the vector number and jumps to
  a shared `isr_common` (`idt.s:219-226`), which `cli`s, calls
  `on_exception(vec)` (`kmain.mx:3468-3484`), then `hlt`s in an infinite
  loop. Unlike the three sources above, this path never returns — no
  `iret`, no end-of-interrupt — so a fault is unrecoverable; only a reboot
  clears it. `on_exception` reports the raw vector number on the VGA console's last
  row, or as a red band across the bottom of the screen in graphics mode
  (`ui_fault`, whatever scene is up), not a per-vector fault name: the `crash` shell command's `ud2` (`kmain.mx:3410`,
  vector 6, `#UD`) prints `*** CPU EXCEPTION #6 -- HALTED ***`, not
  "Invalid Opcode".

Every other vector — the 224 slots from 32 to 255, minus the three gates
above — is wired to `default_isr` (`idt.s:157-162`): acknowledge the PIC
(EOI) and `iret`, with no Mort-level handling at all. `load_idt` fills all
224 of those gates with `default_isr` first (`idt.s:90-96`), then
overwrites the keyboard/timer/syscall gates on top of it (`idt.s:98-111`).
In normal operation this stub can never run: `remap_pic`'s own PIC mask
(`0xFC` on the master, `idt.s:131`; `0xFF` on the slave, `idt.s:133`)
enables only IRQ0 and IRQ1 and masks the master's IRQ2 cascade line, so no
other hardware IRQ can reach the CPU even if the (fully masked) slave PIC
raised one, and nothing in the source executes a software `int` in that
range. It's a safety net for a case the rest of the source never triggers.

### A shell command runs inside the keyboard ISR, interrupts off

`load_idt` installs every gate — the 32 exception vectors, the keyboard
gate, the timer gate, and the syscall gate — through the same `set_gate`
helper, which always writes type byte `0x8E` (`idt.s:73`): present, ring 0,
32-bit **interrupt gate**, never a trap gate. An interrupt gate clears the
CPU's IF flag on entry and only restores it via the saved `EFLAGS` when the
handler reaches `iret`. `keyboard_isr` (`idt.s:137`-`145`) never re-enables
it early — it calls `mort_on_key` (`on_key()`) first and only sends the PIC
its end-of-interrupt, then `iret`s, *after* that call returns
(`idt.s:142`-`145`). Pressing Enter runs the typed command inside that same,
still-uninterruptible call: `key_event()`'s Enter branch calls `run_command()`
directly (`kmain.mx:3730`), which reaches `run_command_impl()`'s dispatch
(e.g. the `net`/`httpd` rows, `kmain.mx:2937`-`2944`) with no `asm("sti")`
anywhere in between — the same holds for a command arriving over COM1, since
`serial_service()` calls `key_event()` from `kmain`'s main loop with
interrupts already turned back off (see Kernel entry above). Outside the
IDT's own interrupt-gate mechanism, the only `sti`/`cli` use in the kernel is
that main loop's repeating toggle (`kmain.mx:3800`-`3808`) plus two
unrecoverable halts that disable interrupts and never re-enable them:
`poweroff()`'s shutdown `cli` (`kmain.mx:3682`) and the Borehole interface's
own init-failure halt, `ui_fatal()`'s `cli` (`ui/borehole.mx:92`). Two
commands make the interrupts-off-during-dispatch behavior observable:

- **`net` freezes the clock and the keyboard for its whole DHCP wait.**
  `net_dhcp()`'s receive-poll loop (`net/netapp.mx:77`,
  `while spins < 30000000`) runs with IF cleared throughout, so IRQ0 can't
  tick the clock and IRQ1 can't call `on_key()` again until the loop
  ends and the Enter keystroke's original call finally returns — any key
  pressed in that window isn't serviced until then. The Machine stratum's
  "Connect with DHCP" row calls the same `net_dhcp()` from its own key
  handler, so the interface freezes the same way.
- **`httpd` never gives the keyboard back.** `net_httpd()`'s serve loop
  (`net/netapp.mx:193`-`259`) is an unconditional `while true` with no exit,
  so the `on_key()` call that started it never returns — `keyboard_isr`
  never reaches its EOI or `iret`, and IF stays cleared for good. From then
  on, no IRQ1 (keystrokes — including Esc back to the surface, or typing
  `reboot`) and no IRQ0 (the clock) can fire again. `net_httpd`'s own
  printed `"(reboot to stop)"` (`net/netapp.mx:182`-`187`, see
  [`docs/networking.md`](networking.md)) therefore means a physical reset
  or power-cycle — the shell's own `reboot` command (`kmain.mx:3369`-`3372`)
  can't run, since the shell can no longer read a keystroke to launch it.

Every text-entry point funnels raw scancodes through the same
`scancode_to_ascii(sc, shift)` (`kmain.mx:839-874`): a fixed, hand-built
US-QWERTY table covering only the alphabetic keys, the digit row (with its
shifted symbols `!@#$%^&*()`), space, and eleven punctuation keys
(`-_=+[]{};:'"` `` `~ `` `\|,.<>/?`), each `if sc == N` line mapping one
scancode. Anything else — Tab, Caps Lock, function keys, the numpad, media
keys — falls through to `return 0`. All four call sites treat `0` the same
way, silently dropping the keystroke rather than inserting a character: the
main shell prompt (`key_event`, `kmain.mx:3750-3751`), the blocking poll-based
line reader used for `su`/`passwd`/masked prompts (`kread_line`,
`kmain.mx:3565`, `ch != 0` at `kmain.mx:3590`), the program `read-line`
syscall (`read_line`, `kmain.mx:2196`, `ch != 0` at `kmain.mx:2228`), and
the lock screen (`ui_lock_key`, `ui/borehole.mx`). There is no Caps Lock state anywhere in the source — only
the tracked Shift flag (`g_shift` or a local `shift`) selects the
upper/shifted row, so `scancode_to_ascii`'s own two-value `shift: bool`
parameter is the entire case-toggle mechanism.

Arrow keys are a separate case worth tracing, since they arrive as a
two-byte `0xE0`-prefixed sequence rather than the single scancodes
`scancode_to_ascii` maps. `ui_on_key()` tracks that prefix for every
non-shell scene, which use the raw scancodes `72` (Up), `80` (Down), and
`73`/`81` (PgUp/PgDn, in the core sample) once it is seen — as does the shell
prompt's own history recall, now in `key_event()`
(`kmain.mx:3697`-`3709`, see
[`docs/shell.md`](shell.md)'s Line editing section). The three plain
text-entry readers do not: `kread_line` and `read_line` drop the prefix
only incidentally, since `224` fails their own `sc < 128` gate
(`kmain.mx:3588`, `kmain.mx:2226`) before ever reaching
`scancode_to_ascii`; `ui_lock_key` ignores it explicitly (`if ext`). Either way, the arrow key's second byte (`72`/
`75`/`77`/`80`) also maps to `0` in `scancode_to_ascii` — none of those
values fall inside any of its mapped ranges — so pressing an arrow key
while typing a password (`su`/`passwd`), answering a program's `read-line`
syscall, or at the lock screen is a complete no-op: no digit is inserted,
no cursor moves, nothing is recalled. None of these three readers supports
editing anywhere but the end of the line — only appending a character and
Backspace.

Only one compiled program can run at a time, synchronously, from inside a
shell command — there is no concept of a background process.

## The Borehole interface

The graphics path's whole interface lives in `ui/borehole.mx`; the idea is
written up in [`docs/borehole-concept.md`](borehole-concept.md). There is no
window manager and there are no apps. `g_scene` selects one full-screen scene:
surface, shell gallery, Objects, core sample, Machine, Terminate, lock or sleep.

**Drawing.** Each scene is composed off-screen into `g_back` (1024x768, pitch
4096, from `kmalloc` in `ui_init`, which halts with an on-screen error if the
allocation fails or the framebuffer is not 1024x768). `ui_reveal` then lets the
timer copy it to the framebuffer row by row, behind the drill bit. Anything
that changes between scenes (selection, the bit, the clock, the password
field) is drawn straight on the framebuffer over a strip restored from `g_back`
by `ui_restore`.

Every primitive clips to the surface it is drawing on: `put_pixel`,
`fill_rect` and `draw_glyph` in `kmain.mx`, using `g_tgt`/`g_tgt_w`/`g_tgt_h`,
and `ui_glyph`, `ui_restore` and `ui_copy_row` in the interface. Coordinates are
`u32`, so a negative value arrives as a huge one and is clipped with the rest.
The `drawprobe` shell command exists to prove this: `test_gfx.py` runs it and
diffs guest memory.

**The console seam.** The shell still draws through `put_cell_at`,
`move_cursor`, `clear_screen` and `scroll_up`. Their graphics branches call
`ui_put_cell`, `ui_move_cursor`, `ui_console_clear` and `ui_console_scroll`, which
keep the text in `g_cells` (80x25, character and attribute) whether or not the
shell is on screen. That is why leaving the shell loses nothing, and why output
produced before the first frame still appears. A cell is 10x20 px, so the
console fills 800x500 inside the gallery.

**Keys.** `key_event()` calls `ui_on_key(sc)` first. In the shell gallery only Esc
is taken; everything else returns `false` and reaches the normal shell path.
Every other scene consumes all keys. A key pressed during a reveal finishes the
reveal first. On the surface `M`, `O`, `R` and `T` drill straight to a stratum.

**Timer.** `ui_tick()` advances a reveal, slides the bit toward its goal,
flickers its spark, and redraws the clock (and Machine's uptime) once a second.
The sealed scenes, lock and sleep, draw neither bit nor clock.

**Objects** (`ui_scan_dir`, `ui_compose_objects`) lists one directory's entries,
directories first, by checking each table entry's `parent` and `type` bytes.
`g_chain` holds the path, drawn as stacked strata (the last seven segments on a
very deep path). A bed's height grows with the log of the file's size; beds stay
above a fixed footer and the list scrolls so the selection is always visible.
Esc re-finds the directory just left in its parent's listing, so the selection
is valid at any depth. Enter on a file reads it into FILEBUF with
`fs_read_file` and opens the core sample, which reports a failed read on the
slab rather than showing an empty one.

**Lock** checks the typed password against the logged-in account's hash
(`ui_lock_ok`). **Lock and Sleep** return to whichever scene opened them
(`g_return_scene`). `restore_desktop()` puts the shell gallery back on screen
at once, with no reveal, for callers outside the keyboard path.

## Programs and syscalls

`exec <file>` (`exec_file`, `kmain.mx:2647`) copies a file's bytes from the
disk straight to the fixed load address `0x00A00000` via `fs_read_at`
(`kmain.mx:2669-2684`, see `docs/memory-map.md` for why not `0x01000000`)
and calls into it — through SECBUF, sector by sector (`fs_read_at`,
`kmain.mx:2027-2056`), *not* FILEBUF: `exec_file`'s own header comment notes
"the image does not go through FILEBUF, which may hold the script that
launched this program" (`kmain.mx:2644-2646`), since `run` may be what's
calling `exec`. The loaded program shares no symbols with the kernel; it
communicates entirely through a fixed mailbox at `0x009F0000` plus
`int 0x80` (`kmain.mx:2153-2157`). `on_syscall()` (`kmain.mx:2574-2634`)
reads the syscall number from the mailbox and dispatches on it — the ABI has
grown well past its original four calls (print with newline (1), print
inline (2), return uptime in seconds (3), and read a line of input (4));
file read/write, process queries, directory listing, and kill have all been
added since, so this doc doesn't enumerate them — see
[`docs/programs.md`](programs.md) for the syscall table and how to build and
write your own program (check it against `on_syscall()` directly, since it
may itself predate some of these). Read-line (4) still works by polling
rather than via IRQ1, since the handler runs with interrupts off — but
`read_line` (`kmain.mx:2196-2243`) and the masked-prompt reader `kread_line`
now poll `input_wait()`, which the latter's own comment marks "PS/2 or
COM1" (`kmain.mx:3570`), not the keyboard alone.

## Filesystem, networking, shell

These three subsystems each have their own detailed reference; this doc
only places them in the picture:

- **MortFS** (disk + files): `fs_init`/`fs_read_file`/`fs_create_full`/`fs_remove`
  and the ATA PIO driver underneath it — see
  [`docs/fs-design.md`](fs-design.md) for the on-disk format and
  [`docs/memory-map.md`](memory-map.md) for `SECBUF`/`TABCACHE`/`FILEBUF`.
- **mortnet** (the `net`/`httpd` shell commands): the vendored TCP/IP stack
  under `net/`, RTL8139 up through HTTP — see
  [`docs/networking.md`](networking.md) for the full layer table.
- **The shell**: command parsing, `$VAR` expansion, and every built-in —
  see [`docs/shell.md`](shell.md).

## What isn't here

No paging (`docs/memory-map.md` notes CR0/CR3 are never touched), no
long-mode transition, no scheduler or multitasking, no dynamic loading
(programs are flat binaries at a fixed address), and no window manager or
multiple apps — just the single `g_scene` full-screen state machine
described in [The Borehole interface](#the-borehole-interface) above
(`g_scene`, `ui/borehole.mx:38`; the eight `SC_*` scene constants,
`ui/borehole.mx:10-17`). These aren't gaps in this document — they're
genuinely absent from the kernel as it stands today.

## Orphaned files

`font_data.mxinc` (repo root) is never referenced anywhere in the source —
no `build.py` step, and no `*.mx`/`*.s` file includes or imports it
(confirmed by grepping the whole repo for `font_data`). It declares a
`g_font: [u8; 4096]` bitmap-font array that is byte-for-byte identical to
the one actually compiled in, which is embedded directly inside `kmain.mx`
at `kmain.mx:81`-`338` (also named `g_font`, used by `draw_glyph`,
`kmain.mx:419`). The file appears to be a leftover from before the font
data was inlined into the kernel source; it costs nothing at build time
since nothing pulls it in, but it's dead weight in the tree. A human could
safely `git rm` it — deleting an unreferenced file changes no kernel
behavior — but that's left as a call for a human to make rather than this
docs-only pass.
