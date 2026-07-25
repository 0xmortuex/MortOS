#ifndef MORTOS_UNISTD_H
#define MORTOS_UNISTD_H

#include <sys/types.h>

#ifdef __cplusplus
extern "C" {
#endif

ssize_t read(int descriptor, void *buffer, size_t length);
ssize_t write(int descriptor, const void *buffer, size_t length);
int close(int descriptor);
pid_t getpid(void);
pid_t gettid(void);
off_t lseek(int descriptor, off_t offset, int origin);
unsigned int sleep(unsigned int seconds);
int usleep(unsigned int microseconds);

#ifdef __cplusplus
}
#endif

#endif
