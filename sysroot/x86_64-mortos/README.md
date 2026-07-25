# x86_64-mortos bootstrap sysroot

This source tree defines the first reusable native MortOS platform SDK. The
build copies its headers to `build/x86_64/sysroot/include`, installs `crt1.o`,
and archives the syscall, allocator/C++ ABI, and freestanding runtime objects
as `lib/libmortos.a`.

It is deliberately named a bootstrap sysroot rather than a complete libc.
The canonical Vex port still requires full C/POSIX headers, thread-local
`errno`, libc/libc++, dynamic loading, networking, and device/window APIs.
Every exported bootstrap call returns the raw MortOS syscall result so callers
can distinguish the complete `-errno` range without hidden global state.
