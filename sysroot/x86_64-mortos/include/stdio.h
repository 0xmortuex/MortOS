#ifndef MORTOS_STDIO_H
#define MORTOS_STDIO_H

#include <sys/types.h>

typedef struct __mortos_file FILE;
typedef long fpos_t;

#define EOF (-1)
#define SEEK_SET 0
#define SEEK_CUR 1
#define SEEK_END 2

#ifdef __cplusplus
extern "C" {
#endif

FILE *fopen(const char *path, const char *mode);
FILE *fdopen(int descriptor, const char *mode);
int fclose(FILE *stream);
int fileno(FILE *stream);
size_t fread(void *buffer, size_t size, size_t count, FILE *stream);
size_t fwrite(
    const void *buffer, size_t size, size_t count, FILE *stream);
int fflush(FILE *stream);
int ferror(FILE *stream);
int feof(FILE *stream);
void clearerr(FILE *stream);
int printf(const char *format, ...);
int fprintf(FILE *stream, const char *format, ...);
int snprintf(char *buffer, size_t size, const char *format, ...);
int vsnprintf(
    char *buffer, size_t size, const char *format, __builtin_va_list args);
int puts(const char *text);
int fputs(const char *text, FILE *stream);
int remove(const char *path);
int rename(const char *old_path, const char *new_path);

extern FILE *stdin;
extern FILE *stdout;
extern FILE *stderr;

#ifdef __cplusplus
}
#endif

#endif
