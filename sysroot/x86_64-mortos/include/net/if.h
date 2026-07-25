#ifndef MORTOS_NET_IF_H
#define MORTOS_NET_IF_H

#define IF_NAMESIZE 16
#define IFNAMSIZ IF_NAMESIZE

struct if_nameindex {
    unsigned int if_index;
    char *if_name;
};

#ifdef __cplusplus
extern "C" {
#endif

unsigned int if_nametoindex(const char *name);
char *if_indextoname(unsigned int index, char name[IF_NAMESIZE]);
struct if_nameindex *if_nameindex(void);
void if_freenameindex(struct if_nameindex *entries);

#ifdef __cplusplus
}
#endif

#endif
