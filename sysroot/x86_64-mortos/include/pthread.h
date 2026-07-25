#ifndef MORTOS_PTHREAD_H
#define MORTOS_PTHREAD_H

#include <sched.h>
#include <sys/types.h>
#include <time.h>

typedef unsigned long pthread_t;
typedef unsigned int pthread_key_t;
struct timespec;

typedef struct {
    size_t __stack_size;
    int __detach_state;
} pthread_attr_t;

typedef struct {
    int __type;
} pthread_mutexattr_t;

typedef struct {
    int __clock;
} pthread_condattr_t;

typedef struct {
    volatile unsigned int __state;
} pthread_once_t;

typedef struct {
    volatile unsigned int __state;
} pthread_mutex_t;

typedef struct {
    volatile unsigned int __sequence;
} pthread_cond_t;

typedef struct {
    volatile unsigned int __state;
} pthread_rwlock_t;

#define PTHREAD_MUTEX_INITIALIZER {0}
#define PTHREAD_COND_INITIALIZER {0}
#define PTHREAD_RWLOCK_INITIALIZER {0}
#define PTHREAD_ONCE_INIT {0}
#define PTHREAD_KEYS_MAX 64
#define PTHREAD_DESTRUCTOR_ITERATIONS 4
#define PTHREAD_CREATE_JOINABLE 0
#define PTHREAD_CREATE_DETACHED 1
#define PTHREAD_MUTEX_NORMAL 0
#define PTHREAD_MUTEX_RECURSIVE 1

#ifdef __cplusplus
extern "C" {
#endif

int pthread_create(
    pthread_t *thread,
    const void *attributes,
    void *(*start)(void *),
    void *argument);
int pthread_join(pthread_t thread, void **result);
int pthread_detach(pthread_t thread);
pthread_t pthread_self(void);
int pthread_equal(pthread_t left, pthread_t right);
int pthread_getschedparam(
    pthread_t thread, int *policy, struct sched_param *parameters);
int pthread_setschedparam(
    pthread_t thread, int policy, const struct sched_param *parameters);
int pthread_atfork(
    void (*prepare)(void), void (*parent)(void), void (*child)(void));
int pthread_attr_init(pthread_attr_t *attributes);
int pthread_attr_destroy(pthread_attr_t *attributes);
int pthread_attr_setstacksize(pthread_attr_t *attributes, size_t stack_size);
int pthread_attr_getstacksize(
    const pthread_attr_t *attributes, size_t *stack_size);
int pthread_attr_setdetachstate(pthread_attr_t *attributes, int state);
int pthread_mutexattr_init(pthread_mutexattr_t *attributes);
int pthread_mutexattr_destroy(pthread_mutexattr_t *attributes);
int pthread_mutexattr_settype(pthread_mutexattr_t *attributes, int type);
int pthread_condattr_init(pthread_condattr_t *attributes);
int pthread_condattr_destroy(pthread_condattr_t *attributes);
int pthread_condattr_setclock(pthread_condattr_t *attributes, clockid_t clock);
int pthread_setname_np(pthread_t thread, const char *name);
int pthread_getname_np(pthread_t thread, char *name, size_t length);
int pthread_once(pthread_once_t *once, void (*initialize)(void));
int pthread_key_create(pthread_key_t *key, void (*destructor)(void *));
int pthread_key_delete(pthread_key_t key);
void *pthread_getspecific(pthread_key_t key);
int pthread_setspecific(pthread_key_t key, const void *value);

int pthread_mutex_init(pthread_mutex_t *mutex, const void *attributes);
int pthread_mutex_destroy(pthread_mutex_t *mutex);
int pthread_mutex_lock(pthread_mutex_t *mutex);
int pthread_mutex_trylock(pthread_mutex_t *mutex);
int pthread_mutex_unlock(pthread_mutex_t *mutex);

int pthread_cond_init(pthread_cond_t *condition, const void *attributes);
int pthread_cond_destroy(pthread_cond_t *condition);
int pthread_cond_wait(pthread_cond_t *condition, pthread_mutex_t *mutex);
int pthread_cond_timedwait(
    pthread_cond_t *condition,
    pthread_mutex_t *mutex,
    const struct timespec *absolute_timeout);
int pthread_cond_clockwait(
    pthread_cond_t *condition,
    pthread_mutex_t *mutex,
    int clock,
    const struct timespec *absolute_timeout);
int pthread_cond_signal(pthread_cond_t *condition);
int pthread_cond_broadcast(pthread_cond_t *condition);

int pthread_rwlock_init(pthread_rwlock_t *lock, const void *attributes);
int pthread_rwlock_destroy(pthread_rwlock_t *lock);
int pthread_rwlock_rdlock(pthread_rwlock_t *lock);
int pthread_rwlock_tryrdlock(pthread_rwlock_t *lock);
int pthread_rwlock_wrlock(pthread_rwlock_t *lock);
int pthread_rwlock_trywrlock(pthread_rwlock_t *lock);
int pthread_rwlock_unlock(pthread_rwlock_t *lock);

#ifdef __cplusplus
}
#endif

#endif
