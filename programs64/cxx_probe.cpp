// A separately linked freestanding C++ process. This validates constructor
// startup, C allocation, C++ new/delete, and syscall linkage at ring 3.

#include <mortos/syscall.h>
#include <netdb.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <pthread.h>
#include <semaphore.h>
#include <stdlib.h>
#include <sys/epoll.h>
#include <sys/eventfd.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

using size_type = unsigned long;

static unsigned long constructor_value;

struct StartupProbe {
    StartupProbe() {
        constructor_value = 0x435858434F4E5354UL;
    }
};

static StartupProbe startup_probe;

struct Widget {
    explicit Widget(unsigned long initial) : value(initial) {}
    unsigned long value;
};

static const char pipe_message[] = "descriptor-ipc";
static pthread_once_t runtime_once = PTHREAD_ONCE_INIT;
static unsigned int runtime_once_count;
static unsigned long key_destructor_seen;

static void initialize_runtime_once() {
    __atomic_add_fetch(&runtime_once_count, 1U, __ATOMIC_RELEASE);
}

static void record_key_destructor(void *value) {
    __atomic_store_n(
        &key_destructor_seen,
        reinterpret_cast<unsigned long>(value),
        __ATOMIC_RELEASE);
}

static struct timespec realtime_deadline(unsigned long milliseconds) {
    struct timespec deadline = {};
    if (clock_gettime(CLOCK_REALTIME, &deadline) != 0) {
        return deadline;
    }
    deadline.tv_sec += static_cast<time_t>(milliseconds / 1000UL);
    deadline.tv_nsec += static_cast<long>(
        (milliseconds % 1000UL) * 1000000UL);
    if (deadline.tv_nsec >= 1000000000L) {
        ++deadline.tv_sec;
        deadline.tv_nsec -= 1000000000L;
    }
    return deadline;
}

struct PipeWorkerArguments {
    unsigned int write_descriptor;
};

struct EventWorkerArguments {
    unsigned int descriptor;
    unsigned long value;
};

struct ThreadSyncArguments {
    pthread_mutex_t *mutex;
    pthread_cond_t *condition;
    unsigned int *ready;
    pthread_key_t key;
};

struct RwlockWorkerArguments {
    pthread_rwlock_t *lock;
    unsigned long *value;
};

struct SemaphoreWorkerArguments {
    sem_t *semaphore;
    unsigned long *value;
};

extern "C" void *thread_worker(void *opaque) {
    if (mortos_getpid() != 5 || mortos_gettid() == 5) {
        return reinterpret_cast<void *>(30UL);
    }
    errno = EAGAIN;
    if (errno != EAGAIN || pthread_self() == 5) {
        return reinterpret_cast<void *>(30UL);
    }
    if (mortos_yield() != 0) {
        return reinterpret_cast<void *>(30UL);
    }
    auto *arguments = static_cast<ThreadSyncArguments *>(opaque);
    void *key_value = reinterpret_cast<void *>(0x99UL);
    if (pthread_once(&runtime_once, initialize_runtime_once) != 0
        || pthread_setspecific(arguments->key, key_value) != 0
        || pthread_getspecific(arguments->key) != key_value) {
        return reinterpret_cast<void *>(30UL);
    }
    if (pthread_mutex_lock(arguments->mutex) != 0) {
        return reinterpret_cast<void *>(30UL);
    }
    __atomic_store_n(arguments->ready, 1U, __ATOMIC_RELEASE);
    if (pthread_cond_signal(arguments->condition) != 0
        || pthread_mutex_unlock(arguments->mutex) != 0) {
        return reinterpret_cast<void *>(30UL);
    }
    return reinterpret_cast<void *>(31UL);
}

extern "C" void *pipe_worker(void *opaque) {
    if (mortos_yield() != 0) {
        return reinterpret_cast<void *>(40UL);
    }
    auto *arguments = static_cast<PipeWorkerArguments *>(opaque);
    if (mortos_fd_write(
            arguments->write_descriptor,
            pipe_message,
            sizeof(pipe_message) - 1) != sizeof(pipe_message) - 1) {
        return reinterpret_cast<void *>(40UL);
    }
    return reinterpret_cast<void *>(32UL);
}

extern "C" void *event_worker(void *opaque) {
    if (mortos_yield() != 0) {
        return reinterpret_cast<void *>(41UL);
    }
    auto *arguments = static_cast<EventWorkerArguments *>(opaque);
    if (mortos_fd_write(
            arguments->descriptor,
            &arguments->value,
            sizeof(arguments->value)) != sizeof(arguments->value)) {
        return reinterpret_cast<void *>(41UL);
    }
    return reinterpret_cast<void *>(33UL);
}

