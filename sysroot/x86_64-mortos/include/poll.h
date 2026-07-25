#ifndef MORTOS_POLL_H
#define MORTOS_POLL_H

typedef unsigned long nfds_t;

struct pollfd {
    int fd;
    short events;
    short revents;
};

#define POLLIN 0x001
#define POLLOUT 0x004
#define POLLERR 0x008
#define POLLHUP 0x010
#define POLLNVAL 0x020

#ifdef __cplusplus
extern "C" {
#endif

int poll(struct pollfd *descriptors, nfds_t count, int timeout);

#ifdef __cplusplus
}
#endif

#endif
