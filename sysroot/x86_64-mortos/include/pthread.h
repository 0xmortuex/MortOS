#ifndef MORTOS_PTHREAD_H
#define MORTOS_PTHREAD_H

typedef unsigned long pthread_t;

#ifdef __cplusplus
extern "C" {
#endif

int pthread_create(
    pthread_t *thread,
    const void *attributes,
    void *(*start)(void *),
    void *argument);
pthread_t pthread_self(void);

#ifdef __cplusplus
}
#endif

#endif
