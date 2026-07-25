// First reusable libc slice for x86_64-mortos.
//
// The CRT establishes one TLS page for the main thread before constructors.
// FS:0 is the self pointer, FS:8 stores errno, and FS:40 carries the stack
// protector canary sourced from the kernel-provided AT_RANDOM bytes.

#include <errno.h>
#include <fcntl.h>
#include <mortos/syscall.h>
#include <poll.h>
#include <pthread.h>
#include <semaphore.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <sys/epoll.h>
#include <sys/eventfd.h>
#include <sys/socket.h>
#include <time.h>
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

extern "C" int socket(int domain, int type, int protocol) {
    return static_cast<int>(posix_result(mortos_socket(
        static_cast<unsigned long>(domain),
        static_cast<unsigned long>(type),
        static_cast<unsigned long>(protocol))));
}

extern "C" int getsockopt(
    int descriptor,
    int level,
    int option,
    void *value,
    socklen_t *length
) {
    return static_cast<int>(posix_result(mortos_getsockopt(
        static_cast<unsigned long>(descriptor),
        static_cast<unsigned long>(level),
        static_cast<unsigned long>(option), value, length)));
}

extern "C" int fcntl(int descriptor, int command, ...) {
    unsigned long argument = 0;
    if (command == F_SETFD || command == F_SETFL) {
        __builtin_va_list arguments;
        __builtin_va_start(arguments, command);
        argument = static_cast<unsigned long>(
            __builtin_va_arg(arguments, int));
        __builtin_va_end(arguments);
    }
    return static_cast<int>(posix_result(mortos_fcntl(
        static_cast<unsigned long>(descriptor),
        static_cast<unsigned long>(command), argument)));
}

extern "C" int openat(
    int directory,
    const char *path,
    int flags,
    ...
) {
    return static_cast<int>(posix_result(mortos_openat(
        static_cast<unsigned long>(directory), path,
        static_cast<unsigned long>(flags), 0)));
}

extern "C" int open(const char *path, int flags, ...) {
    return openat(AT_FDCWD, path, flags, 0);
}

extern "C" int pipe2(int descriptors[2], int flags) {
    return static_cast<int>(posix_result(mortos_pipe2(
        reinterpret_cast<unsigned int *>(descriptors),
        static_cast<unsigned long>(flags))));
}

extern "C" int pipe(int descriptors[2]) {
    return pipe2(descriptors, 0);
}

extern "C" int poll(
    struct pollfd *descriptors,
    nfds_t count,
    int timeout
) {
    return static_cast<int>(posix_result(mortos_poll(
        descriptors, count, static_cast<unsigned long>(timeout))));
}

extern "C" int eventfd(unsigned int initial, int flags) {
    return static_cast<int>(posix_result(mortos_eventfd2(
        initial, static_cast<unsigned long>(flags))));
}

extern "C" int eventfd_read(int descriptor, eventfd_t *value) {
    if (!value) {
        errno = EFAULT;
        return -1;
    }
    return read(descriptor, value, sizeof(*value)) == sizeof(*value)
        ? 0 : -1;
}

extern "C" int eventfd_write(int descriptor, eventfd_t value) {
    return write(descriptor, &value, sizeof(value)) == sizeof(value)
        ? 0 : -1;
}

extern "C" int epoll_create1(int flags) {
    return static_cast<int>(posix_result(mortos_epoll_create1(
        static_cast<unsigned long>(flags))));
}

extern "C" int epoll_ctl(
    int epoll_descriptor,
    int operation,
    int descriptor,
    struct epoll_event *event
) {
    return static_cast<int>(posix_result(mortos_epoll_ctl(
        static_cast<unsigned long>(epoll_descriptor),
        static_cast<unsigned long>(operation),
        static_cast<unsigned long>(descriptor), event)));
}

