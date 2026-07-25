#ifndef MORTOS_UNISTD_H
#define MORTOS_UNISTD_H

#include <sys/types.h>

#define STDIN_FILENO 0
#define STDOUT_FILENO 1
#define STDERR_FILENO 2

#define F_OK 0
#define X_OK 1
#define W_OK 2
#define R_OK 4

#define _SC_PAGESIZE 30
#define _SC_OPEN_MAX 4
#define _SC_CLK_TCK 2
#define _SC_NPROCESSORS_ONLN 84

#ifdef __cplusplus
extern "C" {
#endif

ssize_t read(int descriptor, void *buffer, size_t length);
ssize_t write(int descriptor, const void *buffer, size_t length);
int close(int descriptor);
int dup(int descriptor);
int dup2(int old_descriptor, int new_descriptor);
pid_t getpid(void);
pid_t gettid(void);
pid_t getppid(void);
uid_t getuid(void);
uid_t geteuid(void);
gid_t getgid(void);
gid_t getegid(void);
off_t lseek(int descriptor, off_t offset, int origin);
int pipe(int descriptors[2]);
int pipe2(int descriptors[2], int flags);
unsigned int sleep(unsigned int seconds);
int usleep(unsigned int microseconds);
char *getcwd(char *buffer, size_t size);
int chdir(const char *path);
int access(const char *path, int mode);
int unlink(const char *path);
int rmdir(const char *path);
int isatty(int descriptor);
long sysconf(int name);
int getpagesize(void);
int gethostname(char *name, size_t length);
pid_t fork(void);
pid_t setsid(void);
int setuid(uid_t uid);
int setgid(gid_t gid);
int execve(
    const char *path, char *const arguments[], char *const environment[]);
int execvp(const char *file, char *const arguments[]);
int execvpe(
    const char *file, char *const arguments[], char *const environment[]);
void _exit(int status) __attribute__((noreturn));

#ifdef __cplusplus
}
#endif

#endif
