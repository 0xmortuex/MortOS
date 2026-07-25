#ifndef MORTOS_SYS_RESOURCE_H
#define MORTOS_SYS_RESOURCE_H

#include <sys/time.h>

typedef unsigned long rlim_t;

struct rlimit {
    rlim_t rlim_cur;
    rlim_t rlim_max;
};

struct rusage {
    struct timeval ru_utime;
    struct timeval ru_stime;
    long ru_maxrss;
    long ru_ixrss;
    long ru_idrss;
    long ru_isrss;
    long ru_minflt;
    long ru_majflt;
    long ru_nswap;
    long ru_inblock;
    long ru_oublock;
    long ru_msgsnd;
    long ru_msgrcv;
    long ru_nsignals;
    long ru_nvcsw;
    long ru_nivcsw;
};

#define RUSAGE_SELF 0
#define RUSAGE_CHILDREN (-1)
#define RUSAGE_THREAD 1

#define PRIO_PROCESS 0
#define PRIO_PGRP 1
#define PRIO_USER 2

#define RLIMIT_DATA 2
#define RLIMIT_STACK 3
#define RLIMIT_NOFILE 7
#define RLIMIT_AS 9
#define RLIM_INFINITY (~(rlim_t)0)

#ifdef __cplusplus
extern "C" {
#endif

int getrlimit(int resource, struct rlimit *limits);
int setrlimit(int resource, const struct rlimit *limits);
int getrusage(int who, struct rusage *usage);
int getpriority(int which, id_t who);
int setpriority(int which, id_t who, int priority);

#ifdef __cplusplus
}
#endif

#endif
