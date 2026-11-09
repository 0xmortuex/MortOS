# Writing MORT OS Programs

MORT OS runs compiled programs: `.mx` sources in [`programs/`](../programs/), built by `build.py`
into flat binaries and launched from the shell by name. This file is the reference for the program
format, the syscall ABI and the userland library. See [`docs/shell.md`](shell.md) for the shell and
[`docs/memory-map.md`](memory-map.md) for the physical layout.

## What a program is

A program is **a flat 32-bit binary with no ELF header**, linked to load at `0x00A00000`. It shares
no symbols with the kernel. The kernel enters it at byte 0, and that byte is the compiled Mort
`main`: `programs/prog.ld` places `.text.mort_main` first and fails the link if `mort_main` is not
at the load base. No assembly entry stub exists any more. A program ends by returning from `main`
or by calling `exit`; both give the kernel an exit status (the low 8 bits).

| Region | Address | Size | Note |
|---|---|---|---|
| Image and bss | `0x00A00000` | 64 KiB | Zeroed, then the file is copied in. `prog.ld` fails the link if image + bss is larger |
| Stack | `0x00A10000` to `0x00A20000` | 64 KiB | Grows down from `0x00A20000`. The program's own, not the kernel's |
| Mailbox | `0x009F0000` | 0x180 B | Syscall arguments and results |
| argv | `0x009F0200` | 0x600 B | Filled by the kernel before entry; read it through syscalls 7 and 8 |

## Build pipeline

`build_program()` in `build.py` concatenates `programs/lib/ulib.mx` with one `programs/*.mx`, then:

1. Compiles the Mort to freestanding C (`main` becomes `mort_main`).
2. Compiles that and `runtime.c` with `-ffunction-sections -fdata-sections -mno-sse -mno-sse2 -mno-mmx`.
   SSE is disabled in this kernel, so vector code would raise `#UD`.
3. Links at the fixed base with `prog.ld`, entry `mort_main`, `--gc-sections` (a program only
   carries the parts of the library it uses).
4. Runs `objcopy -O binary`.

Compiler error line numbers count from the start of the concatenation, so a program's errors are
offset by the length of `ulib.mx`.

Any new `.mx` in `programs/` is picked up automatically by `python build.py prog`. `lib/` is not
scanned.

**The disk image is seeded once.** `ensure_disk()` does nothing if `build/disk.img` exists, so after
adding or rebuilding a program delete that file (or reseed it with `python mkfs.py build/disk.img
--add-bin build/<name>.bin`). A new `<name>.bin` is moved from `/` into `/bin` and marked 0755 at
first boot.

## Running one

From the shell, type its name: the lookup tries `<name>`, `/bin/<name>`, `<name>.bin` and
`/bin/<name>.bin`. `exec <path> [args...]` runs one by path.

`ls`, `cat` and `echo` exist both as programs and as shell builtins. When `/bin/<name>.bin` is
present and executable the shell runs the program; the builtin is only the fallback for a machine
with no disk or an older disk image without the program. `ps`, `kill` and `ed` are programs only.

`$?` expands to the exit status of the last command. A program sets it to its exit status. A
command that is not found sets 127. Builtins always set 0, including when they print an error,
because they have no status of their own.

Argument splitting: words are separated by spaces, and `"double quotes"` group a word. `$VAR` and
`$?` expand before splitting. The limit is 16 arguments.

## The syscall ABI

A program fills the mailbox and raises `int 0x80`. All fields are 4-byte little-endian. Registers
carry nothing, because Mort's `asm()` takes one string and cannot bind operands (`BLOCKERS.md`).

| Address | Field | Direction |
|---|---|---|
| `0x009F0000` | syscall number | to kernel |
| `0x009F0004` | arg0 | to kernel |
| `0x009F0008` | arg1 | to kernel |
| `0x009F000C` | return value | to program |
| `0x009F0010` | entry address | kernel only |
| `0x009F0014` | arg2 | to kernel |
| `0x009F0018` | arg3 | to kernel |
| `0x009F001C` | saved kernel stack | kernel only |
| `0x009F0020` | exit status of the finished program | kernel only |
| `0x009F0024` | status passed to the exit path | kernel only |
| `0x009F0100` | syscall 4 line buffer, 120 chars + NUL | to program |

Calls that can fail return `-errno` as a u32 (`is_err`, `err_of`). The kernel prints no messages on
a program's behalf: error text is the program's job. Numbers are the POSIX ones.

| # | Name | Arguments | Returns |
|---|---|---|---|
| 1 | print and newline | `str` | none |
| 2 | print inline | `str` | none |
| 3 | uptime | none | seconds |
| 4 | read a line, polling | none | pointer to `0x009F0100` |
| 5 | write bytes | `buf`, `len` | `len`; `\n` starts a new line, `\r` is dropped |
| 6 | exit | `status` | does not return |
| 7 | argc | none | argument count |
| 8 | argv | `i` | pointer to argument `i`, or 0 past the end |
| 9 | stat | `path`, `ent` | 0 |
| 10 | readdir | `path`, `cursor` (start at 0), `ent` | next cursor, 0 at the end |
| 11 | read file | `path`, `offset`, `buf`, `len` | bytes read, 0 at end of file |
| 12 | write file | `path`, `buf`, `len`, `flags` (0 append, 1 replace) | `len`; creates a missing file |
| 13 | getpid | none | pid |
| 14 | process list | `cursor` (start at 0), `rec` | next cursor, 0 at the end |
| 15 | kill | `pid` | 0; killing yourself does not return |

