#ifndef MORTOS_SEMAPHORE_H
#define MORTOS_SEMAPHORE_H

typedef struct {
    volatile unsigned int __value;
} sem_t;

#define SEM_VALUE_MAX 0x7FFFFFFF

#ifdef __cplusplus
extern "C" {
#endif

int sem_init(sem_t *semaphore, int process_shared, unsigned int value);
int sem_destroy(sem_t *semaphore);
int sem_wait(sem_t *semaphore);
int sem_trywait(sem_t *semaphore);
int sem_post(sem_t *semaphore);
int sem_getvalue(sem_t *semaphore, int *value);

#ifdef __cplusplus
}
#endif

#endif
