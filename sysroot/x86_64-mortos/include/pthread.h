#ifndef MORTOS_PTHREAD_H
#define MORTOS_PTHREAD_H

typedef unsigned long pthread_t;
typedef unsigned int pthread_key_t;
struct timespec;

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
