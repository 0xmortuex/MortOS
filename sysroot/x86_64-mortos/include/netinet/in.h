#ifndef MORTOS_NETINET_IN_H
#define MORTOS_NETINET_IN_H

#include <sys/socket.h>

typedef unsigned int in_addr_t;
typedef unsigned short in_port_t;

struct in_addr {
    in_addr_t s_addr;
};

struct in6_addr {
    unsigned char s6_addr[16];
};

struct sockaddr_in {
    sa_family_t sin_family;
    in_port_t sin_port;
    struct in_addr sin_addr;
    unsigned char sin_zero[8];
};

struct sockaddr_in6 {
    sa_family_t sin6_family;
    in_port_t sin6_port;
    unsigned int sin6_flowinfo;
    struct in6_addr sin6_addr;
    unsigned int sin6_scope_id;
};

#define IPPROTO_IP 0
#define IPPROTO_ICMP 1
#define IPPROTO_TCP 6
#define IPPROTO_UDP 17
#define IPPROTO_IPV6 41

#define INADDR_ANY ((in_addr_t)0x00000000U)
#define INADDR_LOOPBACK ((in_addr_t)0x7F000001U)
#define IN6ADDR_ANY_INIT {{0, 0, 0, 0, 0, 0, 0, 0, \
                           0, 0, 0, 0, 0, 0, 0, 0}}
#define IN6ADDR_LOOPBACK_INIT {{0, 0, 0, 0, 0, 0, 0, 0, \
                                0, 0, 0, 0, 0, 0, 0, 1}}

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
