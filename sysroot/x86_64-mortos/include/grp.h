#ifndef MORTOS_GRP_H
#define MORTOS_GRP_H

#include <sys/types.h>

struct group {
    char *gr_name;
    char *gr_passwd;
    gid_t gr_gid;
    char **gr_mem;
};

#ifdef __cplusplus
extern "C" {
#endif

struct group *getgrnam(const char *name);
struct group *getgrgid(gid_t gid);
int getgrnam_r(
    const char *name, struct group *record, char *buffer,
    size_t buffer_length, struct group **result);
int getgrgid_r(
    gid_t gid, struct group *record, char *buffer,
    size_t buffer_length, struct group **result);
int getgrouplist(
    const char *user, gid_t group, gid_t *groups, int *group_count);
int setgroups(size_t count, const gid_t *groups);

#ifdef __cplusplus
}
#endif

#endif
