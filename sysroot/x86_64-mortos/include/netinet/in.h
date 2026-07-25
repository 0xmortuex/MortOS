#ifndef MORTOS_NETINET_IN_H
#define MORTOS_NETINET_IN_H

#include <sys/socket.h>

typedef unsigned int in_addr_t;
typedef unsigned short in_port_t;

struct in_addr {
    in_addr_t s_addr;
};

struct sockaddr_in {
    sa_family_t sin_family;
    in_port_t sin_port;
    struct in_addr sin_addr;
    unsigned char sin_zero[8];
};

#define IPPROTO_IP 0
#define IPPROTO_TCP 6

#define INADDR_ANY ((in_addr_t)0x00000000U)

#ifdef __cplusplus
extern "C" {
#endif

unsigned int htonl(unsigned int value);
unsigned short htons(unsigned short value);
unsigned int ntohl(unsigned int value);
unsigned short ntohs(unsigned short value);

#ifdef __cplusplus
}
#endif

#endif
