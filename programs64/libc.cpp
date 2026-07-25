// First reusable libc slice for x86_64-mortos.
//
// The CRT establishes one TLS page for the main thread before constructors.
// FS:0 is the self pointer, FS:8 stores errno, and FS:40 carries the stack
// protector canary sourced from the kernel-provided AT_RANDOM bytes.

#include <errno.h>
#include <mortos/syscall.h>
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
