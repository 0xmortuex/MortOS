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

struct sockaddr_storage {
    sa_family_t ss_family;
    char __data[118];
    unsigned long __align;
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

struct cmsghdr {
    size_t cmsg_len;
    int cmsg_level;
    int cmsg_type;
};

#define __MORTOS_CMSG_ALIGN(length) \
    (((length) + sizeof(size_t) - 1) & ~(sizeof(size_t) - 1))
#define CMSG_ALIGN(length) __MORTOS_CMSG_ALIGN(length)
#define CMSG_SPACE(length) \
    (CMSG_ALIGN(sizeof(struct cmsghdr)) + CMSG_ALIGN(length))
#define CMSG_LEN(length) \
    (CMSG_ALIGN(sizeof(struct cmsghdr)) + (length))
#define CMSG_DATA(header) \
    ((unsigned char *)(header) + CMSG_ALIGN(sizeof(struct cmsghdr)))
#define CMSG_FIRSTHDR(message) \
    ((message)->msg_controllen >= sizeof(struct cmsghdr) ? \
        (struct cmsghdr *)(message)->msg_control : (struct cmsghdr *)0)
#define CMSG_NXTHDR(message, header) \
    (((char *)(header) + CMSG_ALIGN((header)->cmsg_len) + \
      CMSG_ALIGN(sizeof(struct cmsghdr)) > \
      (char *)(message)->msg_control + (message)->msg_controllen) ? \
        (struct cmsghdr *)0 : \
        (struct cmsghdr *)((char *)(header) + \
                          CMSG_ALIGN((header)->cmsg_len)))

#define AF_UNSPEC 0
#define AF_UNIX 1
#define AF_INET 2
#define AF_INET6 10
#define PF_UNSPEC AF_UNSPEC
#define PF_UNIX AF_UNIX
#define PF_INET AF_INET
#define PF_INET6 AF_INET6

#define SOCK_STREAM 1
#define SOCK_DGRAM 2
#define SOCK_RAW 3
#define SOCK_SEQPACKET 5
#define SOCK_NONBLOCK 0x800
#define SOCK_CLOEXEC 0x80000

#define SOL_SOCKET 1
#define SCM_RIGHTS 1
#define SO_REUSEADDR 2
#define SO_ERROR 4
#define SO_TYPE 3
#define SO_SNDBUF 7
#define SO_RCVBUF 8
#define SO_KEEPALIVE 9
#define SO_BROADCAST 6
#define SO_LINGER 13
#define SO_ACCEPTCONN 30

#define MSG_DONTWAIT 0x40
#define MSG_TRUNC 0x20
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
int bind(
    int descriptor, const struct sockaddr *address, socklen_t length);
int listen(int descriptor, int backlog);
int accept(
    int descriptor, struct sockaddr *address, socklen_t *length);
int accept4(
    int descriptor, struct sockaddr *address, socklen_t *length, int flags);
ssize_t send(
    int descriptor, const void *buffer, size_t length, int flags);
ssize_t recv(int descriptor, void *buffer, size_t length, int flags);
ssize_t sendto(
    int descriptor, const void *buffer, size_t length, int flags,
    const struct sockaddr *address, socklen_t address_length);
ssize_t recvfrom(
    int descriptor, void *buffer, size_t length, int flags,
    struct sockaddr *address, socklen_t *address_length);
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
int socketpair(int domain, int type, int protocol, int descriptors[2]);

#ifdef __cplusplus
}
#endif

#endif
