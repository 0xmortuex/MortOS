#ifndef MORTOS_DIRENT_H
#define MORTOS_DIRENT_H

#include <sys/types.h>

#define DT_UNKNOWN 0
#define DT_FIFO 1
#define DT_CHR 2
#define DT_DIR 4
#define DT_BLK 6
#define DT_REG 8
#define DT_LNK 10
#define DT_SOCK 12

struct dirent {
    ino_t d_ino;
    off_t d_off;
    unsigned short d_reclen;
    unsigned char d_type;
    char d_name[256];
};

typedef struct __mortos_dir_stream DIR;

#ifdef __cplusplus
extern "C" {
#endif

DIR *opendir(const char *path);
DIR *fdopendir(int descriptor);
struct dirent *readdir(DIR *directory);
int readdir_r(DIR *directory, struct dirent *entry, struct dirent **result);
void rewinddir(DIR *directory);
void seekdir(DIR *directory, long position);
long telldir(DIR *directory);
int dirfd(DIR *directory);
int closedir(DIR *directory);

#ifdef __cplusplus
}
#endif

#endif
