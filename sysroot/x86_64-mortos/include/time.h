#ifndef MORTOS_TIME_H
#define MORTOS_TIME_H

typedef int clockid_t;
typedef long time_t;

struct timespec {
    time_t tv_sec;
    long tv_nsec;
};

#define CLOCK_MONOTONIC 1
#define TIMER_ABSTIME 1

#ifdef __cplusplus
extern "C" {
#endif

int clock_gettime(clockid_t clock, struct timespec *time);
int clock_getres(clockid_t clock, struct timespec *resolution);
int clock_nanosleep(
    clockid_t clock,
    int flags,
    const struct timespec *request,
    struct timespec *remaining);
int nanosleep(
    const struct timespec *request,
    struct timespec *remaining);

#ifdef __cplusplus
}
#endif

#endif
