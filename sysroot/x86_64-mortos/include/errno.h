#ifndef MORTOS_ERRNO_H
#define MORTOS_ERRNO_H

#ifdef __cplusplus
extern "C" {
#endif

int *__errno_location(void);

#ifdef __cplusplus
}
#endif

#define errno (*__errno_location())

#define EAGAIN 11
#define EWOULDBLOCK EAGAIN
#define EACCES 13
#define EADDRINUSE 98
#define EADDRNOTAVAIL 99
#define EAFNOSUPPORT 97
#define EALREADY 114
#define EBADF 9
#define EBUSY 16
#define ECHILD 10
#define ECONNABORTED 103
#define ECONNREFUSED 111
#define ECONNRESET 104
#define EDESTADDRREQ 89
#define EFAULT 14
#define EFBIG 27
#define EHOSTUNREACH 113
#define EILSEQ 84
#define EINPROGRESS 115
#define EDEADLK 35
#define EINVAL 22
#define EINTR 4
#define EIO 5
#define EISCONN 106
#define EISDIR 21
#define ELOOP 40
#define EMFILE 24
#define EMSGSIZE 90
#define ENAMETOOLONG 36
#define ENETDOWN 100
#define ENETUNREACH 101
#define ENFILE 23
#define ENOBUFS 105
#define ENODEV 19
#define ENOENT 2
#define ENOMEM 12
#define ENONET 64
#define ENOPROTOOPT 92
#define ENOSPC 28
#define ENOSYS 38
#define ENOTCONN 107
#define ENOTDIR 20
#define ENOTEMPTY 39
#define ENOTSOCK 88
#define ENOTSUP 95
#define EOPNOTSUPP ENOTSUP
#define ENXIO 6
#define EPIPE 32
#define EPERM 1
#define EPROTO 71
#define EPROTONOSUPPORT 93
#define EPROTOTYPE 91
#define ERANGE 34
#define EROFS 30
#define ESPIPE 29
#define ESRCH 3
#define ETXTBSY 26
#define EXDEV 18
#define EOVERFLOW 75
#define ETIMEDOUT 110

#endif
