/* Freestanding C/C++ process entry with static-constructor startup. */

.section .text.entry, "ax", @progbits
.code64
.global _user_start
.type _user_start, @function
_user_start:
    and $-16, %rsp
    lea __init_array_start(%rip), %r12
    lea __init_array_end(%rip), %rbx
.Lconstructor_loop:
    cmp %rbx, %r12
    jae .Lconstructors_done
    call *(%r12)
    add $8, %r12
    jmp .Lconstructor_loop
.Lconstructors_done:
    call main
    mov %eax, %edi
    mov $60, %rax
    syscall
    ud2
.size _user_start, . - _user_start
