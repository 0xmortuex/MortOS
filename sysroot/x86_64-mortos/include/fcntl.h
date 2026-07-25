#ifndef MORTOS_FCNTL_H
#define MORTOS_FCNTL_H

#define AT_FDCWD (-100)

#define O_RDONLY 0
#define O_WRONLY 1
#define O_RDWR 2
#define O_NONBLOCK 0x800
#define O_DIRECTORY 0x10000
#define O_CLOEXEC 0x80000

#define F_GETFD 1
#define F_SETFD 2
#define F_GETFL 3
#define F_SETFL 4
#define FD_CLOEXEC 1

#ifdef __cplusplus
extern "C" {
#endif

int open(const char *path, int flags, ...);
int openat(int directory, const char *path, int flags, ...);
int fcntl(int descriptor, int command, ...);

#ifdef __cplusplus
}
#endif

#endif
