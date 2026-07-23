# MortOS x86-64 userspace ABI

Status: active implementation contract for the canonical Vex platform port.
Long mode, ring-3 execution, a validating static ELF64 loader, distinct
per-process W^X/NX mappings, PID assignment, cooperative context switching,
terminal-process frame reclamation, user-fault containment, a demand-paged
`brk` heap, `write`, `yield`, `getpid`, and `exit` are boot-tested. Other
facilities remain planned unless explicitly marked otherwise.

The kernel build currently pins Mort 0.18.0, the proven freestanding compiler.
Mort 0.39's hosted `net_*` intrinsic detection collides with MortOS's own
kernel network functions and must be fixed before the OS toolchain advances.
An explicit `MORT_HOME` can be used to test a corrected compiler.

## Binary and calling conventions

- Architecture: little-endian AMD64 (`x86_64-mortos`).
- Executables: ELF64, initially static `ET_EXEC`; PIE `ET_DYN` follows when
  relocations and ASLR are available.
- Application function calls: System V AMD64 ABI.
- Stack: 16-byte aligned at call boundaries, grows downward, with a guard page.
- Thread-local storage: `FS.base`; the kernel owns `GS.base`.
- Initial process stack: `argc`, `argv`, `envp`, then an ELF auxiliary vector.
- Page size: 4096 bytes. Large pages are a kernel optimization, never an
  userspace requirement.

Following existing AMD64 conventions minimizes custom compiler work and makes
LLVM, libc, V8, and Chromium ports maintainable.

## Syscall convention

The `syscall` instruction enters the kernel.

| Purpose | Register |
| --- | --- |
| Syscall number | `RAX` |
| Arguments 1–6 | `RDI`, `RSI`, `RDX`, `R10`, `R8`, `R9` |
| Return value | `RAX` |
| Clobbered | `RCX`, `R11`, condition flags |

Success returns a non-negative value. Failure returns `-errno` in the inclusive
range `-4095..-1`. Pointer/length pairs are checked for canonical addresses,
overflow, access permissions, and complete range validity before use.

## Required syscall groups

The initial numeric assignments are:

| Number | Call | Status |
| --- | --- | --- |
| 1 | `write(fd, buffer, length)` | Implemented for stdout with bounded user-range validation |
| 12 | `brk(address)` | Implemented with zeroed RW+NX pages, shrink/unmap, and per-process state |
| 24 | `yield()` | Implemented with per-process saved context and round-robin resumption |
| 39 | `getpid()` | Implemented for scheduled processes |
| 60 | `exit(status)` | Implemented for the current process |

The remaining implementation order is:

1. `read`, `close`, and `clock_gettime`.
2. `mmap`, `munmap`, `mprotect`, shared memory, and page-fault reporting.
3. `openat`, `stat`, `getdents`, `pread`, `pwrite`, `fsync`, and file mapping.
4. `spawn`, `execve`, `wait`, process groups, threads, TLS, and futex-style waits.
5. `poll`, pipes, local IPC, sockets, DNS-facing service IPC, and entropy.
6. Window surfaces, shared pixel buffers, input queues, clipboard, audio
   streams, device permissions, and GPU command submission.

The names intentionally resemble mature Unix ABIs, but their implementation is
MortOS-native. Linux binaries are not implicitly supported.

## Process security invariants

- User code executes at ring 3 and cannot share the kernel address space as
  writable memory.
- Every process receives its own page-table root.
- User mappings are non-executable by default; executable mappings are not
  writable (W^X).
- Kernel/user copies are explicit and recover from user page faults.
- Renderer, network, GPU, and utility processes have separate capability and
  namespace policies.
- Handles are per-process and rights-reduced on transfer.
- Randomized mappings, stack guards, NX, SMEP, and SMAP are enabled as soon as
  the corresponding bootstrap stages support them.

These are prerequisites for running untrusted web content. A Chromium port may
not bypass them for convenience.

## Compatibility transition

The current 32-bit flat program loader at `0x00A00000` and mailbox-based
`int 0x80` interface remain available only on the legacy kernel during
migration. They are not the ABI used by Vex. Once the 64-bit desktop reaches
feature parity, a bounded compatibility personality may run old Mort programs;
it will not constrain the 64-bit ABI.