extern "C" void *join_worker(void *) {
    if (errno != 0 || pthread_self() == 5) {
        return reinterpret_cast<void *>(42UL);
    }
    return reinterpret_cast<void *>(34UL);
}

extern "C" void *rwlock_worker(void *opaque) {
    auto *arguments = static_cast<RwlockWorkerArguments *>(opaque);
    if (pthread_rwlock_wrlock(arguments->lock) != 0) {
        return reinterpret_cast<void *>(43UL);
    }
    *arguments->value = 0x52574C4F434B5645UL;
    if (pthread_rwlock_unlock(arguments->lock) != 0) {
        return reinterpret_cast<void *>(43UL);
    }
    return reinterpret_cast<void *>(35UL);
}

extern "C" void *semaphore_worker(void *opaque) {
    auto *arguments = static_cast<SemaphoreWorkerArguments *>(opaque);
    if (sem_wait(arguments->semaphore) != 0) {
        return reinterpret_cast<void *>(44UL);
    }
    *arguments->value = 0x53454D4150484F52UL;
    return reinterpret_cast<void *>(36UL);
}

static bool contains_text(
    const char *haystack,
    unsigned long haystack_size,
    const char *needle,
    unsigned long needle_size
) {
    if (needle_size == 0 || needle_size > haystack_size) {
        return false;
    }
    for (unsigned long start = 0;
         start <= haystack_size - needle_size;
         ++start) {
        bool matches = true;
        for (unsigned long index = 0; index < needle_size; ++index) {
            if (haystack[start + index] != needle[index]) {
                matches = false;
                break;
            }
        }
        if (matches) {
            return true;
        }
    }
    return false;
}

static bool text_equals(const char *left, const char *right) {
    for (unsigned long index = 0; index < 128; ++index) {
        if (left[index] != right[index]) {
            return false;
        }
        if (left[index] == 0) {
            return true;
        }
    }
    return false;
}

