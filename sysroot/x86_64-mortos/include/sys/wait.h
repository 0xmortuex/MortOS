#ifndef MORTOS_SYS_WAIT_H
#define MORTOS_SYS_WAIT_H

#include <sys/types.h>

#define WNOHANG 1
#define WUNTRACED 2
#define WCONTINUED 8

#define WEXITSTATUS(status) (((status) & 0xFF00) >> 8)
#define WTERMSIG(status) ((status) & 0x7F)
#define WSTOPSIG(status) WEXITSTATUS(status)
#define WIFEXITED(status) (WTERMSIG(status) == 0)
#define WIFSIGNALED(status) \
    (((signed char)(((status) & 0x7F) + 1) >> 1) > 0)
#define WIFSTOPPED(status) (((status) & 0xFF) == 0x7F)
#define WIFCONTINUED(status) ((status) == 0xFFFF)

#ifdef __cplusplus
extern "C" {
#endif

pid_t wait(int *status);
pid_t waitpid(pid_t process, int *status, int options);

#ifdef __cplusplus
}
#endif

#endif
