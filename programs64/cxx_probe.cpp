// A separately linked freestanding C++ process. This validates constructor
// startup, C allocation, C++ new/delete, and syscall linkage at ring 3.

using size_type = unsigned long;

extern "C" unsigned long mortos_write(const char *, unsigned long);
extern "C" unsigned long mortos_getpid();
extern "C" void *malloc(size_type);
extern "C" void free(void *);
extern "C" void *calloc(size_type, size_type);
extern "C" void *realloc(void *, size_type);

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

    static const char message[] = "MORT64 CXX RUNTIME OK\r\n";
    if (mortos_write(message, sizeof(message) - 1) != sizeof(message) - 1) {
        return 7;
    }
    return 23;
}
