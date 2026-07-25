#ifndef MORTOS_LIBUV_PLATFORM_H
#define MORTOS_LIBUV_PLATFORM_H

/*
 * libuv's generic POSIX layout is the starting point for the native backend.
 * Upstream has no __MORTOS__ selector yet, so this forced include selects that
 * layout without pretending the kernel implements Linux-only ABI details.
 */
#if defined(__MORTOS__) && !defined(__GNU__)
#define __GNU__ 1
#endif

#endif
