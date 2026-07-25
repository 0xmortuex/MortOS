#ifndef MORTOS_PTHREAD_H
#define MORTOS_PTHREAD_H

typedef unsigned long pthread_t;

typedef struct {
    volatile unsigned int __state;
} pthread_mutex_t;

typedef struct {
    volatile unsigned int __sequence;
} pthread_cond_t;

#define PTHREAD_MUTEX_INITIALIZER {0}
#define PTHREAD_COND_INITIALIZER {0}

#ifdef __cplusplus
extern "C" {
#endif

int pthread_create(
    pthread_t *thread,
    const void *attributes,
    void *(*start)(void *),
    void *argument);
int pthread_join(pthread_t thread, void **result);
pthread_t pthread_self(void);
int pthread_equal(pthread_t left, pthread_t right);

int pthread_mutex_init(pthread_mutex_t *mutex, const void *attributes);
int pthread_mutex_destroy(pthread_mutex_t *mutex);
int pthread_mutex_lock(pthread_mutex_t *mutex);
int pthread_mutex_trylock(pthread_mutex_t *mutex);
int pthread_mutex_unlock(pthread_mutex_t *mutex);

int pthread_cond_init(pthread_cond_t *condition, const void *attributes);
int pthread_cond_destroy(pthread_cond_t *condition);
int pthread_cond_wait(pthread_cond_t *condition, pthread_mutex_t *mutex);
int pthread_cond_signal(pthread_cond_t *condition);
int pthread_cond_broadcast(pthread_cond_t *condition);

#ifdef __cplusplus
}
#endif

#endif
