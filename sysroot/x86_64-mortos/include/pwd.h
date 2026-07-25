#ifndef MORTOS_PWD_H
#define MORTOS_PWD_H

#include <sys/types.h>

struct passwd {
    char *pw_name;
    char *pw_passwd;
    uid_t pw_uid;
    gid_t pw_gid;
    char *pw_gecos;
    char *pw_dir;
    char *pw_shell;
};

#ifdef __cplusplus
extern "C" {
#endif

struct passwd *getpwnam(const char *name);
struct passwd *getpwuid(uid_t uid);
int getpwnam_r(
    const char *name, struct passwd *record, char *buffer,
    size_t buffer_length, struct passwd **result);
int getpwuid_r(
    uid_t uid, struct passwd *record, char *buffer,
    size_t buffer_length, struct passwd **result);

#ifdef __cplusplus
}
#endif

#endif
