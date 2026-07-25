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

#ifdef __cplusplus
}
#endif

#endif