extern "C" int epoll_wait(
    int epoll_descriptor,
    struct epoll_event *events,
    int maxevents,
    int timeout
) {
    return static_cast<int>(posix_result(mortos_epoll_wait(
        static_cast<unsigned long>(epoll_descriptor), events,
        static_cast<unsigned long>(maxevents),
        static_cast<unsigned long>(timeout))));
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

extern "C" int clock_gettime(
    clockid_t clock,
    struct timespec *time
) {
    if (!time) {
        errno = EFAULT;
        return -1;
    }
    return static_cast<int>(posix_result(mortos_clock_gettime(
        static_cast<unsigned long>(clock), time)));
}

extern "C" int clock_getres(
    clockid_t clock,
    struct timespec *resolution
) {
    if (clock != CLOCK_REALTIME && clock != CLOCK_MONOTONIC) {
        errno = EINVAL;
        return -1;
    }
    if (resolution) {
        resolution->tv_sec = 0;
        resolution->tv_nsec = 10000000L;
    }
    return 0;
}

static int sleep_timespec_valid(const struct timespec *request) {
    return request && request->tv_sec >= 0
        && request->tv_nsec >= 0
        && request->tv_nsec < 1000000000L;
}

static int absolute_timeout_milliseconds(
    clockid_t clock,
    const struct timespec *absolute,
    unsigned long *milliseconds
) {
    if ((clock != CLOCK_REALTIME && clock != CLOCK_MONOTONIC)
        || !sleep_timespec_valid(absolute) || !milliseconds) {
        return EINVAL;
    }
    struct timespec now = {};
    if (clock_gettime(clock, &now) != 0) {
        return errno;
    }
    if (absolute->tv_sec < now.tv_sec
        || (absolute->tv_sec == now.tv_sec
            && absolute->tv_nsec <= now.tv_nsec)) {
        *milliseconds = 0;
        return 0;
    }
    unsigned long seconds = static_cast<unsigned long>(
        absolute->tv_sec - now.tv_sec);
    long nanoseconds = absolute->tv_nsec - now.tv_nsec;
    if (nanoseconds < 0) {
        --seconds;
        nanoseconds += 1000000000L;
    }
    if (seconds > (0x7FFFFFFFFFFFFFFFUL / 1000UL)) {
        return EINVAL;
    }
    *milliseconds = (seconds * 1000UL)
        + ((static_cast<unsigned long>(nanoseconds) + 999999UL)
            / 1000000UL);
    return 0;
}

extern "C" int nanosleep(
    const struct timespec *request,
    struct timespec *remaining
) {
    if (!sleep_timespec_valid(request)
        || static_cast<unsigned long>(request->tv_sec)
            > (0x7FFFFFFFFFFFFFFFUL / 1000UL)) {
        errno = EINVAL;
        return -1;
    }
    unsigned long milliseconds =
        static_cast<unsigned long>(request->tv_sec) * 1000UL;
    milliseconds += (
        static_cast<unsigned long>(request->tv_nsec) + 999999UL)
        / 1000000UL;
    if (milliseconds != 0) {
        unsigned long result = mortos_poll(nullptr, 0, milliseconds);
        if (result >= ERROR_LIMIT) {
            errno = static_cast<int>((~result) + 1);
            return -1;
        }
    }
    if (remaining) {
        remaining->tv_sec = 0;
        remaining->tv_nsec = 0;
    }
    return 0;
}

extern "C" int clock_nanosleep(
    clockid_t clock,
    int flags,
    const struct timespec *request,
    struct timespec *remaining
) {
    if (clock != CLOCK_MONOTONIC
        || (flags != 0 && flags != TIMER_ABSTIME)
        || !sleep_timespec_valid(request)) {
        return EINVAL;
    }
    if (flags == 0) {
        return nanosleep(request, remaining) == 0 ? 0 : errno;
    }
    struct timespec now = {};
    if (clock_gettime(clock, &now) != 0) {
        return errno;
    }
    struct timespec relative = {};
    if (request->tv_sec < now.tv_sec
        || (request->tv_sec == now.tv_sec
            && request->tv_nsec <= now.tv_nsec)) {
        return 0;
    }
    relative.tv_sec = request->tv_sec - now.tv_sec;
    relative.tv_nsec = request->tv_nsec - now.tv_nsec;
    if (relative.tv_nsec < 0) {
        --relative.tv_sec;
        relative.tv_nsec += 1000000000L;
    }
    return nanosleep(&relative, remaining) == 0 ? 0 : errno;
}

extern "C" unsigned int sleep(unsigned int seconds) {
    struct timespec request = {static_cast<time_t>(seconds), 0};
    struct timespec remaining = {};
    if (nanosleep(&request, &remaining) == 0) {
        return 0;
    }
    return static_cast<unsigned int>(remaining.tv_sec
        + (remaining.tv_nsec != 0 ? 1 : 0));
}

extern "C" int usleep(unsigned int microseconds) {
    struct timespec request = {
        static_cast<time_t>(microseconds / 1000000U),
        static_cast<long>((microseconds % 1000000U) * 1000U),
    };
    return nanosleep(&request, nullptr);
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
static volatile unsigned long pthread_key_bitmap = 0;
static volatile unsigned long pthread_key_ever_bitmap = 0;
static void (*pthread_key_destructors[PTHREAD_KEYS_MAX])(void *) = {};

static int pthread_futex_error(unsigned long result);

static bool pthread_key_valid(pthread_key_t key) {
    if (key >= PTHREAD_KEYS_MAX) {
        return false;
    }
    unsigned long bitmap = __atomic_load_n(
        &pthread_key_bitmap, __ATOMIC_ACQUIRE);
    return (bitmap & (1UL << key)) != 0;
}

static void pthread_run_key_destructors() {
    for (unsigned int pass = 0;
         pass < PTHREAD_DESTRUCTOR_ITERATIONS;
         ++pass) {
        bool invoked = false;
        for (pthread_key_t key = 0; key < PTHREAD_KEYS_MAX; ++key) {
            if (!pthread_key_valid(key)) {
                continue;
            }
            unsigned long offset = 64UL + (key * sizeof(unsigned long));
            void *value = reinterpret_cast<void *>(mortos_fs_load(offset));
            auto destructor = pthread_key_destructors[key];
            if (value && destructor) {
                mortos_fs_store(offset, 0);
                destructor(value);
                invoked = true;
            }
        }
        if (!invoked) {
            return;
        }
    }
}

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
    unsigned long result = reinterpret_cast<unsigned long>(start(argument));
    pthread_run_key_destructors();
    return result;
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

extern "C" int pthread_once(
    pthread_once_t *once,
    void (*initialize)()
) {
    if (!once || !initialize) {
        return EINVAL;
    }
    for (;;) {
        unsigned int state = __atomic_load_n(
            &once->__state, __ATOMIC_ACQUIRE);
        if (state == 2) {
            return 0;
        }
        if (state == 0) {
            unsigned int expected = 0;
            if (__atomic_compare_exchange_n(
                    &once->__state, &expected, 1U, false,
                    __ATOMIC_ACQUIRE, __ATOMIC_RELAXED)) {
                initialize();
                __atomic_store_n(&once->__state, 2U, __ATOMIC_RELEASE);
                int error = pthread_futex_error(mortos_futex(
                    const_cast<unsigned int *>(&once->__state), 1, 8));
                return error;
            }
            continue;
        }
        if (state != 1) {
            return EINVAL;
        }
        int error = pthread_futex_error(mortos_futex(
            const_cast<unsigned int *>(&once->__state), 0, 1));
        if (error != 0 && error != EAGAIN) {
            return error;
        }
    }
}

extern "C" int pthread_key_create(
    pthread_key_t *key,
    void (*destructor)(void *)
) {
    if (!key) {
        return EINVAL;
    }
    for (pthread_key_t candidate = 0;
         candidate < PTHREAD_KEYS_MAX;
         ++candidate) {
        unsigned long bit = 1UL << candidate;
        unsigned long bitmap = __atomic_load_n(
            &pthread_key_ever_bitmap, __ATOMIC_RELAXED);
        while ((bitmap & bit) == 0) {
            if (__atomic_compare_exchange_n(
                    &pthread_key_ever_bitmap, &bitmap, bitmap | bit, true,
                    __ATOMIC_ACQUIRE, __ATOMIC_RELAXED)) {
                pthread_key_destructors[candidate] = destructor;
                __atomic_fetch_or(
                    &pthread_key_bitmap, bit, __ATOMIC_RELEASE);
                *key = candidate;
                return 0;
            }
        }
    }
    return EAGAIN;
}

extern "C" int pthread_key_delete(pthread_key_t key) {
    if (!pthread_key_valid(key)) {
        return EINVAL;
    }
    pthread_key_destructors[key] = nullptr;
    __atomic_fetch_and(
        &pthread_key_bitmap, ~(1UL << key), __ATOMIC_RELEASE);
    return 0;
}

extern "C" void *pthread_getspecific(pthread_key_t key) {
    if (!pthread_key_valid(key)) {
        return nullptr;
    }
    return reinterpret_cast<void *>(
        mortos_fs_load(64UL + (key * sizeof(unsigned long))));
}

extern "C" int pthread_setspecific(
    pthread_key_t key,
    const void *value
) {
    if (!pthread_key_valid(key)) {
        return EINVAL;
    }
    mortos_fs_store(
        64UL + (key * sizeof(unsigned long)),
        reinterpret_cast<unsigned long>(value));
    return 0;
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

extern "C" int pthread_cond_clockwait(
    pthread_cond_t *condition,
    pthread_mutex_t *mutex,
    int clock,
    const struct timespec *absolute_timeout
) {
    if (!condition || !mutex) {
        return EINVAL;
    }
    unsigned long timeout = 0;
    int timeout_error = absolute_timeout_milliseconds(
        static_cast<clockid_t>(clock), absolute_timeout, &timeout);
    if (timeout_error != 0) {
        return timeout_error;
    }
    if (timeout == 0) {
        return ETIMEDOUT;
    }
    unsigned int sequence = __atomic_load_n(
        &condition->__sequence, __ATOMIC_ACQUIRE);
    int unlock_error = pthread_mutex_unlock(mutex);
    if (unlock_error != 0) {
        return unlock_error;
    }
    int wait_error = pthread_futex_error(mortos_futex_timed(
        const_cast<unsigned int *>(&condition->__sequence),
        0, sequence, timeout));
    int lock_error = pthread_mutex_lock(mutex);
    if (lock_error != 0) {
        return lock_error;
    }
    return wait_error == EAGAIN ? 0 : wait_error;
}

extern "C" int pthread_cond_timedwait(
    pthread_cond_t *condition,
    pthread_mutex_t *mutex,
    const struct timespec *absolute_timeout
) {
    return pthread_cond_clockwait(
        condition, mutex, CLOCK_REALTIME, absolute_timeout);
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

static constexpr unsigned int PTHREAD_RWLOCK_WRITER = ~0U;

extern "C" int pthread_rwlock_init(
    pthread_rwlock_t *lock,
    const void *attributes
) {
    if (!lock || attributes) {
        return EINVAL;
    }
    __atomic_store_n(&lock->__state, 0U, __ATOMIC_RELAXED);
    return 0;
}

extern "C" int pthread_rwlock_destroy(pthread_rwlock_t *lock) {
    if (!lock) {
        return EINVAL;
    }
    return __atomic_load_n(&lock->__state, __ATOMIC_ACQUIRE) == 0
        ? 0 : EBUSY;
}

extern "C" int pthread_rwlock_tryrdlock(pthread_rwlock_t *lock) {
    if (!lock) {
        return EINVAL;
    }
    unsigned int state = __atomic_load_n(
        &lock->__state, __ATOMIC_RELAXED);
    while (state != PTHREAD_RWLOCK_WRITER
           && state != PTHREAD_RWLOCK_WRITER - 1U) {
        if (__atomic_compare_exchange_n(
                &lock->__state, &state, state + 1U, true,
                __ATOMIC_ACQUIRE, __ATOMIC_RELAXED)) {
            return 0;
        }
    }
    return EBUSY;
}

extern "C" int pthread_rwlock_rdlock(pthread_rwlock_t *lock) {
    if (!lock) {
        return EINVAL;
    }
    for (;;) {
        int result = pthread_rwlock_tryrdlock(lock);
        if (result == 0) {
            return 0;
        }
        unsigned int state = __atomic_load_n(
            &lock->__state, __ATOMIC_ACQUIRE);
        int error = pthread_futex_error(mortos_futex(
            const_cast<unsigned int *>(&lock->__state), 0, state));
        if (error != 0 && error != EAGAIN) {
            return error;
        }
    }
}

extern "C" int pthread_rwlock_trywrlock(pthread_rwlock_t *lock) {
    if (!lock) {
        return EINVAL;
    }
    unsigned int expected = 0;
    return __atomic_compare_exchange_n(
        &lock->__state, &expected, PTHREAD_RWLOCK_WRITER, false,
        __ATOMIC_ACQUIRE, __ATOMIC_RELAXED) ? 0 : EBUSY;
}

extern "C" int pthread_rwlock_wrlock(pthread_rwlock_t *lock) {
    if (!lock) {
        return EINVAL;
    }
    for (;;) {
        int result = pthread_rwlock_trywrlock(lock);
        if (result == 0) {
            return 0;
        }
        unsigned int state = __atomic_load_n(
            &lock->__state, __ATOMIC_ACQUIRE);
        int error = pthread_futex_error(mortos_futex(
            const_cast<unsigned int *>(&lock->__state), 0, state));
        if (error != 0 && error != EAGAIN) {
            return error;
        }
    }
}

extern "C" int pthread_rwlock_unlock(pthread_rwlock_t *lock) {
    if (!lock) {
        return EINVAL;
    }
    for (;;) {
        unsigned int state = __atomic_load_n(
            &lock->__state, __ATOMIC_RELAXED);
        if (state == 0) {
            return EPERM;
        }
        unsigned int next = state == PTHREAD_RWLOCK_WRITER
            ? 0U : state - 1U;
        if (__atomic_compare_exchange_n(
                &lock->__state, &state, next, true,
                __ATOMIC_RELEASE, __ATOMIC_RELAXED)) {
            if (next == 0) {
                return pthread_futex_error(mortos_futex(
                    const_cast<unsigned int *>(&lock->__state), 1, 8));
            }
            return 0;
        }
    }
}

extern "C" int sem_init(
    sem_t *semaphore,
    int process_shared,
    unsigned int value
) {
    if (!semaphore || process_shared != 0 || value > SEM_VALUE_MAX) {
        errno = EINVAL;
        return -1;
    }
    __atomic_store_n(&semaphore->__value, value, __ATOMIC_RELAXED);
    return 0;
}

extern "C" int sem_destroy(sem_t *semaphore) {
    if (!semaphore) {
        errno = EINVAL;
        return -1;
    }
    return 0;
}

extern "C" int sem_trywait(sem_t *semaphore) {
    if (!semaphore) {
        errno = EINVAL;
        return -1;
    }
    unsigned int value = __atomic_load_n(
        &semaphore->__value, __ATOMIC_RELAXED);
    while (value != 0) {
        if (__atomic_compare_exchange_n(
                &semaphore->__value, &value, value - 1U, true,
                __ATOMIC_ACQUIRE, __ATOMIC_RELAXED)) {
            return 0;
        }
    }
    errno = EAGAIN;
    return -1;
}

extern "C" int sem_wait(sem_t *semaphore) {
    if (!semaphore) {
        errno = EINVAL;
        return -1;
    }
    for (;;) {
        unsigned int value = __atomic_load_n(
            &semaphore->__value, __ATOMIC_RELAXED);
        while (value != 0) {
            if (__atomic_compare_exchange_n(
                    &semaphore->__value, &value, value - 1U, true,
                    __ATOMIC_ACQUIRE, __ATOMIC_RELAXED)) {
                return 0;
            }
        }
        int error = pthread_futex_error(mortos_futex(
            const_cast<unsigned int *>(&semaphore->__value), 0, 0));
        if (error != 0 && error != EAGAIN) {
            errno = error;
            return -1;
        }
    }
}

extern "C" int sem_clockwait(
    sem_t *semaphore,
    int clock,
    const struct timespec *absolute_timeout
) {
    if (!semaphore) {
        errno = EINVAL;
        return -1;
    }
    for (;;) {
        unsigned int value = __atomic_load_n(
            &semaphore->__value, __ATOMIC_RELAXED);
        while (value != 0) {
            if (__atomic_compare_exchange_n(
                    &semaphore->__value, &value, value - 1U, true,
                    __ATOMIC_ACQUIRE, __ATOMIC_RELAXED)) {
                return 0;
            }
        }
        unsigned long timeout = 0;
        int timeout_error = absolute_timeout_milliseconds(
            static_cast<clockid_t>(clock), absolute_timeout, &timeout);
        if (timeout_error != 0 || timeout == 0) {
            errno = timeout_error != 0 ? timeout_error : ETIMEDOUT;
            return -1;
        }
        int wait_error = pthread_futex_error(mortos_futex_timed(
            const_cast<unsigned int *>(&semaphore->__value),
            0, 0, timeout));
        if (wait_error == ETIMEDOUT) {
            errno = ETIMEDOUT;
            return -1;
        }
        if (wait_error != 0 && wait_error != EAGAIN) {
            errno = wait_error;
            return -1;
        }
    }
}

extern "C" int sem_timedwait(
    sem_t *semaphore,
    const struct timespec *absolute_timeout
) {
    return sem_clockwait(
        semaphore, CLOCK_REALTIME, absolute_timeout);
}

extern "C" int sem_post(sem_t *semaphore) {
    if (!semaphore) {
        errno = EINVAL;
        return -1;
    }
    unsigned int value = __atomic_load_n(
        &semaphore->__value, __ATOMIC_RELAXED);
    for (;;) {
        if (value >= SEM_VALUE_MAX) {
            errno = EOVERFLOW;
            return -1;
        }
        if (__atomic_compare_exchange_n(
                &semaphore->__value, &value, value + 1U, true,
                __ATOMIC_RELEASE, __ATOMIC_RELAXED)) {
            int error = pthread_futex_error(mortos_futex(
                const_cast<unsigned int *>(&semaphore->__value), 1, 1));
            if (error != 0) {
                errno = error;
                return -1;
            }
            return 0;
        }
    }
}

extern "C" int sem_getvalue(sem_t *semaphore, int *value) {
    if (!semaphore || !value) {
        errno = EINVAL;
        return -1;
    }
    *value = static_cast<int>(__atomic_load_n(
        &semaphore->__value, __ATOMIC_ACQUIRE));
    return 0;
}
