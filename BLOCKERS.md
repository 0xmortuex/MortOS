# MORT OS blockers

What the userland cannot do today, and exactly why. Each entry is either something missing in the
OS or something the Mort language cannot yet express.

## Process model: what is real, and what is not

Measured and read from the source on 2026-11-09.

**Real:** a process table in the kernel (`g_proc`, 8 records) holding pid 1 (the kernel), the one
running program, and records of programs that have exited, with their exit status. Pids are not
reused. `ps` reads it through syscall 14. `kill` goes through syscall 15. A program ends by
returning from `main` or calling `exit`, and the status reaches the shell as `$?`.

**Not real, and not pretended:** there is no scheduler. A program runs to completion inside the
command that started it, with interrupts off, on the single CPU. So at any moment exactly one
program can be alive, and it is the caller of every syscall. The consequences:

| Missing | Effect today | Needs |
|---|---|---|
| Preemption, a scheduler, context switches | `kill` can only ever end the caller. Any other pid is a true `no such process`. No background programs | ROADMAP 9 (commands out of the keyboard ISR), then 12. A context switch needs naked functions or assembly |
| Timer interrupts during a program | Interrupts are off while a program runs, so a program that loops forever hangs the machine. No Ctrl-C. `uptime` loses the time a program ran | ROADMAP 9 |
| `spawn`, `wait` | A program cannot start another. Only the shell launches programs | The scheduler above, or a nested-run design |
| Process isolation | Programs run in ring 0 in the one address space. They can overwrite the kernel. The kernel's syscall pointer checks only protect its copy loops from wild pointers | ROADMAP 10 and 11 (paging, ring 3, TSS) |
| CPU fault recovery | An exception in a program halts the machine, as in the kernel: `on_exception` never returns | A fault path that uses the `proc_leave` return route, or ring 3 |
| Stack overflow detection | A program overflowing its 64 KiB stack runs into its own image | Paging (guard pages) |
| Read permissions | `stat`, `readdir` and read-file ignore the mode bits, as the shell's `cat` does. Writes do check them | A read-permission check in the kernel and the shell |
| Pipes, redirection, stdin and stdout streams | All program output goes straight to the console. No `\|` | ROADMAP 13, after the scheduler |

## Language gaps that shaped the ABI

Compiler checked: `C:\Claude code free\Mort` at `69c7052`.

| Gap | Measured | What it forces |
|---|---|---|
| `asm()` takes one string, no operand binding | `asm("int $0x80", in("eax") n)` gives `expected ')', got ','` (`mort/parser.py:_asm_stmt`) | Syscall arguments go through the memory mailbox at `0x009F0000`, not registers. `int 0x80` plus a volatile store of each argument is the whole ABI |
| Naked or interrupt functions | Not available in the checked compiler (`ROADMAP.md`, not re-tested here) | The exec trampoline and `exit` path are single `asm` statements in Mort; the ISR stubs stay in `idt.s` |
| Unmangled definitions | `@export` rejected per `ROADMAP.md`, not re-tested here | `runtime.c` (memset, memcpy, memmove) stays in C and links into every program. It is the only non-Mort code in a program. The assembly entry stub is gone |

`volatile_read<T>` and `volatile_write<T>` do exist in this compiler (the audit found them missing).
`programs/lib/ulib.mx` uses them for every mailbox access, and the kernel reads the exit status
through them.

## Filesystem limits that affect programs

- MortFS is at most 64 entries and 64 KiB per file. `ed` is limited further, to 200 lines of 120
  characters.
- `rm` does not reclaim space. A file-replacing write (flag 1) reuses the file's own extent, so
  `ed` does not leak.
