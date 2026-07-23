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
