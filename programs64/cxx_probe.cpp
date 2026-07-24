// A separately linked freestanding C++ process. This validates constructor
// startup, C allocation, C++ new/delete, and syscall linkage at ring 3.

using size_type = unsigned long;

extern "C" unsigned long mortos_write(const char *, unsigned long);
extern "C" unsigned long mortos_getpid();
extern "C" void *malloc(size_type);
extern "C" void free(void *);
extern "C" void *calloc(size_type, size_type);
extern "C" void *realloc(void *, size_type);
extern "C" unsigned long mortos_mmap(
    unsigned long, unsigned long, unsigned long,
    unsigned long, unsigned long, unsigned long);
extern "C" unsigned long mortos_munmap(unsigned long, unsigned long);
extern "C" unsigned long mortos_arch_prctl(unsigned long, unsigned long);
extern "C" unsigned long mortos_yield();
extern "C" void mortos_fs_store(unsigned long, unsigned long);
extern "C" unsigned long mortos_fs_load(unsigned long);
extern "C" unsigned long mortos_gettid();
extern "C" unsigned long mortos_thread_create(
    unsigned long, unsigned long, unsigned long);
extern "C" unsigned long mortos_read(
    unsigned long, void *, unsigned long);
extern "C" unsigned long mortos_close(unsigned long);
extern "C" unsigned long mortos_pipe2(unsigned int *, unsigned long);
extern "C" unsigned long mortos_fd_write(
    unsigned long, const void *, unsigned long);
extern "C" unsigned long mortos_futex(
    unsigned int *, unsigned long, unsigned int);
extern "C" unsigned long mortos_poll(
    void *, unsigned long, unsigned long);

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

struct PollDescriptor {
    int descriptor;
    unsigned short events;
    unsigned short returned;
};

static const char pipe_message[] = "descriptor-ipc";

struct PipeWorkerArguments {
    unsigned int write_descriptor;
};

extern "C" unsigned long thread_worker(void *opaque) {
    if (mortos_getpid() != 5 || mortos_gettid() == 5) {
        return 30;
    }
    if (mortos_yield() != 0) {
        return 30;
    }
    auto *ready = static_cast<unsigned int *>(opaque);
    __atomic_store_n(ready, 1U, __ATOMIC_RELEASE);
    if (mortos_futex(ready, 1, 1) != 1) {
        return 30;
    }
    return 31;
}

extern "C" unsigned long pipe_worker(void *opaque) {
    if (mortos_yield() != 0) {
        return 40;
    }
    auto *arguments = static_cast<PipeWorkerArguments *>(opaque);
    if (mortos_fd_write(
            arguments->write_descriptor,
            pipe_message,
            sizeof(pipe_message) - 1) != sizeof(pipe_message) - 1) {
        return 40;
    }
    return 32;
}

extern "C" int main() {
    if (mortos_getpid() != 5
        || constructor_value != 0x435858434F4E5354UL) {
        return 1;
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

    unsigned long tls = mortos_mmap(0, 4096, 3, 0x22, ~0UL, 0);
    if (tls >= ~4095UL
        || mortos_arch_prctl(0x1002, tls) != 0) {
        return 8;
    }
    mortos_fs_store(8, 0x544C5356414C5545UL);
    unsigned long atomic_value = 10;
    if (__atomic_fetch_add(&atomic_value, 7, __ATOMIC_SEQ_CST) != 10
        || atomic_value != 17) {
        return 9;
    }
    unsigned long thread_stack = mortos_mmap(
        0, 8192, 3, 0x22, ~0UL, 0);
    if (thread_stack >= ~4095UL) {
        return 9;
    }
    unsigned int thread_ready = 0;
    unsigned long thread_id = mortos_thread_create(
        reinterpret_cast<unsigned long>(&thread_worker),
        thread_stack + 8192,
        reinterpret_cast<unsigned long>(&thread_ready));
    if (thread_id <= 5) {
        return 9;
    }
    unsigned long futex_result = mortos_futex(&thread_ready, 0, 0);
    if (futex_result != 0 && futex_result != ~10UL) {
        return 9;
    }
    if (__atomic_load_n(&thread_ready, __ATOMIC_ACQUIRE) != 1) {
        return 9;
    }
    if (mortos_fs_load(8) != 0x544C5356414C5545UL
        || mortos_arch_prctl(0x1003, tls + 16) != 0
        || *reinterpret_cast<unsigned long *>(tls + 16) != tls) {
        return 9;
    }
    if (mortos_munmap(thread_stack, 8192) != 0) {
        return 9;
    }
    if (mortos_arch_prctl(0x1002, 0) != 0
        || mortos_munmap(tls, 4096) != 0) {
        return 10;
    }

    unsigned int pipe_descriptors[2] = {};
    char pipe_result[sizeof(pipe_message)] = {};
    if (mortos_pipe2(pipe_descriptors, 0) != 0) {
        return 11;
    }
    unsigned long pipe_stack = mortos_mmap(
        0, 8192, 3, 0x22, ~0UL, 0);
    if (pipe_stack >= ~4095UL) {
        return 11;
    }
    PipeWorkerArguments pipe_arguments = {pipe_descriptors[1]};
    unsigned long pipe_thread = mortos_thread_create(
        reinterpret_cast<unsigned long>(&pipe_worker),
        pipe_stack + 8192,
        reinterpret_cast<unsigned long>(&pipe_arguments));
    if (pipe_thread <= thread_id) {
        return 11;
    }
    PollDescriptor readiness[1] = {
        {static_cast<int>(pipe_descriptors[0]), 1, 0},
    };
    if (mortos_poll(readiness, 1, 1000) != 1
        || (readiness[0].returned & 1) == 0
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
    readiness[0].returned = 0;
    if (mortos_poll(readiness, 1, 20) != 0
        || readiness[0].returned != 0) {
        return 11;
    }
    if (mortos_close(pipe_descriptors[0]) != 0
        || mortos_close(pipe_descriptors[1]) != 0
        || mortos_munmap(pipe_stack, 8192) != 0) {
        return 11;
    }

    static const char message[] = "MORT64 CXX RUNTIME OK\r\n";
    if (mortos_write(message, sizeof(message) - 1) != sizeof(message) - 1) {
        return 7;
    }
    return 23;
}
