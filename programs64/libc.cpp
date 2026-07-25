// First reusable libc slice for x86_64-mortos.
//
// The CRT establishes one TLS page for the main thread before constructors.
// FS:0 is the self pointer, FS:8 stores errno, and FS:40 carries the stack
// protector canary sourced from the kernel-provided AT_RANDOM bytes.

#include <errno.h>
#include <mortos/syscall.h>
#include <pthread.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <unistd.h>

static constexpr unsigned long ERROR_LIMIT = ~4095UL;

static long posix_result(unsigned long result) {
    if (result >= ERROR_LIMIT) {
        errno = static_cast<int>((~result) + 1);
        return -1;
    }
    return static_cast<long>(result);
}

extern "C" int *__errno_location() {
    unsigned long self = mortos_fs_load(0);
    return reinterpret_cast<int *>(self + 8);
}

extern "C" unsigned long mortos_runtime_start(unsigned long *stack) {
    unsigned long tls = mortos_mmap(
        0, 4096, PROT_READ | PROT_WRITE,
        MAP_PRIVATE | MAP_ANONYMOUS, ~0UL, 0);
    if (tls >= ERROR_LIMIT
        || mortos_arch_prctl(0x1002, tls) != 0) {
        return 0;
    }
    *reinterpret_cast<unsigned long *>(tls) = tls;
    *reinterpret_cast<int *>(tls + 8) = 0;

    unsigned long argc = stack[0];
    unsigned long *environment = stack + 2 + argc;
    while (*environment) {
        ++environment;
    }
    unsigned long *auxiliary = environment + 1;
    unsigned long random = 0;
    for (unsigned long index = 0; index < 32; ++index) {
        unsigned long type = auxiliary[index * 2];
        if (type == 0) {
            break;
        }
        if (type == 25) {
            random = auxiliary[index * 2 + 1];
        }
    }
    if (!random) {
        return 0;
    }
    unsigned long canary =
        *reinterpret_cast<const unsigned long *>(random);
    if (canary == 0) {
        canary = 0x4D4F525443414E59UL;
    }
    *reinterpret_cast<unsigned long *>(tls + 40) = canary;
    return tls;
}

extern "C" [[noreturn]] void __stack_chk_fail() {
    __asm__ volatile("ud2");
    for (;;) {
    }
}

extern "C" ssize_t read(int descriptor, void *buffer, size_t length) {
    return static_cast<ssize_t>(posix_result(
        mortos_read(static_cast<unsigned long>(descriptor), buffer, length)));
}

extern "C" ssize_t write(
    int descriptor, const void *buffer, size_t length
) {
    return static_cast<ssize_t>(posix_result(mortos_fd_write(
        static_cast<unsigned long>(descriptor), buffer, length)));
}

extern "C" int close(int descriptor) {
    return static_cast<int>(posix_result(
        mortos_close(static_cast<unsigned long>(descriptor))));
}

extern "C" pid_t getpid() {
    return static_cast<pid_t>(mortos_getpid());
}

extern "C" pid_t gettid() {
    return static_cast<pid_t>(mortos_gettid());
}

extern "C" off_t lseek(int descriptor, off_t offset, int origin) {
    return static_cast<off_t>(posix_result(mortos_lseek(
        static_cast<unsigned long>(descriptor),
        static_cast<unsigned long>(offset),
        static_cast<unsigned long>(origin))));
}

extern "C" void *mmap(
    void *address,
    size_t length,
    int protection,
    int flags,
    int descriptor,
    off_t offset
) {
    unsigned long result = mortos_mmap(
        reinterpret_cast<unsigned long>(address), length,
        static_cast<unsigned long>(protection),
        static_cast<unsigned long>(flags),
        static_cast<unsigned long>(descriptor),
        static_cast<unsigned long>(offset));
    if (result >= ERROR_LIMIT) {
        errno = static_cast<int>((~result) + 1);
        return MAP_FAILED;
    }
    return reinterpret_cast<void *>(result);
}

extern "C" int mprotect(void *address, size_t length, int protection) {
    return static_cast<int>(posix_result(mortos_mprotect(
        reinterpret_cast<unsigned long>(address), length,
        static_cast<unsigned long>(protection))));
}

extern "C" int munmap(void *address, size_t length) {
    return static_cast<int>(posix_result(mortos_munmap(
        reinterpret_cast<unsigned long>(address), length)));
}

struct PthreadStartContext {
    void *(*start)(void *);
    void *argument;
    unsigned long tls;
};

