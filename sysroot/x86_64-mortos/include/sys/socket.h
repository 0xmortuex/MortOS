#ifndef MORTOS_SYS_SOCKET_H
#define MORTOS_SYS_SOCKET_H

#include <sys/types.h>
#include <sys/uio.h>

typedef unsigned int socklen_t;
typedef unsigned short sa_family_t;

struct sockaddr {
    sa_family_t sa_family;
    char sa_data[14];
};

struct msghdr {
    void *msg_name;
    socklen_t msg_namelen;
    struct iovec *msg_iov;
    size_t msg_iovlen;
    void *msg_control;
    size_t msg_controllen;
    int msg_flags;
};

#define AF_UNSPEC 0
#define AF_INET 2
#define PF_INET AF_INET

#define SOCK_STREAM 1
#define SOCK_NONBLOCK 0x800
#define SOCK_CLOEXEC 0x80000

#define SOL_SOCKET 1
#define SO_REUSEADDR 2
#define SO_ERROR 4
#define SO_TYPE 3
#define SO_SNDBUF 7
#define SO_RCVBUF 8
#define SO_KEEPALIVE 9

#define MSG_DONTWAIT 0x40
#define MSG_NOSIGNAL 0x4000

#define SHUT_RD 0
#define SHUT_WR 1
#define SHUT_RDWR 2

#ifdef __cplusplus
extern "C" {
#endif

int socket(int domain, int type, int protocol);
int connect(
    int descriptor, const struct sockaddr *address, socklen_t length);
ssize_t send(
    int descriptor, const void *buffer, size_t length, int flags);
ssize_t recv(int descriptor, void *buffer, size_t length, int flags);
ssize_t sendmsg(
    int descriptor, const struct msghdr *message, int flags);
ssize_t recvmsg(int descriptor, struct msghdr *message, int flags);
int shutdown(int descriptor, int how);
int getsockname(
    int descriptor, struct sockaddr *address, socklen_t *length);
int getpeername(
    int descriptor, struct sockaddr *address, socklen_t *length);
int setsockopt(
    int descriptor, int level, int option,
    const void *value, socklen_t length);
int getsockopt(
    int descriptor, int level, int option,
    void *value, socklen_t *length);

#ifdef __cplusplus
}
#endif

#endif
