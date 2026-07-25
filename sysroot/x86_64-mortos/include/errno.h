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
#define EBADF 9
#define EBUSY 16
#define EFAULT 14
#define EDEADLK 35
#define EINVAL 22
#define ENOSYS 38
#define ENOTCONN 107
#define ENOTSOCK 88
#define EPIPE 32
#define EPERM 1
#define ESRCH 3
#define EOVERFLOW 75
#define ETIMEDOUT 110

#endif
