/* ELF64 Mort userspace entry using the MortOS AMD64 syscall ABI. */

.section .text.entry, "ax", @progbits
.code64
.global _user_start
.type _user_start, @function
_user_start:
    and $-16, %rsp
    call mort_main
    mov %rax, %rdi                  /* exit status */
    mov $60, %rax                   /* SYS_exit */
    syscall
    ud2
.size _user_start, . - _user_start
