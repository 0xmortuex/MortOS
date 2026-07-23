// Minimal freestanding allocation and C++ ABI support for x86_64-mortos.
//
// The allocator intentionally uses one anonymous mapping per allocation at
// this bootstrap stage. It prioritizes correct ownership, overflow handling,
// and reclamation; arenas and size classes follow with the full libc port.

using size_type = unsigned long;

extern "C" unsigned long mortos_mmap(
    unsigned long, unsigned long, unsigned long,
    unsigned long, unsigned long, unsigned long);
extern "C" unsigned long mortos_munmap(unsigned long, unsigned long);

static constexpr unsigned long MAP_FAILED_LIMIT = ~4095UL;
static constexpr unsigned long HEADER_SIZE = 16;

extern "C" void *malloc(size_type requested) noexcept {
    if (requested == 0) {
        requested = 1;
    }
    if (requested > ~0UL - HEADER_SIZE) {
        return nullptr;
    }
    unsigned long total = requested + HEADER_SIZE;
    if (total > ~0UL - 4095) {
        return nullptr;
    }
    unsigned long mapped = (total + 4095) & ~4095UL;
    unsigned long base = mortos_mmap(
        0, mapped, 3, 0x22, ~0UL, 0);
    if (base >= MAP_FAILED_LIMIT) {
        return nullptr;
    }
    auto *header = reinterpret_cast<unsigned long *>(base);
    header[0] = mapped;
    header[1] = requested;
    return reinterpret_cast<void *>(base + HEADER_SIZE);
}

extern "C" void free(void *pointer) noexcept {
    if (!pointer) {
        return;
    }
    auto address = reinterpret_cast<unsigned long>(pointer);
    auto *header =
        reinterpret_cast<unsigned long *>(address - HEADER_SIZE);
    mortos_munmap(address - HEADER_SIZE, header[0]);
}

extern "C" void *calloc(size_type count, size_type size) noexcept {
    if (count != 0 && size > ~0UL / count) {
        return nullptr;
    }
    size_type bytes = count * size;
    auto *result = static_cast<unsigned char *>(malloc(bytes));
    if (!result) {
        return nullptr;
    }
    for (size_type index = 0; index < bytes; ++index) {
        result[index] = 0;
    }
    return result;
}

extern "C" void *realloc(void *pointer, size_type requested) noexcept {
    if (!pointer) {
        return malloc(requested);
    }
    if (requested == 0) {
        free(pointer);
        return nullptr;
    }
    auto address = reinterpret_cast<unsigned long>(pointer);
    auto *header =
        reinterpret_cast<unsigned long *>(address - HEADER_SIZE);
    size_type old_size = header[1];
    void *replacement = malloc(requested);
    if (!replacement) {
        return nullptr;
    }
    size_type copy = old_size < requested ? old_size : requested;
    auto *source = static_cast<unsigned char *>(pointer);
    auto *destination = static_cast<unsigned char *>(replacement);
    for (size_type index = 0; index < copy; ++index) {
        destination[index] = source[index];
    }
    free(pointer);
    return replacement;
}

void *operator new(size_type size) {
    return malloc(size);
}

void *operator new[](size_type size) {
    return malloc(size);
}

void operator delete(void *pointer) noexcept {
    free(pointer);
}

void operator delete[](void *pointer) noexcept {
    free(pointer);
}

void operator delete(void *pointer, size_type) noexcept {
    free(pointer);
}

void operator delete[](void *pointer, size_type) noexcept {
    free(pointer);
}

extern "C" {
void *__dso_handle = nullptr;

int __cxa_atexit(void (*)(void *), void *, void *) {
    return 0;
}

[[noreturn]] void __cxa_pure_virtual() {
    for (;;) {
        __asm__ volatile("ud2");
    }
}
}