struct PthreadRecord {
    volatile unsigned int claimed;
    pthread_t thread;
    unsigned long stack;
    unsigned long tls;
};

static PthreadRecord pthread_records[8] = {};

extern "C" __attribute__((no_stack_protector))
unsigned long mortos_pthread_start(void *opaque) {
    auto *context = static_cast<PthreadStartContext *>(opaque);
    auto start = context->start;
    void *argument = context->argument;
    unsigned long tls = context->tls;
    if (mortos_arch_prctl(0x1002, tls) != 0) {
        return 126;
    }
    free(context);
    return reinterpret_cast<unsigned long>(start(argument));
}

extern "C" int pthread_create(
    pthread_t *thread,
    const void *attributes,
    void *(*start)(void *),
    void *argument
) {
    if (!thread || !start || attributes) {
        return EINVAL;
    }
    PthreadRecord *record = nullptr;
    for (unsigned long index = 0; index < 8; ++index) {
        unsigned int expected = 0;
        if (__atomic_compare_exchange_n(
                &pthread_records[index].claimed, &expected, 1U, false,
                __ATOMIC_ACQUIRE, __ATOMIC_RELAXED)) {
            record = &pthread_records[index];
            break;
        }
    }
    if (!record) {
        return EAGAIN;
    }
    unsigned long stack = mortos_mmap(
        0, 65536, PROT_READ | PROT_WRITE,
        MAP_PRIVATE | MAP_ANONYMOUS, ~0UL, 0);
    unsigned long tls = mortos_mmap(
        0, 4096, PROT_READ | PROT_WRITE,
        MAP_PRIVATE | MAP_ANONYMOUS, ~0UL, 0);
    if (stack >= ERROR_LIMIT || tls >= ERROR_LIMIT) {
        if (stack < ERROR_LIMIT) {
            mortos_munmap(stack, 65536);
        }
        if (tls < ERROR_LIMIT) {
            mortos_munmap(tls, 4096);
        }
        __atomic_store_n(&record->claimed, 0U, __ATOMIC_RELEASE);
        return EAGAIN;
    }
    unsigned long parent_tls = mortos_fs_load(0);
    *reinterpret_cast<unsigned long *>(tls) = tls;
    *reinterpret_cast<int *>(tls + 8) = 0;
    *reinterpret_cast<unsigned long *>(tls + 40) =
        *reinterpret_cast<unsigned long *>(parent_tls + 40);
    auto *context = static_cast<PthreadStartContext *>(
        malloc(sizeof(PthreadStartContext)));
    if (!context) {
        mortos_munmap(stack, 65536);
        mortos_munmap(tls, 4096);
        __atomic_store_n(&record->claimed, 0U, __ATOMIC_RELEASE);
        return EAGAIN;
    }
    context->start = start;
    context->argument = argument;
    context->tls = tls;
    unsigned long result = mortos_thread_create(
        reinterpret_cast<unsigned long>(&mortos_pthread_start),
        stack + 65536,
        reinterpret_cast<unsigned long>(context));
    if (result >= ERROR_LIMIT) {
        free(context);
        mortos_munmap(stack, 65536);
        mortos_munmap(tls, 4096);
        __atomic_store_n(&record->claimed, 0U, __ATOMIC_RELEASE);
        return static_cast<int>((~result) + 1);
    }
    record->thread = result;
    record->stack = stack;
    record->tls = tls;
    *thread = result;
    return 0;
}

extern "C" int pthread_join(pthread_t thread, void **result) {
    PthreadRecord *record = nullptr;
    for (unsigned long index = 0; index < 8; ++index) {
        if (__atomic_load_n(
                &pthread_records[index].claimed, __ATOMIC_ACQUIRE) == 1
            && pthread_records[index].thread == thread) {
            unsigned int expected = 1;
            if (__atomic_compare_exchange_n(
                    &pthread_records[index].claimed, &expected, 2U, false,
                    __ATOMIC_ACQUIRE, __ATOMIC_RELAXED)) {
                record = &pthread_records[index];
                break;
            }
        }
    }
    if (!record) {
        return ESRCH;
    }
    unsigned long status = 0;
    unsigned long join_result = mortos_thread_join(thread, &status);
    if (join_result >= ERROR_LIMIT) {
        __atomic_store_n(&record->claimed, 1U, __ATOMIC_RELEASE);
        return static_cast<int>((~join_result) + 1);
    }
    mortos_munmap(record->stack, 65536);
    mortos_munmap(record->tls, 4096);
    record->thread = 0;
    record->stack = 0;
    record->tls = 0;
    __atomic_store_n(&record->claimed, 0U, __ATOMIC_RELEASE);
    if (result) {
        *result = reinterpret_cast<void *>(status);
    }
    return 0;
}

