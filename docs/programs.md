# Writing MORT OS Programs

MORT OS runs real compiled programs — `.mx` sources in [`programs/`](../programs/),
built by `build.py` into flat binaries and `exec`'d from the shell. This is a
grounded reference for the format and the syscall ABI a program uses to talk
to the kernel; see [`docs/shell.md`](shell.md) for the `exec` command itself
and [`docs/memory-map.md`](memory-map.md) for where everything below lives in
physical memory.

## What a program is

A program is **a flat 32-bit binary with no ELF header** — just raw
`.text`/`.rodata`/`.data`/`.bss` bytes linked to load at the fixed address
`0x00A00000` (`kmain.mx:1775`). It shares no symbols with the kernel: the
only way in is its entry point, and the only way to ask the kernel for
anything is the syscall mailbox below.

Every program links against two small pieces the kernel doesn't need at
runtime, both in `programs/`:

- **`pstart.s`** — the entry stub. The kernel calls the first byte of the
  loaded binary, so this must be linked first; it just calls the compiled
  Mort `main` (emitted as `mort_main`) and returns:
  ```
  _pstart:
      call mort_main
      ret
  ```
  (`programs/pstart.s:6-8`)
- **`prog.ld`** — the linker script that places everything at
  `0x00A00000` and discards ELF metadata sections (`programs/prog.ld:4`,
  `:12`).

## Build pipeline

`build_program()` (`build.py:274`-`320`) compiles one `programs/*.mx` file
into a seedable `.bin`, the same four-step recipe as the kernel itself but
linked differently:

1. **Mort → freestanding C** via `mortc.compile_to_c(..., freestanding=True)`
   (`build.py:288`) — the program's `main` becomes `mort_main`.
2. **Compile + assemble**: the generated C, `runtime.c` (freestanding
   `memset`/`memcpy`/`memmove`, no hosted libc), and `pstart.s`
   (`build.py:303`-`307`).
3. **Link** at the fixed base with `prog.ld`, entry `_pstart`
   (`build.py:310`-`315`).
4. **`objcopy -O binary`** strips the ELF wrapper down to the raw bytes the
   kernel loads verbatim (`build.py:318`-`319`).

`python build.py prog` builds every `programs/*.mx` this way
(`prog()`, `build.py:331`-`338`, via `_program_sources()`,
`build.py:323`-`328`, which just globs `programs/*.mx` — **any new `.mx`
file dropped in `programs/` is picked up automatically**, no registration
needed). `python build.py disk`/`ensure_disk()` builds and seeds all of them
onto `build/disk.img` as `<name>.bin` (`build.py:357`-`365`) so they're
present the moment the OS boots.

## Running one

From the MORT OS shell: `exec <name>.bin` (`exec_file`, `kmain.mx:1892`-
`1920`, dispatched at `kmain.mx:2347`). It looks the file up on MortFS,
reads it into `FILEBUF`, zeroes the full 64 KiB program region at
`0x00A00000`, copies the binary in, and calls into it (`exec_enter`,
`kmain.mx:1886`-`1888`, an indirect call through the stored entry address
so the call's register clobber can't reach live kernel state). There is no
process isolation or separate stack — a program that overflows the stack
corrupts kernel state (see the note in `docs/memory-map.md`).

## The syscall ABI

A program asks the kernel to do something by filling a fixed mailbox and
raising `int 0x80`. Every field is a 4-byte little-endian value
(`kmain.mx:1777`-`1779`):

| Address | Field | Direction |
|---|---|---|
| `0x009F0000` | syscall number | program → kernel |
| `0x009F0004` | arg0 | program → kernel |
| `0x009F000C` | return value | kernel → program |

`on_syscall()` (`kmain.mx:1860`-`1881`) reads the number and implements
exactly four calls:

| # | Name | arg0 | Returns | Behavior |
|---|---|---|---|---|
| `1` | print + newline | pointer to a NUL-terminated string | — | Prints the string, then a newline (`kmain.mx:1862`-`1867`) |
| `2` | print inline | pointer to a NUL-terminated string | — | Prints the string with no trailing newline, so a prompt and typed input can share a line (`kmain.mx:1868`-`1871`) |
| `3` | uptime | — | seconds since boot | Writes `g_ticks / 100` to the return slot (`kmain.mx:1872`-`1875`) |
| `4` | read line | — | pointer to the input buffer at `0x009F0100` | Polls the keyboard ports directly rather than via IRQ1, since the handler that services `int 0x80` runs with interrupts off (`kmain.mx:1876`-`1880`); the returned buffer holds up to 120 chars + NUL (`docs/memory-map.md`) |

There is no syscall 0 and no calls above 4 — an unrecognized number is
silently a no-op (`on_syscall` falls through its `if` chain with no `else`).

A minimal caller (from `programs/hello.mx:6`-`10`):

```
fn sys_print(s: *u8) {
    *((0x009F0000) as *u32) = 1;          // syscall #1 = print string
    *((0x009F0004) as *u32) = s as u32;   // arg0 = string pointer
    asm("int $0x80");
}
```

and reading input back (`programs/ask.mx:18`-`22`):

```
fn sys_readline() -> *u8 {
    *((0x009F0000) as *u32) = 4;
    asm("int $0x80");
    return (*((0x009F000C) as *u32)) as *u8;
}
```

See [`programs/hello.mx`](../programs/hello.mx),
[`programs/count.mx`](../programs/count.mx), and
[`programs/ask.mx`](../programs/ask.mx) for three complete, working examples
(print-only, multiple prints, and interactive input).

## Writing a new one

Drop a `.mx` file in `programs/` with a `fn main() -> int` — no other setup
needed, `build.py prog`/`disk` finds it by directory listing. It can only
reach the kernel through the four syscalls above; there is no heap, no file
I/O syscall, and no way to spawn another program (see the Roadmap in the
main [README](../README.md) for what's planned there).
