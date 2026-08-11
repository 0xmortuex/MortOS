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
   `fb_init()` (`kmain.mx:340-355`) detects via the multiboot info struct's
   bit 12 (`kmain.mx:342`) and 32-bpp direct-RGB check (`kmain.mx:345-348`).

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
   `%ebx` by the bootloader) to `kmain(mbinfo)` in `kmain.mx:3589`.
4. If `kmain` ever returns, `_start` does `cli; hlt` in a loop rather than
   running off into undefined memory (`boot.s:48-51`).

`linker.ld` places `.multiboot` first (so it lands in the required first
8 KiB) and everything else after, with the whole image based at 1 MiB
(`linker.ld:8-13`) — the address `docs/memory-map.md` calls the kernel load
address.

## Kernel entry (`kmain`, `kmain.mx:3589-3625`)

In order: `heap_init()` carves the dynamic-memory heap out of high RAM,
`fb_init()` looks for a framebuffer, `fs_init()`/`fs_ensure_layout()`/
`fs_populate_bin()` mount MortFS and seed `/bin /etc /home /var` on a fresh
disk, `acct_init()`/`ensure_home()`/`login_default()` set up and log into
the one built-in user account, `run_script(1)` runs the boot script from a
multiboot module if one was passed in, and the prompt is drawn. Only after
all of that does `kmain` call `usb_boot_init()` (a one-shot, polling-only
UHCI enumeration — see [`docs/hardware.md`](hardware.md)), `init_pit()`
(arms the ~100 Hz PIT on IRQ0), optionally `open_launcher()` on the graphics
path, and
finally `asm("sti")` to enable interrupts — everything before that line runs
with interrupts off. The function ends in `while true { asm("hlt"); }`
(`kmain.mx:3622-3624`): once interrupts are on, all real work happens inside
IRQ handlers.

## Execution model: no scheduler, no processes

There is no scheduler, no task list, and no preemption anywhere in this
codebase — the repo has exactly one flow of control besides interrupts.
Shell and UI state lives in global variables at the top of `kmain.mx`
(e.g. `g_row` at `kmain.mx:10`, `g_uid` at `kmain.mx:25`, `g_gfx` at
`kmain.mx:42`, `g_app` at `kmain.mx:49`), and three interrupt sources drive
all behavior after `sti`:

- **IRQ1 (keyboard)** → `keyboard_isr` (`idt.s:137-145`) → `mort_on_key` →
  `on_key()` (`kmain.mx:3491`), which reads the scancode and either routes
  it to an open overlay (`g_overlay != 0`), an app-switch hotkey (F1-F5,
  graphics only, `kmain.mx:3503-3508`), the active app's own handler when
  `g_app` isn't the terminal (`kmain.mx:3510-3518`), or the terminal/shell
  scancode-to-ASCII path.
- **IRQ0 (timer, ~100 Hz)** → `timer_isr` (`idt.s:147-155`) → `mort_on_tick`,
  which bumps `g_ticks` (backs the `uptime` command).
- **`int 0x80` (syscall)** → `syscall_isr` (`idt.s:170-174`) → `on_syscall()`
  (`kmain.mx:1860`), described below.

Only one compiled program can run at a time, synchronously, from inside a
shell command — there is no concept of a background process.

## The desktop / window manager

`g_app` (`kmain.mx:49`) selects which of four apps is active: `0` Terminal,
`1` Files, `2` Vex (browser), `3` Settings. `switch_app()` (`kmain.mx:2839-2850`) just sets `g_app`, redraws
the top bar, and calls that app's own draw function
(`terminal_activate`/`files_draw`/`vex_draw`/`settings_draw`) — there's no
generic window/widget abstraction, each app owns its own draw + key-handler
pair, dispatched by the `if g_app == N` chain in `on_key()` above. `F12`
opens the power menu as a modal overlay from any app (`g_overlay`,
`kmain.mx:3498-3499`); overlays intercept the keyboard ahead of app routing.
The framebuffer console itself (`put_pixel`/`fill_rect`/`fill_gradient`,
`kmain.mx:357-391`) is a flat pixel-pushing layer with no double buffering
or dirty-rect tracking — every draw call writes straight to `g_fb`.

## Programs and syscalls

`exec <file>` (`exec_file`, `kmain.mx:1892`) copies a file's bytes from the
disk's FILEBUF straight to the fixed load address `0x00A00000`
(`kmain.mx:1908-1916`, see `docs/memory-map.md` for why not `0x01000000`)
and calls into it. The loaded program shares no symbols with the kernel;
it communicates entirely through a fixed mailbox at `0x009F0000` plus
`int 0x80` (`kmain.mx:1773-1779`). `on_syscall()` (`kmain.mx:1860`) reads
the syscall number from the mailbox and implements four calls: print with
newline (1), print inline (2), return uptime in seconds (3), and read a
line of input by polling the keyboard ports directly rather than via IRQ1,
since the handler runs with interrupts off (`read_line`, `kmain.mx:1801-1854`).
See [`docs/programs.md`](programs.md) for the full syscall table and how to
build and write your own program.

## Filesystem, networking, shell

These three subsystems each have their own detailed reference; this doc
only places them in the picture:

- **MortFS** (disk + files): `fs_init`/`fs_read_file`/`fs_create`/`fs_remove`
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
(programs are flat binaries at a fixed address), and no window-manager
abstraction beyond the four hardcoded `g_app` slots described above. These
aren't gaps in this document — they're genuinely absent from the kernel as
it stands today.