extern "C" pthread_t pthread_self() {
    return static_cast<pthread_t>(mortos_gettid());
}

extern "C" int pthread_equal(pthread_t left, pthread_t right) {
    return left == right;
}

static int pthread_futex_error(unsigned long result) {
    if (result < ERROR_LIMIT) {
        return 0;
    }
    return static_cast<int>((~result) + 1);
}

extern "C" int pthread_mutex_init(
    pthread_mutex_t *mutex,
    const void *attributes
) {
    if (!mutex || attributes) {
        return EINVAL;
    }
    __atomic_store_n(&mutex->__state, 0U, __ATOMIC_RELAXED);
    return 0;
}

extern "C" int pthread_mutex_destroy(pthread_mutex_t *mutex) {
    if (!mutex) {
        return EINVAL;
    }
    return __atomic_load_n(&mutex->__state, __ATOMIC_ACQUIRE) == 0
        ? 0 : EBUSY;
}

extern "C" int pthread_mutex_trylock(pthread_mutex_t *mutex) {
    if (!mutex) {
        return EINVAL;
    }
    unsigned int expected = 0;
    return __atomic_compare_exchange_n(
        &mutex->__state, &expected, 1U, false,
        __ATOMIC_ACQUIRE, __ATOMIC_RELAXED) ? 0 : EBUSY;
}

extern "C" int pthread_mutex_lock(pthread_mutex_t *mutex) {
    if (!mutex) {
        return EINVAL;
    }
    for (;;) {
        unsigned int expected = 0;
        if (__atomic_compare_exchange_n(
                &mutex->__state, &expected, 1U, false,
                __ATOMIC_ACQUIRE, __ATOMIC_RELAXED)) {
            return 0;
        }
        int error = pthread_futex_error(mortos_futex(
            const_cast<unsigned int *>(&mutex->__state), 0, 1));
        if (error != 0 && error != EAGAIN) {
            return error;
        }
    }
}

extern "C" int pthread_mutex_unlock(pthread_mutex_t *mutex) {
    if (!mutex) {
        return EINVAL;
    }
    unsigned int expected = 1;
    if (!__atomic_compare_exchange_n(
            &mutex->__state, &expected, 0U, false,
            __ATOMIC_RELEASE, __ATOMIC_RELAXED)) {
        return EPERM;
    }
    return pthread_futex_error(mortos_futex(
        const_cast<unsigned int *>(&mutex->__state), 1, 1));
}

extern "C" int pthread_cond_init(
    pthread_cond_t *condition,
    const void *attributes
) {
    if (!condition || attributes) {
        return EINVAL;
    }
    __atomic_store_n(&condition->__sequence, 0U, __ATOMIC_RELAXED);
    return 0;
}

extern "C" int pthread_cond_destroy(pthread_cond_t *condition) {
    return condition ? 0 : EINVAL;
}

extern "C" int pthread_cond_wait(
    pthread_cond_t *condition,
    pthread_mutex_t *mutex
) {
    if (!condition || !mutex) {
        return EINVAL;
    }
    unsigned int sequence = __atomic_load_n(
        &condition->__sequence, __ATOMIC_ACQUIRE);
    int unlock_error = pthread_mutex_unlock(mutex);
    if (unlock_error != 0) {
        return unlock_error;
    }
    int wait_error = pthread_futex_error(mortos_futex(
        const_cast<unsigned int *>(&condition->__sequence), 0, sequence));
    int lock_error = pthread_mutex_lock(mutex);
    if (lock_error != 0) {
        return lock_error;
    }
    return wait_error == EAGAIN ? 0 : wait_error;
}

extern "C" int pthread_cond_signal(pthread_cond_t *condition) {
    if (!condition) {
        return EINVAL;
    }
    __atomic_add_fetch(&condition->__sequence, 1U, __ATOMIC_RELEASE);
    return pthread_futex_error(mortos_futex(
        const_cast<unsigned int *>(&condition->__sequence), 1, 1));
}

extern "C" int pthread_cond_broadcast(pthread_cond_t *condition) {
    if (!condition) {
        return EINVAL;
    }
    __atomic_add_fetch(&condition->__sequence, 1U, __ATOMIC_RELEASE);
    return pthread_futex_error(mortos_futex(
        const_cast<unsigned int *>(&condition->__sequence), 1, 8));
}
