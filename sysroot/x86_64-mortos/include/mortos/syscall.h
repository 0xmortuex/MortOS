#ifndef MORTOS_SYSCALL_H
#define MORTOS_SYSCALL_H

#ifdef __cplusplus
extern "C" {
#endif

unsigned long mortos_write(const char *text, unsigned long length);
unsigned long mortos_fd_write(
    unsigned long descriptor, const void *buffer, unsigned long length);
unsigned long mortos_read(
    unsigned long descriptor, void *buffer, unsigned long length);
unsigned long mortos_close(unsigned long descriptor);
unsigned long mortos_fcntl(
    unsigned long descriptor, unsigned long command, unsigned long argument);
unsigned long mortos_getpid(void);
unsigned long mortos_gettid(void);
unsigned long mortos_yield(void);
unsigned long mortos_brk(unsigned long address);
unsigned long mortos_clock_gettime(unsigned long clock_id, void *timespec);
unsigned long mortos_mmap(
    unsigned long address, unsigned long length, unsigned long protection,
    unsigned long flags, unsigned long descriptor, unsigned long offset);
unsigned long mortos_mprotect(
    unsigned long address, unsigned long length, unsigned long protection);
unsigned long mortos_munmap(unsigned long address, unsigned long length);
unsigned long mortos_call0(unsigned long address);
unsigned long mortos_arch_prctl(unsigned long code, unsigned long address);
void mortos_fs_store(unsigned long offset, unsigned long value);
unsigned long mortos_fs_load(unsigned long offset);
unsigned long mortos_pipe2(unsigned int *descriptors, unsigned long flags);
unsigned long mortos_futex(
    unsigned int *address, unsigned long operation, unsigned int value);
unsigned long mortos_futex_timed(
    unsigned int *address, unsigned long operation,
    unsigned int value, unsigned long timeout_milliseconds);
unsigned long mortos_poll(
    void *descriptors, unsigned long count, unsigned long timeout);
unsigned long mortos_openat(
    unsigned long directory, const char *path,
    unsigned long flags, unsigned long mode);
unsigned long mortos_fstat(unsigned long descriptor, void *status);
unsigned long mortos_newfstatat(
    unsigned long directory, const char *path,
    void *status, unsigned long flags);
unsigned long mortos_getdents64(
    unsigned long descriptor, void *buffer, unsigned long length);
unsigned long mortos_getcwd(void *buffer, unsigned long size);
unsigned long mortos_chdir(const char *path);
unsigned long mortos_getrandom(
    void *buffer, unsigned long length, unsigned long flags);
unsigned long mortos_eventfd2(unsigned long initial, unsigned long flags);
unsigned long mortos_epoll_create1(unsigned long flags);
unsigned long mortos_epoll_ctl(
    unsigned long epoll_descriptor, unsigned long operation,
    unsigned long descriptor, void *event);
unsigned long mortos_epoll_wait(
    unsigned long epoll_descriptor, void *events,
    unsigned long maxevents, unsigned long timeout);
unsigned long mortos_lseek(
    unsigned long descriptor, unsigned long offset, unsigned long origin);
unsigned long mortos_pread(
    unsigned long descriptor, void *buffer,
    unsigned long length, unsigned long offset);
unsigned long mortos_thread_create(
    unsigned long entry, unsigned long stack_top, unsigned long argument);
unsigned long mortos_thread_join(
    unsigned long thread, unsigned long *status);
void mortos_spin(unsigned long iterations);

#ifdef __cplusplus
}
#endif

#endif
