#ifndef MORTOS_SYS_TIME_H
#define MORTOS_SYS_TIME_H

#include <sys/types.h>
#include <time.h>

struct timeval {
    time_t tv_sec;
    suseconds_t tv_usec;
};

struct timezone {
    int tz_minuteswest;
    int tz_dsttime;
};

#ifdef __cplusplus
extern "C" {
#endif

int gettimeofday(struct timeval *time, struct timezone *zone);

#ifdef __cplusplus
}
#endif

#endif
