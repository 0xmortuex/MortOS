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

int memcmp(const void *left, const void *right, size_t count) {
    const unsigned char *a = (const unsigned char *)left;
    const unsigned char *b = (const unsigned char *)right;
    while (count != 0) {
        if (*a != *b)
            return *a < *b ? -1 : 1;
        ++a;
        ++b;
        --count;
    }
    return 0;
}

void *memchr(const void *memory, int value, size_t count) {
    const unsigned char *bytes = (const unsigned char *)memory;
    while (count != 0) {
        if (*bytes == (unsigned char)value)
            return (void *)bytes;
        ++bytes;
        --count;
    }
    return (void *)0;
}

size_t strlen(const char *string) {
    const char *end = string;
    while (*end != '\0')
        ++end;
    return (size_t)(end - string);
}

size_t strnlen(const char *string, size_t maximum) {
    size_t length = 0;
    while (length < maximum && string[length] != '\0')
        ++length;
    return length;
}

int strcmp(const char *left, const char *right) {
    while (*left != '\0' && *left == *right) {
        ++left;
        ++right;
    }
    return (unsigned char)*left - (unsigned char)*right;
}

int strncmp(const char *left, const char *right, size_t count) {
    while (count != 0 && *left != '\0' && *left == *right) {
        ++left;
        ++right;
        --count;
    }
    if (count == 0)
        return 0;
    return (unsigned char)*left - (unsigned char)*right;
}

char *strchr(const char *string, int character) {
    do {
        if (*string == (char)character)
            return (char *)string;
    } while (*string++ != '\0');
    return (char *)0;
}

char *strrchr(const char *string, int character) {
    const char *result = (const char *)0;
    do {
        if (*string == (char)character)
            result = string;
    } while (*string++ != '\0');
    return (char *)result;
}
