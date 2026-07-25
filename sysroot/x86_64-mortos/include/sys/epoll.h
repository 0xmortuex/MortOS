#ifndef MORTOS_SYS_EPOLL_H
#define MORTOS_SYS_EPOLL_H

typedef union epoll_data {
    void *ptr;
    int fd;
    unsigned int u32;
    unsigned long u64;
} epoll_data_t;

struct __attribute__((packed)) epoll_event {
    unsigned int events;
    epoll_data_t data;
};

#define EPOLLIN 0x001
#define EPOLLOUT 0x004
#define EPOLLERR 0x008
#define EPOLLHUP 0x010

#define EPOLL_CTL_ADD 1
#define EPOLL_CTL_DEL 2
#define EPOLL_CTL_MOD 3
#define EPOLL_CLOEXEC 0x80000

#ifdef __cplusplus
extern "C" {
#endif

int epoll_create1(int flags);
int epoll_ctl(
    int epoll_descriptor,
    int operation,
    int descriptor,
    struct epoll_event *event);
int epoll_wait(
    int epoll_descriptor,
    struct epoll_event *events,
    int maxevents,
    int timeout);

#ifdef __cplusplus
}
#endif

#endif