extern "C" int main(int argc, char **argv, char **envp) {
    if (mortos_getpid() != 5
        || constructor_value != 0x435858434F4E5354UL
        || argc != 1 || !argv || !argv[0] || argv[1]
        || !text_equals(argv[0], "/system/bin/mort-cxx")) {
        return 1;
    }
    bool environment_found = false;
    char **environment = envp;
    unsigned long environment_count = 0;
    while (environment && *environment && environment_count < 16) {
        if (text_equals(*environment, "MORTOS=1")) {
            environment_found = true;
        }
        ++environment;
        ++environment_count;
    }
    if (!environment || *environment || !environment_found) {
        return 1;
    }
    auto *auxiliary = reinterpret_cast<unsigned long *>(environment + 1);
    bool pagesize_found = false;
    bool random_found = false;
    bool exec_found = false;
    bool auxiliary_end = false;
    for (unsigned long index = 0; index < 32; ++index) {
        unsigned long type = auxiliary[index * 2];
        unsigned long value = auxiliary[index * 2 + 1];
        if (type == 0) {
            auxiliary_end = true;
            break;
        }
        if (type == 6 && value == 4096) {
            pagesize_found = true;
        } else if (type == 25 && value != 0) {
            auto *random = reinterpret_cast<unsigned char *>(value);
            unsigned char any = 0;
            for (unsigned long byte = 0; byte < 16; ++byte) {
                any = static_cast<unsigned char>(any | random[byte]);
            }
            random_found = any != 0;
        } else if (type == 31 && value != 0) {
            exec_found = text_equals(
                reinterpret_cast<const char *>(value), argv[0]);
        }
    }
    if (!pagesize_found || !random_found || !exec_found || !auxiliary_end) {
        return 1;
    }
    char invalid_read = 0;
    errno = 0;
    if (read(99, &invalid_read, 1) != -1
        || errno != EBADF || getpid() != 5) {
        return 19;
    }

    auto *bytes = static_cast<unsigned char *>(malloc(32));
    if (!bytes) {
        return 2;
    }
    for (unsigned long index = 0; index < 32; ++index) {
        bytes[index] = static_cast<unsigned char>(index ^ 0xA5);
    }
    bytes = static_cast<unsigned char *>(realloc(bytes, 96));
    if (!bytes) {
        return 3;
    }
    for (unsigned long index = 0; index < 32; ++index) {
        if (bytes[index] != static_cast<unsigned char>(index ^ 0xA5)) {
            return 4;
        }
    }
    free(bytes);

    auto *zeros = static_cast<unsigned long *>(calloc(4, sizeof(unsigned long)));
    if (!zeros || zeros[0] != 0 || zeros[3] != 0) {
        return 5;
    }
    free(zeros);

    Widget *widget = new Widget(0x564558435858UL);
    if (!widget || widget->value != 0x564558435858UL) {
        return 6;
    }
    delete widget;

    unsigned char random_first[32] = {};
    unsigned char random_second[32] = {};
    if (mortos_getrandom(random_first, sizeof(random_first), 0)
            != sizeof(random_first)
        || mortos_getrandom(random_second, sizeof(random_second), 1)
            != sizeof(random_second)) {
        return 17;
    }
    unsigned char random_any = 0;
    bool random_differs = false;
    for (unsigned long index = 0; index < sizeof(random_first); ++index) {
        random_any = static_cast<unsigned char>(
            random_any | random_first[index] | random_second[index]);
        if (random_first[index] != random_second[index]) {
            random_differs = true;
        }
    }
    if (random_any == 0 || !random_differs) {
        return 17;
    }

    unsigned long high_mapping = reinterpret_cast<unsigned long>(
        mortos_mmap(
            0x70000000UL, 8192, 3, 0x32, ~0UL, 0));
    if (high_mapping != 0x70000000UL) {
        return 15;
    }
    *reinterpret_cast<unsigned long *>(high_mapping) =
        0x4D4D415057494445UL;
    *reinterpret_cast<unsigned char *>(high_mapping + 8191) = 0xA7;
    if (mortos_munmap(high_mapping, 8192) != 0) {
        return 15;
    }

    unsigned long runtime_tls = 0;
    if (mortos_arch_prctl(
            0x1003, reinterpret_cast<unsigned long>(&runtime_tls)) != 0
        || runtime_tls == 0) {
        return 10;
    }
    unsigned long tls = mortos_mmap(0, 4096, 3, 0x22, ~0UL, 0);
    if (tls >= ~4095UL) {
        return 8;
    }
    *reinterpret_cast<unsigned long *>(tls) = tls;
    *reinterpret_cast<unsigned long *>(tls + 40) =
        *reinterpret_cast<unsigned long *>(runtime_tls + 40);
    if (mortos_arch_prctl(0x1002, tls) != 0) {
        return 8;
    }
    mortos_fs_store(8, 0x544C5356414C5545UL);
    unsigned long atomic_value = 10;
    if (__atomic_fetch_add(&atomic_value, 7, __ATOMIC_SEQ_CST) != 10
        || atomic_value != 17) {
        return 9;
    }
    unsigned int thread_ready = 0;
    pthread_key_t worker_key = 0;
    void *main_key_value = reinterpret_cast<void *>(0x55UL);
    if (pthread_key_create(&worker_key, record_key_destructor) != 0
        || pthread_setspecific(worker_key, main_key_value) != 0
        || pthread_getspecific(worker_key) != main_key_value
        || pthread_once(&runtime_once, initialize_runtime_once) != 0) {
        return 9;
    }
    pthread_mutex_t thread_mutex = PTHREAD_MUTEX_INITIALIZER;
    pthread_cond_t thread_condition = PTHREAD_COND_INITIALIZER;
    ThreadSyncArguments thread_arguments = {
        &thread_mutex, &thread_condition, &thread_ready, worker_key};
    pthread_t thread_id = 0;
    if (pthread_mutex_lock(&thread_mutex) != 0
        || pthread_mutex_trylock(&thread_mutex) != EBUSY
        || pthread_create(
            &thread_id, nullptr, thread_worker, &thread_arguments) != 0
        || thread_id <= 5) {
        return 9;
    }
    while (__atomic_load_n(&thread_ready, __ATOMIC_ACQUIRE) == 0) {
        if (pthread_cond_wait(&thread_condition, &thread_mutex) != 0) {
            return 9;
        }
    }
    if (pthread_mutex_unlock(&thread_mutex) != 0
        || pthread_mutex_destroy(&thread_mutex) != 0
        || pthread_cond_broadcast(&thread_condition) != 0
        || pthread_cond_destroy(&thread_condition) != 0) {
        return 9;
    }
    void *thread_result = nullptr;
    if (pthread_join(thread_id, &thread_result) != 0
        || thread_result != reinterpret_cast<void *>(31UL)
        || __atomic_load_n(&runtime_once_count, __ATOMIC_ACQUIRE) != 1
        || __atomic_load_n(&key_destructor_seen, __ATOMIC_ACQUIRE) != 0x99
        || pthread_getspecific(worker_key) != main_key_value
        || pthread_key_delete(worker_key) != 0
        || pthread_setspecific(worker_key, nullptr) != EINVAL) {
        return 9;
    }
    pthread_t joined_thread = 0;
    if (pthread_create(
            &joined_thread, nullptr, join_worker, nullptr) != 0
        || pthread_join(joined_thread, &thread_result) != 0
        || thread_result != reinterpret_cast<void *>(34UL)
        || pthread_join(joined_thread, nullptr) != ESRCH) {
        return 9;
    }
    pthread_rwlock_t rwlock = PTHREAD_RWLOCK_INITIALIZER;
    unsigned long rwlock_value = 0;
    RwlockWorkerArguments rwlock_arguments = {&rwlock, &rwlock_value};
    pthread_t rwlock_thread = 0;
    if (pthread_rwlock_rdlock(&rwlock) != 0
        || pthread_rwlock_trywrlock(&rwlock) != EBUSY
        || pthread_create(
            &rwlock_thread, nullptr, rwlock_worker,
            &rwlock_arguments) != 0
        || mortos_yield() != 0
        || rwlock_value != 0
        || pthread_rwlock_unlock(&rwlock) != 0
        || pthread_join(rwlock_thread, &thread_result) != 0
        || thread_result != reinterpret_cast<void *>(35UL)
        || rwlock_value != 0x52574C4F434B5645UL
        || pthread_rwlock_tryrdlock(&rwlock) != 0
        || pthread_rwlock_unlock(&rwlock) != 0
        || pthread_rwlock_destroy(&rwlock) != 0) {
        return 9;
    }
    sem_t semaphore = {};
    unsigned long semaphore_value = 0;
    int semaphore_count = -1;
    SemaphoreWorkerArguments semaphore_arguments = {
        &semaphore, &semaphore_value};
    pthread_t semaphore_thread = 0;
    if (sem_init(&semaphore, 0, 1) != 0
        || sem_trywait(&semaphore) != 0
        || pthread_create(
            &semaphore_thread, nullptr, semaphore_worker,
            &semaphore_arguments) != 0
        || mortos_yield() != 0
        || semaphore_value != 0
        || sem_getvalue(&semaphore, &semaphore_count) != 0
        || semaphore_count != 0
        || sem_post(&semaphore) != 0
        || pthread_join(semaphore_thread, &thread_result) != 0
        || thread_result != reinterpret_cast<void *>(36UL)
        || semaphore_value != 0x53454D4150484F52UL
        || sem_destroy(&semaphore) != 0) {
        return 9;
    }
    if (mortos_fs_load(8) != 0x544C5356414C5545UL
        || mortos_arch_prctl(0x1003, tls + 16) != 0
        || *reinterpret_cast<unsigned long *>(tls + 16) != tls) {
        return 9;
    }
    if (mortos_arch_prctl(0x1002, runtime_tls) != 0
        || mortos_munmap(tls, 4096) != 0
        || errno != EBADF) {
        return 10;
    }
    struct timespec clock_resolution = {};
    struct timespec sleep_before = {};
    struct timespec sleep_after = {};
    struct timespec sleep_duration = {0, 20000000L};
    if (clock_getres(CLOCK_MONOTONIC, &clock_resolution) != 0
        || clock_resolution.tv_sec != 0
        || clock_resolution.tv_nsec != 10000000L
        || clock_gettime(CLOCK_MONOTONIC, &sleep_before) != 0
        || nanosleep(&sleep_duration, nullptr) != 0
        || clock_gettime(CLOCK_MONOTONIC, &sleep_after) != 0) {
        return 20;
    }
    unsigned long sleep_before_ns =
        static_cast<unsigned long>(sleep_before.tv_sec) * 1000000000UL
        + static_cast<unsigned long>(sleep_before.tv_nsec);
    unsigned long sleep_after_ns =
        static_cast<unsigned long>(sleep_after.tv_sec) * 1000000000UL
        + static_cast<unsigned long>(sleep_after.tv_nsec);
    if (sleep_after_ns < sleep_before_ns + 10000000UL) {
        return 20;
    }
    pthread_mutex_t timed_mutex = PTHREAD_MUTEX_INITIALIZER;
    pthread_cond_t timed_condition = PTHREAD_COND_INITIALIZER;
    struct timespec condition_deadline = realtime_deadline(20);
    if (condition_deadline.tv_sec == 0
        || pthread_mutex_lock(&timed_mutex) != 0
        || pthread_cond_timedwait(
            &timed_condition, &timed_mutex,
            &condition_deadline) != ETIMEDOUT
        || pthread_mutex_unlock(&timed_mutex) != 0
        || pthread_mutex_destroy(&timed_mutex) != 0
        || pthread_cond_destroy(&timed_condition) != 0) {
        return 20;
    }
    sem_t timed_semaphore = {};
    struct timespec semaphore_deadline = realtime_deadline(20);
    errno = 0;
    if (sem_init(&timed_semaphore, 0, 0) != 0
        || semaphore_deadline.tv_sec == 0
        || sem_timedwait(
            &timed_semaphore, &semaphore_deadline) != -1
        || errno != ETIMEDOUT
        || sem_destroy(&timed_semaphore) != 0) {
        return 20;
    }
    struct timespec realtime = {};
    if (clock_gettime(CLOCK_REALTIME, &realtime) != 0
        || realtime.tv_sec < 1577836800L
        || realtime.tv_nsec < 0
        || realtime.tv_nsec >= 1000000000L) {
        return 20;
    }
    unsigned int timed_futex = 0;
    if (clock_gettime(CLOCK_MONOTONIC, &sleep_before) != 0
        || mortos_futex_timed(&timed_futex, 0, 0, 20) != ~109UL
        || clock_gettime(CLOCK_MONOTONIC, &sleep_after) != 0) {
        return 20;
    }
    sleep_before_ns =
        static_cast<unsigned long>(sleep_before.tv_sec) * 1000000000UL
        + static_cast<unsigned long>(sleep_before.tv_nsec);
    sleep_after_ns =
        static_cast<unsigned long>(sleep_after.tv_sec) * 1000000000UL
        + static_cast<unsigned long>(sleep_after.tv_nsec);
    if (sleep_after_ns < sleep_before_ns + 10000000UL) {
        return 20;
    }

    unsigned int pipe_descriptors[2] = {};
    char pipe_result[sizeof(pipe_message)] = {};
    int flag_pipe[2] = {};
    if (pipe2(flag_pipe, O_NONBLOCK | O_CLOEXEC) != 0
        || fcntl(flag_pipe[0], F_GETFD) != FD_CLOEXEC
        || fcntl(flag_pipe[1], F_GETFD) != FD_CLOEXEC
        || fcntl(flag_pipe[0], F_GETFL) != O_NONBLOCK
        || fcntl(flag_pipe[1], F_GETFL) != (O_WRONLY | O_NONBLOCK)
        || fcntl(flag_pipe[0], F_SETFD, 0) != 0
        || fcntl(flag_pipe[0], F_SETFL, 0) != 0
        || fcntl(flag_pipe[0], F_GETFD) != 0
        || fcntl(flag_pipe[0], F_GETFL) != O_RDONLY
        || close(flag_pipe[0]) != 0 || close(flag_pipe[1]) != 0
        || mortos_pipe2(pipe_descriptors, 0) != 0) {
        return 11;
    }
    PipeWorkerArguments pipe_arguments = {pipe_descriptors[1]};
    pthread_t pipe_thread = 0;
    if (pthread_create(
            &pipe_thread, nullptr, pipe_worker, &pipe_arguments) != 0
        || pipe_thread <= thread_id) {
        return 11;
    }
    struct pollfd readiness[1] = {
        {static_cast<int>(pipe_descriptors[0]), POLLIN, 0},
    };
    if (poll(readiness, 1, 1000) != 1
        || (readiness[0].revents & POLLIN) == 0
        || mortos_read(
            pipe_descriptors[0], pipe_result,
            sizeof(pipe_message) - 1) != sizeof(pipe_message) - 1) {
        return 11;
    }
    for (unsigned long index = 0; index < sizeof(pipe_message) - 1; ++index) {
        if (pipe_result[index] != pipe_message[index]) {
            return 11;
        }
    }
    if (pthread_join(pipe_thread, &thread_result) != 0
        || thread_result != reinterpret_cast<void *>(32UL)) {
        return 11;
    }
    readiness[0].revents = 0;
    if (poll(readiness, 1, 20) != 0
        || readiness[0].revents != 0) {
        return 11;
    }
    if (mortos_close(pipe_descriptors[0]) != 0
        || mortos_close(pipe_descriptors[1]) != 0) {
        return 11;
    }

    int event_descriptor = eventfd(0, EFD_NONBLOCK | EFD_CLOEXEC);
    int epoll_descriptor = epoll_create1(EPOLL_CLOEXEC);
    if (event_descriptor < 0 || epoll_descriptor < 0) {
        return 18;
    }
    struct epoll_event event_interest = {};
    event_interest.events = EPOLLIN;
    event_interest.data.u64 = 0x45504F4C4C564558UL;
    if (epoll_ctl(
            epoll_descriptor, EPOLL_CTL_ADD, event_descriptor,
            &event_interest) != 0) {
        return 18;
    }
    event_interest.data.u64 = 0x45504F4C4C4D4F44UL;
    if (epoll_ctl(
            epoll_descriptor, EPOLL_CTL_MOD, event_descriptor,
            &event_interest) != 0) {
        return 18;
    }
    EventWorkerArguments event_arguments = {
        static_cast<unsigned int>(event_descriptor), 7UL};
    pthread_t event_thread = 0;
    if (pthread_create(
            &event_thread, nullptr, event_worker,
            &event_arguments) != 0) {
        return 18;
    }
    struct epoll_event event_readiness = {};
    eventfd_t event_value = 0;
    if (event_thread <= pipe_thread
        || epoll_wait(
            epoll_descriptor, &event_readiness, 1, 1000) != 1
        || (event_readiness.events & EPOLLIN) == 0
        || event_readiness.data.u64 != 0x45504F4C4C4D4F44UL
        || eventfd_read(event_descriptor, &event_value) != 0
        || event_value != 7
        || pthread_join(event_thread, &thread_result) != 0
        || thread_result != reinterpret_cast<void *>(33UL)
        || eventfd_read(event_descriptor, &event_value) != -1
        || errno != EAGAIN
        || epoll_wait(
            epoll_descriptor, &event_readiness, 1, 20) != 0
        || epoll_ctl(
            epoll_descriptor, EPOLL_CTL_DEL,
            event_descriptor, nullptr) != 0
        || close(epoll_descriptor) != 0
        || close(event_descriptor) != 0) {
        return 18;
    }

    static const char vex_package_path[] = "/app/vex/package.json";
    unsigned long vex_file = mortos_openat(
        ~99UL, vex_package_path, 0, 0);
    alignas(8) unsigned char vex_status[144] = {};
    char vex_header[512] = {};
    if (vex_file >= ~4095UL
        || mortos_fstat(vex_file, vex_status) != 0) {
        return 12;
    }
    unsigned long vex_size =
        *reinterpret_cast<unsigned long *>(vex_status + 48);
    if (vex_size < sizeof(vex_header)
        || mortos_pread(vex_file, vex_header, sizeof(vex_header), 0)
            != sizeof(vex_header)
        || !contains_text(vex_header, sizeof(vex_header),
                          "\"name\": \"vex\"", 13)
        || !contains_text(vex_header, sizeof(vex_header),
                          "\"version\": \"2.28.1\"", 19)
        || !contains_text(vex_header, sizeof(vex_header),
                          "\"main\": \"src/main.js\"", 21)
        || mortos_lseek(vex_file, 0, 2) != vex_size
        || mortos_lseek(vex_file, 0, 0) != 0) {
        return 12;
    }
    unsigned long vex_mapping = reinterpret_cast<unsigned long>(
        mortos_mmap(0, 512, 1, 2, vex_file, 0));
    if (vex_mapping >= ~4095UL
        || *reinterpret_cast<const char *>(vex_mapping) != '{'
        || !contains_text(
            reinterpret_cast<const char *>(vex_mapping), 512,
            "\"version\": \"2.28.1\"", 19)
        || mortos_munmap(vex_mapping, 512) != 0) {
        return 12;
    }
    char first_byte = 0;
    if (mortos_read(vex_file, &first_byte, 1) != 1
        || first_byte != '{'
        || mortos_close(vex_file) != 0) {
        return 12;
    }
    static const char vex_main_path[] = "/app/vex/src/main.js";
    static const char vex_renderer_path[] = "/app/vex/src/renderer";
    alignas(8) unsigned char vex_main_status[144] = {};
    alignas(8) unsigned char vex_renderer_status[144] = {};
    if (mortos_newfstatat(
            ~99UL, vex_main_path, vex_main_status, 0) != 0
        || ((*reinterpret_cast<unsigned int *>(vex_main_status + 24)
             & 0xF000U) != 0x8000U)
        || *reinterpret_cast<unsigned long *>(vex_main_status + 48) == 0
        || mortos_newfstatat(
            ~99UL, vex_renderer_path, vex_renderer_status, 0) != 0
        || ((*reinterpret_cast<unsigned int *>(vex_renderer_status + 24)
             & 0xF000U) != 0x4000U)) {
        return 13;
    }
    unsigned long vex_directory = mortos_openat(
        ~99UL, vex_renderer_path, 0x90000, 0);
    alignas(8) unsigned char vex_directory_status[144] = {};
    alignas(8) char vex_directory_entries[512] = {};
    if (vex_directory >= ~4095UL
        || mortos_fstat(vex_directory, vex_directory_status) != 0
        || ((*reinterpret_cast<unsigned int *>(
                 vex_directory_status + 24) & 0xF000U) != 0x4000U)) {
        return 14;
    }
    unsigned long directory_bytes = mortos_getdents64(
        vex_directory, vex_directory_entries,
        sizeof(vex_directory_entries));
    if (directory_bytes == 0 || directory_bytes > 512
        || !contains_text(
            vex_directory_entries, directory_bytes, "index.html", 10)
        || mortos_getdents64(
            vex_directory, vex_directory_entries,
            sizeof(vex_directory_entries)) != 0
        || mortos_close(vex_directory) != 0) {
        return 14;
    }
    static const char root_path[] = "/";
    unsigned long root_directory = mortos_openat(
        ~99UL, root_path, 0x90000, 0);
    if (root_directory >= ~4095UL) {
        return 14;
    }
    alignas(8) char root_entries[128] = {};
    unsigned long root_bytes = mortos_getdents64(
        root_directory, root_entries, sizeof(root_entries));
    if (root_bytes == 0 || root_bytes > sizeof(root_entries)
        || !contains_text(root_entries, root_bytes, "app", 3)
        || mortos_close(root_directory) != 0) {
        return 14;
    }
    static const char vex_source_path[] = "/app/vex/src";
    static const char relative_main_path[] = "./main.js";
    static const char relative_renderer_path[] = "renderer";
    static const char relative_index_path[] = "index.html";
    char cwd_result[64] = {};
    if (mortos_chdir(vex_source_path) != 0
        || mortos_getcwd(cwd_result, sizeof(cwd_result))
            != reinterpret_cast<unsigned long>(cwd_result)
        || !contains_text(
            cwd_result, sizeof(cwd_result), "/app/vex/src", 12)) {
        return 16;
    }
    unsigned long relative_main = mortos_openat(
        ~99UL, relative_main_path, 0, 0);
    unsigned long relative_renderer = mortos_openat(
        ~99UL, relative_renderer_path, 0x90000, 0);
    alignas(8) unsigned char relative_status[144] = {};
    if (relative_main >= ~4095UL || relative_renderer >= ~4095UL
        || mortos_fstat(relative_main, relative_status) != 0
        || ((*reinterpret_cast<unsigned int *>(relative_status + 24)
             & 0xF000U) != 0x8000U)
        || mortos_newfstatat(
            relative_renderer, relative_index_path,
            relative_status, 0) != 0
        || ((*reinterpret_cast<unsigned int *>(relative_status + 24)
             & 0xF000U) != 0x8000U)
        || mortos_close(relative_main) != 0
        || mortos_close(relative_renderer) != 0
        || mortos_chdir(root_path) != 0) {
        return 16;
    }

    int stream_socket = socket(
        AF_INET, SOCK_STREAM | SOCK_NONBLOCK | SOCK_CLOEXEC, 0);
    int socket_type = 0;
    int socket_error = -1;
    socklen_t socket_option_length = sizeof(socket_type);
    struct pollfd socket_readiness = {stream_socket, POLLOUT, 0};
    char socket_byte = 0;
    if (stream_socket < 0
        || fcntl(stream_socket, F_GETFD) != FD_CLOEXEC
        || fcntl(stream_socket, F_GETFL) != (O_RDWR | O_NONBLOCK)
        || getsockopt(
            stream_socket, SOL_SOCKET, SO_TYPE,
            &socket_type, &socket_option_length) != 0
        || socket_type != SOCK_STREAM
        || socket_option_length != sizeof(socket_type)
        || getsockopt(
            stream_socket, SOL_SOCKET, SO_ERROR,
            &socket_error, &socket_option_length) != 0
        || socket_error != 0
        || poll(&socket_readiness, 1, 0) != 0
        || socket_readiness.revents != 0
        || read(stream_socket, &socket_byte, 1) != -1
        || errno != ENOTCONN
        || close(stream_socket) != 0) {
        return 19;
    }

    static struct addrinfo resolver_hints = {};
    resolver_hints.ai_family = AF_INET;
    resolver_hints.ai_socktype = SOCK_STREAM;
    resolver_hints.ai_protocol = IPPROTO_TCP;
    struct addrinfo *resolved = nullptr;
    if (getaddrinfo(
            "example.com", "80", &resolver_hints, &resolved) != 0
        || !resolved || resolved->ai_family != AF_INET
        || resolved->ai_socktype != SOCK_STREAM
        || resolved->ai_protocol != IPPROTO_TCP
        || resolved->ai_addrlen != sizeof(struct sockaddr_in)
        || ntohs(reinterpret_cast<struct sockaddr_in *>(
                     resolved->ai_addr)->sin_port) != 80
        || reinterpret_cast<struct sockaddr_in *>(
               resolved->ai_addr)->sin_addr.s_addr == 0) {
        if (resolved) {
            freeaddrinfo(resolved);
        }
        return 19;
    }
    int connected_socket = socket(
        resolved->ai_family,
        resolved->ai_socktype | SOCK_CLOEXEC,
        resolved->ai_protocol);
    struct pollfd connected_readiness = {
        connected_socket, POLLOUT, 0};
    int enabled_socket_option = 1;
    static struct sockaddr_in local_socket_address = {};
    static struct sockaddr_in peer_socket_address = {};
    socklen_t local_socket_length = sizeof(local_socket_address);
    socklen_t peer_socket_length = sizeof(peer_socket_address);
    socket_error = -1;
    socket_option_length = sizeof(socket_error);
    if (connected_socket < 0
        || connect(
            connected_socket,
            resolved->ai_addr, resolved->ai_addrlen) != 0
        || setsockopt(
            connected_socket, SOL_SOCKET, SO_KEEPALIVE,
            &enabled_socket_option, sizeof(enabled_socket_option)) != 0
        || setsockopt(
            connected_socket, IPPROTO_TCP, TCP_NODELAY,
            &enabled_socket_option, sizeof(enabled_socket_option)) != 0
        || getsockname(
            connected_socket,
            reinterpret_cast<struct sockaddr *>(&local_socket_address),
            &local_socket_length) != 0
        || getpeername(
            connected_socket,
            reinterpret_cast<struct sockaddr *>(&peer_socket_address),
            &peer_socket_length) != 0
        || local_socket_length != sizeof(local_socket_address)
        || peer_socket_length != sizeof(peer_socket_address)
        || local_socket_address.sin_family != AF_INET
        || local_socket_address.sin_addr.s_addr == 0
        || local_socket_address.sin_port == 0
        || peer_socket_address.sin_family != AF_INET
        || peer_socket_address.sin_port
            != reinterpret_cast<struct sockaddr_in *>(
                resolved->ai_addr)->sin_port
        || peer_socket_address.sin_addr.s_addr
            != reinterpret_cast<struct sockaddr_in *>(
                resolved->ai_addr)->sin_addr.s_addr
        || poll(&connected_readiness, 1, 0) != 1
        || (connected_readiness.revents & POLLOUT) == 0
        || getsockopt(
            connected_socket, SOL_SOCKET, SO_ERROR,
            &socket_error, &socket_option_length) != 0
        || socket_error != 0) {
        freeaddrinfo(resolved);
        return 19;
    }
    freeaddrinfo(resolved);
    resolved = nullptr;
    static const char http_request[] =
        "GET / HTTP/1.0\r\n"
        "Host: example.com\r\n"
        "Connection: close\r\n\r\n";
    static char http_response[1024] = {};
    ssize_t http_bytes = 0;
    if (send(
            connected_socket, http_request,
            sizeof(http_request) - 1,
            MSG_NOSIGNAL) != sizeof(http_request) - 1) {
        return 19;
    }
    int network_epoll = epoll_create1(EPOLL_CLOEXEC);
    static struct epoll_event network_interest = {};
    static struct epoll_event network_readiness = {};
    network_interest.events = EPOLLIN;
    network_interest.data.u64 = 0x5443504854545055UL;
    if (network_epoll < 0
        || epoll_ctl(
            network_epoll, EPOLL_CTL_ADD, connected_socket,
            &network_interest) != 0
        || epoll_wait(
            network_epoll, &network_readiness, 1, 1000) != 1
        || (network_readiness.events & EPOLLIN) == 0
        || network_readiness.data.u64 != 0x5443504854545055UL
        || close(network_epoll) != 0
        || (http_bytes = recv(
                connected_socket, http_response,
                sizeof(http_response), 0)) <= 0
        || !contains_text(
            http_response, static_cast<unsigned long>(http_bytes),
            "HTTP/", 5)
        || shutdown(connected_socket, SHUT_WR) != 0
        || send(
            connected_socket, http_request, 1,
            MSG_NOSIGNAL) != -1
        || errno != EPIPE
        || close(connected_socket) != 0) {
        return 19;
    }
    static const char message[] = "MORT64 CXX RUNTIME OK\r\n";
    if (mortos_write(message, sizeof(message) - 1) != sizeof(message) - 1) {
        return 7;
    }
    return 23;
}
