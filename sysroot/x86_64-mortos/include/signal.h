#ifndef MORTOS_SIGNAL_H
#define MORTOS_SIGNAL_H

#include <sys/types.h>

typedef struct {
    unsigned long __bits[16];
} sigset_t;

typedef void (*sighandler_t)(int);

union sigval {
    int sival_int;
    void *sival_ptr;
};

typedef struct {
    int si_signo;
    int si_errno;
    int si_code;
    int __pad;
    union sigval si_value;
    unsigned char __reserved[112];
} siginfo_t;

struct sigaction {
    union {
        sighandler_t sa_handler;
        void (*sa_sigaction)(int, siginfo_t *, void *);
    };
    sigset_t sa_mask;
    int sa_flags;
    void (*sa_restorer)(void);
};

#define SIGHUP 1
#define SIGINT 2
#define SIGQUIT 3
#define SIGILL 4
#define SIGTRAP 5
#define SIGABRT 6
#define SIGBUS 7
#define SIGFPE 8
#define SIGKILL 9
#define SIGSEGV 11
#define SIGPIPE 13
#define SIGALRM 14
#define SIGTERM 15
#define SIGCHLD 17
#define SIGCONT 18
#define SIGSTOP 19
#define SIGTSTP 20
#define SIGTTIN 21
#define SIGTTOU 22
#define SIGPROF 27
#define SIGSYS 31

#define SIG_BLOCK 0
#define SIG_UNBLOCK 1
#define SIG_SETMASK 2

#define SIG_DFL ((sighandler_t)0)
#define SIG_IGN ((sighandler_t)1)
#define SIG_ERR ((sighandler_t)-1)

#define SA_NOCLDSTOP 0x00000001
#define SA_NOCLDWAIT 0x00000002
#define SA_SIGINFO 0x00000004
#define SA_RESTART 0x10000000
#define SA_RESETHAND 0x80000000

#ifdef __cplusplus
extern "C" {
#endif

sighandler_t signal(int signal_number, sighandler_t handler);
int sigaction(
    int signal_number, const struct sigaction *action,
    struct sigaction *old_action);
int sigemptyset(sigset_t *set);
int sigfillset(sigset_t *set);
int sigaddset(sigset_t *set, int signal_number);
int sigdelset(sigset_t *set, int signal_number);
int sigismember(const sigset_t *set, int signal_number);
int sigprocmask(int how, const sigset_t *set, sigset_t *old_set);
int pthread_sigmask(int how, const sigset_t *set, sigset_t *old_set);
int raise(int signal_number);
int kill(pid_t process, int signal_number);

#ifdef __cplusplus
}
#endif

#endif
