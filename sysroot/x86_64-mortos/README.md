# x86_64-mortos bootstrap sysroot

This source tree defines the first reusable native MortOS platform SDK. The
build copies its headers to `build/x86_64/sysroot/include`, installs `crt1.o`,
and archives the syscall, allocator/C++ ABI, and freestanding runtime objects
as `lib/libmortos.a`.

It is deliberately named a bootstrap sysroot rather than a complete libc.
CRT startup establishes main-thread TLS, thread-local `errno`, and a stack
canary; the first `unistd` and memory-mapping wrappers translate raw kernel
results to POSIX conventions. `pthread_create` supplies protected workers with
private stacks and TLS; mutexes, condition variables, read/write locks, and
process-local POSIX semaphores use kernel scheduler futexes, and blocking join promptly reclaims each worker's scheduler slot,
stack, and TLS. Futex waits also accept relative kernel deadlines for the
absolute realtime condition-variable and semaphore APIs. One-time initialization and 64 per-thread keys with exit
destructors cover additional Node/V8 runtime requirements. The canonical Vex port still requires the rest
of libc/libc++, although descriptor creation/flag control, CMOS-anchored realtime, monotonic clock, and
scheduler-backed sleep plus POSIX poll/epoll/eventfd wrappers are now present. Dynamic loading, networking, and
device/window APIs. Raw calls stay available under `<mortos/syscall.h>`.
