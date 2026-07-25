#ifndef MORTOS_SYS_EVENTFD_H
#define MORTOS_SYS_EVENTFD_H

typedef unsigned long eventfd_t;

#define EFD_SEMAPHORE 1
#define EFD_NONBLOCK 0x800
#define EFD_CLOEXEC 0x80000

#ifdef __cplusplus
extern "C" {
#endif

int eventfd(unsigned int initial, int flags);
int eventfd_read(int descriptor, eventfd_t *value);
int eventfd_write(int descriptor, eventfd_t value);

#ifdef __cplusplus
}
#endif

#endif
