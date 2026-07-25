#ifndef MORTOS_STRING_H
#define MORTOS_STRING_H

#include <sys/types.h>

#ifdef __cplusplus
extern "C" {
#endif

void *memcpy(void *destination, const void *source, size_t length);
void *memmove(void *destination, const void *source, size_t length);
void *memset(void *destination, int value, size_t length);
int memcmp(const void *left, const void *right, size_t length);
void *memchr(const void *memory, int value, size_t length);

size_t strlen(const char *string);
size_t strnlen(const char *string, size_t maximum);
char *strcpy(char *destination, const char *source);
char *strncpy(char *destination, const char *source, size_t length);
char *strcat(char *destination, const char *source);
char *strncat(char *destination, const char *source, size_t length);
int strcmp(const char *left, const char *right);
int strncmp(const char *left, const char *right, size_t length);
char *strchr(const char *string, int character);
char *strrchr(const char *string, int character);
char *strstr(const char *haystack, const char *needle);
char *strdup(const char *string);
char *strndup(const char *string, size_t length);
char *strerror(int error);

#ifdef __cplusplus
}
#endif

#endif
