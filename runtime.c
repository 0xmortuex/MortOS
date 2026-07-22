#include <stddef.h>

// Minimal freestanding memory primitives used when the optimizer lowers Mort
// array initialization or copies. MortOS does not link a hosted C library.
void *memset(void *destination, int value, size_t count) {
    unsigned char *out = (unsigned char *)destination;
    while (count != 0) {
        *out++ = (unsigned char)value;
        --count;
    }
    return destination;
}

void *memcpy(void *destination, const void *source, size_t count) {
    unsigned char *out = (unsigned char *)destination;
    const unsigned char *in = (const unsigned char *)source;
    while (count != 0) {
        *out++ = *in++;
        --count;
    }
    return destination;
}

void *memmove(void *destination, const void *source, size_t count) {
    unsigned char *out = (unsigned char *)destination;
    const unsigned char *in = (const unsigned char *)source;
    if (out < in) {
        return memcpy(destination, source, count);
    }
    while (count != 0) {
        --count;
        out[count] = in[count];
    }
    return destination;
}
