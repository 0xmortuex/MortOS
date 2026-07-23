/* Small Mort-callable wrappers for the x86-64 MortOS syscall convention. */

.section .text
.code64
.global mortos_write
.type mortos_write, @function
mortos_write:
    /* Mort/System V: rdi=text, rsi=length. Kernel: fd, buffer, length. */
    mov %rsi, %rdx
    mov %rdi, %rsi
    mov $1, %rdi
    mov $1, %rax
    syscall
    ret
.size mortos_write, . - mortos_write

.global mortos_getpid
.type mortos_getpid, @function
mortos_getpid:
    mov $39, %rax                  /* SYS_getpid */
    syscall
    ret
.size mortos_getpid, . - mortos_getpid

.global mortos_yield
.type mortos_yield, @function
mortos_yield:
    mov $24, %rax                  /* SYS_yield */
    syscall
    ret
.size mortos_yield, . - mortos_yield

.global mortos_brk
.type mortos_brk, @function
mortos_brk:
    mov $12, %rax                  /* SYS_brk */
    syscall
    ret
.size mortos_brk, . - mortos_brk

.global mortos_clock_gettime
.type mortos_clock_gettime, @function
mortos_clock_gettime:
    /* rdi=clock id, rsi=timespec pointer */
    mov $228, %rax                 /* SYS_clock_gettime */
    syscall
    ret
.size mortos_clock_gettime, . - mortos_clock_gettime

.global mortos_mmap
.type mortos_mmap, @function
mortos_mmap:
    /* System V arg3 is RCX; the syscall ABI uses R10. */
    mov %rcx, %r10
    mov $9, %rax                   /* SYS_mmap */
    syscall
    ret
.size mortos_mmap, . - mortos_mmap

.global mortos_mprotect
.type mortos_mprotect, @function
mortos_mprotect:
    mov $10, %rax                  /* SYS_mprotect */
    syscall
    ret
.size mortos_mprotect, . - mortos_mprotect

.global mortos_munmap
.type mortos_munmap, @function
mortos_munmap:
    mov $11, %rax                  /* SYS_munmap */
    syscall
    ret
.size mortos_munmap, . - mortos_munmap

.global mortos_call0
.type mortos_call0, @function
mortos_call0:
    mov %rdi, %rax
    sub $8, %rsp
    call *%rax
    add $8, %rsp
    ret
.size mortos_call0, . - mortos_call0

.global mortos_spin
.type mortos_spin, @function
mortos_spin:
    /* Deliberately non-cooperative work used by the IRQ0 preemption test. */
    mov %rdi, %rcx
.Lmortos_spin_loop:
    dec %rcx
    jnz .Lmortos_spin_loop
    ret
.size mortos_spin, . - mortos_spin

/*
 * A second fixed ELF entry used only by the kernel isolation test. It attempts
 * a direct read from the supervisor-only kernel mapping. Reaching SYS_exit
 * means page protection failed.
 */
.section .userfault, "ax", @progbits
.global _user_fault_start
.type _user_fault_start, @function
_user_fault_start:
    mov $0x00200000, %rax
    mov (%rax), %rax
    mov $99, %rdi
    mov $60, %rax
    syscall
    ud2
.size _user_fault_start, . - _user_fault_start
