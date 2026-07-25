#ifndef MORTOS_SYS_SOCKET_H
#define MORTOS_SYS_SOCKET_H

#include <sys/types.h>

typedef unsigned int socklen_t;
typedef unsigned short sa_family_t;

struct sockaddr {
    sa_family_t sa_family;
    char sa_data[14];
};

#define AF_UNSPEC 0
#define AF_INET 2
#define PF_INET AF_INET

#define SOCK_STREAM 1
#define SOCK_NONBLOCK 0x800
#define SOCK_CLOEXEC 0x80000

#define SOL_SOCKET 1
#define SO_ERROR 4
#define SO_TYPE 3

#ifdef __cplusplus
extern "C" {
#endif

int socket(int domain, int type, int protocol);
int getsockopt(
    int descriptor, int level, int option,
    void *value, socklen_t *length);

#ifdef __cplusplus
}
#endif

#endif
