// A separately linked freestanding C++ process. This validates constructor
// startup, C allocation, C++ new/delete, and syscall linkage at ring 3.

#include <mortos/syscall.h>
#include <errno.h>
#include <stdlib.h>
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

struct PollDescriptor {
    int descriptor;
    unsigned short events;
    unsigned short returned;
};

struct __attribute__((packed)) EpollEvent {
    unsigned int events;
    unsigned long data;
};

static const char pipe_message[] = "descriptor-ipc";

struct PipeWorkerArguments {
    unsigned int write_descriptor;
};

struct EventWorkerArguments {
    unsigned int descriptor;
    unsigned long value;
};

extern "C" __attribute__((no_stack_protector))
unsigned long thread_worker(void *opaque) {
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

extern "C" __attribute__((no_stack_protector))
unsigned long pipe_worker(void *opaque) {
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

extern "C" __attribute__((no_stack_protector))
unsigned long event_worker(void *opaque) {
    if (mortos_yield() != 0) {
        return 41;
    }
    auto *arguments = static_cast<EventWorkerArguments *>(opaque);
    if (mortos_fd_write(
            arguments->descriptor,
            &arguments->value,
            sizeof(arguments->value)) != sizeof(arguments->value)) {
        return 41;
    }
    return 33;
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
    if (mortos_arch_prctl(0x1002, runtime_tls) != 0
        || mortos_munmap(tls, 4096) != 0
        || errno != EBADF) {
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

    unsigned long event_descriptor = mortos_eventfd2(0, 0x80800);
    unsigned long epoll_descriptor = mortos_epoll_create1(0x80000);
    unsigned long event_stack = mortos_mmap(
        0, 8192, 3, 0x22, ~0UL, 0);
    if (event_descriptor >= ~4095UL
        || epoll_descriptor >= ~4095UL
        || event_stack >= ~4095UL) {
        return 18;
    }
    EpollEvent event_interest = {1U, 0x45504F4C4C564558UL};
    if (mortos_epoll_ctl(
            epoll_descriptor, 1, event_descriptor,
            &event_interest) != 0) {
        return 18;
    }
    event_interest.data = 0x45504F4C4C4D4F44UL;
    if (mortos_epoll_ctl(
            epoll_descriptor, 3, event_descriptor,
            &event_interest) != 0) {
        return 18;
    }
    EventWorkerArguments event_arguments = {
        static_cast<unsigned int>(event_descriptor), 7UL};
    unsigned long event_thread = mortos_thread_create(
        reinterpret_cast<unsigned long>(&event_worker),
        event_stack + 8192,
        reinterpret_cast<unsigned long>(&event_arguments));
    EpollEvent event_readiness = {};
    unsigned long event_value = 0;
    if (event_thread <= pipe_thread
        || mortos_epoll_wait(
            epoll_descriptor, &event_readiness, 1, 1000) != 1
        || (event_readiness.events & 1) == 0
        || event_readiness.data != 0x45504F4C4C4D4F44UL
        || mortos_read(
            event_descriptor, &event_value, sizeof(event_value)) != 8
        || event_value != 7
        || mortos_read(
            event_descriptor, &event_value, sizeof(event_value)) != ~10UL
        || mortos_epoll_wait(
            epoll_descriptor, &event_readiness, 1, 20) != 0
        || mortos_epoll_ctl(
            epoll_descriptor, 2, event_descriptor, nullptr) != 0
        || mortos_close(epoll_descriptor) != 0
        || mortos_close(event_descriptor) != 0
        || mortos_munmap(event_stack, 8192) != 0) {
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

    static const char message[] = "MORT64 CXX RUNTIME OK\r\n";
    if (mortos_write(message, sizeof(message) - 1) != sizeof(message) - 1) {
        return 7;
    }
    return 23;
}
