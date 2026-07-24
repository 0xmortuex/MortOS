# MortOS x86-64 userspace ABI

Status: active implementation contract for the canonical Vex platform port.
Long mode, ring-3 execution, a validating static ELF64 loader, distinct
per-process W^X/NX mappings, PID assignment, cooperative context switching,
PIT-driven full-context preemption, terminal-process frame reclamation,
user-fault containment, a demand-paged `brk` heap, monotonic time, `write`,
anonymous mappings with a boot-tested RW→RX JIT execution transition,
`yield`, `getpid`, `clock_gettime`, and `exit` are boot-tested. Other
facilities remain planned unless explicitly marked otherwise.

The build also links and boots a freestanding C++ executable using
`programs64/cxx_start.s` and `programs64/cxx_runtime.cpp`. Static constructors,
`malloc`, `calloc`, `realloc`, `free`, C++ `new`/`delete`, compiler atomics,
an FS-base TLS value preserved across context switches, and a
shared-address-space worker with a unique TID are exercised in an isolated
process. The same test creates a descriptor pipe and verifies bounded
`write`/`read` transfer plus `close` cleanup. This is a bootstrap runtime, not
yet the complete libc/libc++ surface required by Chromium.

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
| 0 | `read(fd, buffer, length)` | Implemented for bounded pipe reads with validated output ranges |
| 1 | `write(fd, buffer, length)` | Implemented for stdout and bounded pipe writes with validated input ranges |
| 3 | `close(fd)` | Implemented for pipe descriptors with endpoint reference cleanup |
| 9 | `mmap(address, length, protection, flags, fd, offset)` | Implemented for private anonymous mappings in a separate high user arena |
| 10 | `mprotect(address, length, protection)` | Implemented with W^X enforcement and TLB invalidation |
| 11 | `munmap(address, length)` | Implemented with physical-frame reclamation |
| 12 | `brk(address)` | Implemented with zeroed RW+NX pages, shrink/unmap, and per-process state |
| 24 | `yield()` | Implemented with per-process saved context and round-robin resumption |
| 39 | `getpid()` | Implemented for scheduled processes |
| 60 | `exit(status)` | Implemented for the current process |
| 158 | `arch_prctl(code, address)` | Implements bounded `ARCH_SET_FS`/`ARCH_GET_FS`; FS base is restored per task |
| 186 | `gettid()` | Returns the current schedulable task ID |
| 228 | `clock_gettime(clock_id, timespec)` | Implemented for `CLOCK_MONOTONIC` from the 100 Hz kernel tick |
| 293 | `pipe2(descriptors, flags)` | Implements a bounded in-kernel pipe and two per-process descriptors |
| 400 | `thread_create(entry, stack_top, argument, return_trampoline)` | MortOS-native validated thread primitive; shares the process address space and schedules a full independent context |

The remaining implementation order is:

1. `dup`, `fcntl`, descriptor flags, and blocking/poll integration.
2. File-backed mappings, shared memory, and page-fault reporting.
3. `openat`, `stat`, `getdents`, `pread`, `pwrite`, `fsync`, and file mapping.
4. `spawn`, `execve`, `wait`, process groups, thread join/cancellation, and futex-style waits.
5. `poll`, transferable local IPC, sockets, DNS-facing service IPC, and entropy.
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
