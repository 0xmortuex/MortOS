#ifndef MORTOS_STDLIB_H
#define MORTOS_STDLIB_H

#ifdef __cplusplus
extern "C" {
#endif

#ifndef __MORTOS_SIZE_T_DEFINED
#define __MORTOS_SIZE_T_DEFINED
typedef unsigned long size_t;
#endif

void *malloc(size_t size);
void free(void *pointer);
void *calloc(size_t count, size_t size);
void *realloc(void *pointer, size_t size);
void abort(void) __attribute__((noreturn));
void exit(int status) __attribute__((noreturn));
void _Exit(int status) __attribute__((noreturn));
char *getenv(const char *name);
int setenv(const char *name, const char *value, int overwrite);
int unsetenv(const char *name);
int atoi(const char *text);
long strtol(const char *text, char **end, int base);
unsigned long strtoul(const char *text, char **end, int base);
char *realpath(const char *path, char *resolved_path);

#ifdef __cplusplus
}
#endif

#endif
