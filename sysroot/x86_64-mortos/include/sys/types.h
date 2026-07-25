#ifndef MORTOS_SYS_TYPES_H
#define MORTOS_SYS_TYPES_H

#ifndef __MORTOS_SIZE_T_DEFINED
#define __MORTOS_SIZE_T_DEFINED
typedef unsigned long size_t;
#endif

typedef long ssize_t;
typedef long off_t;
typedef int pid_t;
typedef unsigned long dev_t;
typedef unsigned long ino_t;
typedef unsigned long nlink_t;
typedef unsigned int mode_t;
typedef unsigned int uid_t;
typedef unsigned int gid_t;
typedef long blksize_t;
typedef long blkcnt_t;
typedef long suseconds_t;
typedef unsigned int useconds_t;
typedef unsigned int id_t;

#endif
