# x86_64-mortos bootstrap sysroot

This source tree defines the first reusable native MortOS platform SDK. The
build copies its headers to `build/x86_64/sysroot/include`, installs `crt1.o`,
and archives the syscall, allocator/C++ ABI, and freestanding runtime objects
as `lib/libmortos.a`.

It is deliberately named a bootstrap sysroot rather than a complete libc.
CRT startup establishes main-thread TLS, thread-local `errno`, and a stack
canary; the first `unistd` and memory-mapping wrappers translate raw kernel
results to POSIX conventions. The canonical Vex port still requires the rest
of libc/libc++, pthread TLS lifecycle, dynamic loading, networking, and
device/window APIs. Raw calls stay available under `<mortos/syscall.h>`.