Unknown numbers return `-ENOSYS` (38). Errors used: `EPERM` 1, `ENOENT` 2, `ESRCH` 3, `EIO` 5,
`EACCES` 13, `EFAULT` 14, `ENOTDIR` 20, `EISDIR` 21, `EINVAL` 22, `EFBIG` 27, `ENOSPC` 28,
`ENAMETOOLONG` 36, `ENOSYS` 38.

A directory entry or `stat` result is 40 bytes: `name[24]`, then `type` at +24 (0 file, 1 directory),
`size` +28, `mode` +32, `uid` +36. A process record is 40 bytes: `name[24]`, then `pid` +24, `state`
+28 (1 running, 2 exited), `status` +32, `uid` +36.

Paths may be absolute or relative to the shell's working directory, up to 63 characters, with each
component up to 23. The kernel checks that pointers passed to it lie inside the program area (or
the argv and line buffers, for strings it only reads). This guards the kernel's copy loops against
wild pointers. It is not protection: a program runs in ring 0 and can write anywhere.

Writing checks the file's permission bits, as `write` does. Reading does not check them, matching
the shell's `cat`.

### Typing a long answer to syscall 4 corrupts the row below it

`read_line()` (`kmain.mx:1810`-`1858`), the function behind syscall 4, echoes
each typed character by incrementing `g_pcol` with no upper bound besides
the 120-character buffer cap (`kmain.mx:1844`) — it never checks `g_pcol`
against the console's 80-column width the way its neighbors do. Two other
text-entry paths in the same file both guard against this: `print_inline()`
(`kmain.mx:1788`-`1803`, the function syscalls 1 and 2 print through) wraps
to a fresh line whenever `g_pcol >= 80` (`kmain.mx:1795`-`1798`), and
`kread_line()` (`kmain.mx:2935`-`2973`, the shell's own masked-input reader
for `su`/`passwd`) sidesteps the problem by capping input at 60 characters
(`kmain.mx:2961`) — comfortably under 80 even with a prompt already on the
line. `read_line()` has neither a wrap check nor a cap low enough to make
one unnecessary. That margin is specific to `su`/`passwd`'s fixed-length
prompts, though — `sudo` reuses the same `kread_line()` behind a
variable-length prompt and reopens this exact overflow; see
[`docs/accounts.md`](accounts.md#sudos-password-prompt-can-overflow-past-column-79-unlike-sus-or-passwds)
for the concrete repro.

The effect once `g_pcol` reaches 80: `put_cell_at()` (`kmain.mx:505`-`517`)
computes a plain `put_index(row * 80 + col, ...)` in VGA text mode
(`kmain.mx:516`), and `put_index()` itself (`kmain.mx:499`-`503`) does no
bounds check — so column 80 lands at `(row + 1) * 80 + 0`, column 0 of the
row below, silently overwriting whatever is drawn there instead of
scrolling. In graphics mode `draw_glyph` is called at `x = 192 + col * 8`
(`kmain.mx:513`), so the glyph keeps marching right past the console's drawn
edge instead of wrapping there either.

This is concretely reachable with the shipped `ask.bin` sample, not just a
theoretical overflow: `exec_file` resets `g_pcol` to `0` right before
entering a program (`kmain.mx:1921`-`1922`), and `ask.mx`'s prompt,
`"what is your name? "` (`programs/ask.mx:25`), is 19 characters, so
`g_pcol` is already 19 when `sys_readline()` starts echoing. Typing a name
of 62 characters or more places the 62nd character at column 80, which
overwrites column 0 of the line below the prompt instead of wrapping onto a
new one.

## The userland library

`programs/lib/ulib.mx` is the libc-equivalent, and every program gets it. It is all Mort.

| Area | Functions |
|---|---|
| Syscalls | `sys0` to `sys2`, `sys4`, `is_err`, `err_of`, `err_str` |
| Strings | `str_len`, `str_eq`, `str_copy`, `mem_copy`, `str_to_u32` (`NOT_A_NUMBER` on bad input) |
| Output | `puts`, `putln`, `put_bytes`, `put_char`, `put_u32`, `put_u32_w`, `put_pad`, `put_spaces`, `fmt_u32`, `putf` (`%s %u %%`, up to three arguments), `put_err` |
| Input | `read_line` |
| Process | `argc`, `argv`, `getpid`, `uptime`, `exit`, `kill`, `proc_next`, `proc_name`, `proc_pid`, `proc_state`, `proc_status`, `proc_uid` |
| Files | `stat`, `readdir`, `fs_read`, `fs_write` (`FW_APPEND`, `FW_REPLACE`), `ent_name`, `ent_type`, `ent_size`, `ent_mode`, `ent_uid` |

The names `file_read` and `file_write` are reserved by the Mort compiler, hence `fs_read` and
`fs_write`.

## Processes: what actually exists

There is no scheduler and no preemption. A program runs to completion inside the shell's command
path with interrupts off, in ring 0, in the one shared address space. Exactly one program can be
alive at a time, and it is always the one making the syscall.

The process table is real but small: one permanent record for the kernel (pid 1), the running
program, and records of up to 7 programs that have exited, the oldest overwritten first. Pids count
up from 2 and are not reused.

`kill` therefore has three real outcomes. Killing pid 1 is refused with `EPERM`. Killing your own
pid ends you with status 143. Every other pid, including one that has already exited, is `ESRCH`.
`BLOCKERS.md` records what is missing for anything more.

## Writing a new one

Drop a `.mx` file with `fn main() -> int` in `programs/`. Call the library directly; do not
redeclare syscalls. [`programs/echo.mx`](../programs/echo.mx) is the smallest complete example.
