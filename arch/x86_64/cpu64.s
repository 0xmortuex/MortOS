/*
 * x86-64 protected-execution support for MORT OS.
 *
 * Policy remains in Mort. This file contains only the architectural mechanics
 * that cannot be expressed portably: descriptor tables, interrupt frames,
 * model-specific registers, ring transitions, and SYSCALL/SYSRET.
 */

.set KERNEL_CODE, 0x08
.set KERNEL_DATA, 0x10
.set USER_DATA,   0x1B
.set USER_CODE,   0x23
.set TSS_SELECTOR, 0x28

.section .text
.code64

.type mort64_set_idt_gate, @function
mort64_set_idt_gate:
    /* edi = vector, rsi = handler, dl = gate attributes */
    lea mort64_idt(%rip), %rax
    shl $4, %rdi
    add %rdi, %rax
    movw %si, 0(%rax)
    movw $KERNEL_CODE, 2(%rax)
    movb $0, 4(%rax)
    movb %dl, 5(%rax)
    mov %rsi, %rcx
    shr $16, %rcx
    movw %cx, 6(%rax)
    shr $16, %rcx
    movl %ecx, 8(%rax)
    movl $0, 12(%rax)
    ret

.global mort64_cpu_init
.type mort64_cpu_init, @function
mort64_cpu_init:
    push %rbx
    push %r12
    push %r13

    /* Materialize the 64-bit available-TSS descriptor. */
    lea mort64_tss(%rip), %rax
    lea mort64_tss_descriptor(%rip), %rbx
    movw $103, 0(%rbx)
    movw %ax, 2(%rbx)
    shr $16, %rax
    movb %al, 4(%rbx)
    movb $0x89, 5(%rbx)             /* present, DPL0, available 64-bit TSS */
    movb $0, 6(%rbx)
    shr $8, %rax
    movb %al, 7(%rbx)
    shr $8, %rax
    movl %eax, 8(%rbx)
    movl $0, 12(%rbx)
    mov %rsp, mort64_tss+4(%rip)    /* RSP0 */
    movw $104, mort64_tss+102(%rip) /* no userspace I/O bitmap */

    lgdt mort64_gdt_pointer(%rip)
    pushq $KERNEL_CODE
    lea .Lgdt_loaded(%rip), %rax
    push %rax
    lretq
.Lgdt_loaded:
    mov $KERNEL_DATA, %ax
    mov %ax, %ds
    mov %ax, %es
    mov %ax, %ss
    xor %ax, %ax
    mov %ax, %fs
    mov %ax, %gs
    mov $TSS_SELECTOR, %ax
    ltr %ax

    /* Clear the IDT and install all architectural exception vectors. */
    lea mort64_idt(%rip), %rdi
    xor %rax, %rax
    mov $512, %ecx
    rep stosq
    xor %r12d, %r12d
    lea mort64_exception_stub_table(%rip), %r13
.Linstall_exception_gate:
    mov %r12d, %edi
    mov (%r13,%r12,8), %rsi
    mov $0x8E, %edx                 /* present DPL0 interrupt gate */
    cmp $3, %r12d
    jne .Lgate_ready
    mov $0x8F, %edx                 /* breakpoint is a trap gate */
.Lgate_ready:
    call mort64_set_idt_gate
    inc %r12d
    cmp $32, %r12d
    jb .Linstall_exception_gate
    mov $32, %edi
    lea mort64_irq0(%rip), %rsi
    mov $0x8E, %edx
    call mort64_set_idt_gate
    lidt mort64_idt_pointer(%rip)

    /* NX is mandatory for the userspace security contract. */
    mov $0x80000000, %eax
    cpuid
    cmp $0x80000001, %eax
    jb .Lcpu_init_failed
    mov $0x80000001, %eax
    cpuid
    test $(1 << 20), %edx
    jz .Lcpu_init_failed

    /* Enable SYSCALL and NX in EFER. Long mode is already active. */
    mov $0xC0000080, %ecx
    rdmsr
    or $0x801, %eax                 /* SCE | LME | NXE */
    wrmsr

    /* STAR: SYSCALL CS=0x08/SS=0x10, SYSRET CS=0x23/SS=0x1b. */
    mov $0xC0000081, %ecx
    xor %eax, %eax
    mov $0x00130008, %edx
    wrmsr

    mov $0xC0000082, %ecx           /* IA32_LSTAR */
    lea mort64_syscall_entry(%rip), %rax
    mov %rax, %rdx
    shr $32, %rdx
    wrmsr

    mov $0xC0000084, %ecx           /* IA32_FMASK: clear TF, IF, DF */
    mov $0x700, %eax
    xor %edx, %edx
    wrmsr

    mov $1, %eax
    jmp .Lcpu_init_done
.Lcpu_init_failed:
    xor %eax, %eax
.Lcpu_init_done:
    pop %r13
    pop %r12
    pop %rbx
    ret
.size mort64_cpu_init, . - mort64_cpu_init

.global mort64_idt_self_test
.type mort64_idt_self_test, @function
mort64_idt_self_test:
    int3
    ret

.global mort64_enter_user
.type mort64_enter_user, @function
mort64_enter_user:
    /* rdi=entry, rsi=stack top, rdx=process CR3 */
    push %rbx
    push %rbp
    push %r12
    push %r13
    push %r14
    push %r15
    mov %rsp, mort64_kernel_rsp(%rip)
    mov %rsp, mort64_tss+4(%rip)
    mov %cr3, %rax
    mov %rax, mort64_kernel_cr3(%rip)
    mov %rdx, %cr3

    pushq $USER_DATA
    push %rsi
    pushq $0x202                    /* reserved bit + user interrupts enabled */
    pushq $USER_CODE
    push %rdi
    iretq
.size mort64_enter_user, . - mort64_enter_user

.global mort64_resume_user
.type mort64_resume_user, @function
mort64_resume_user:
    /* rdi=full saved context, rsi=process CR3 */
    push %rbx
    push %rbp
    push %r12
    push %r13
    push %r14
    push %r15
    mov %rsp, mort64_kernel_rsp(%rip)
    mov %rsp, mort64_tss+4(%rip)
    mov %cr3, %rax
    mov %rax, mort64_kernel_cr3(%rip)
    mov %rsi, %cr3

    mov %rdi, mort64_resume_context(%rip)
    pushq $USER_DATA
    pushq 136(%rdi)                /* user RSP */
    pushq 128(%rdi)                /* user RFLAGS */
    pushq $USER_CODE
    pushq 120(%rdi)                /* user RIP */
    mov 0(%rdi), %r15
    mov 8(%rdi), %r14
    mov 16(%rdi), %r13
    mov 24(%rdi), %r12
    mov 32(%rdi), %r11
    mov 40(%rdi), %r10
    mov 48(%rdi), %r9
    mov 56(%rdi), %r8
    mov 64(%rdi), %rsi
    mov 80(%rdi), %rbp
    mov 88(%rdi), %rdx
    mov 96(%rdi), %rcx
    mov 104(%rdi), %rbx
    mov 72(%rdi), %rdi
    mov mort64_resume_context(%rip), %rax
    mov 112(%rax), %rax
    iretq
.size mort64_resume_user, . - mort64_resume_user

.global mort64_flush_tlb
.type mort64_flush_tlb, @function
mort64_flush_tlb:
    mov %cr3, %rax
    mov %rax, %cr3
    ret
.size mort64_flush_tlb, . - mort64_flush_tlb

.global mort64_set_user_fs
.type mort64_set_user_fs, @function
mort64_set_user_fs:
    mov %rdi, %rax
    mov %rdi, %rdx
    shr $32, %rdx
    mov $0xC0000100, %ecx           /* IA32_FS_BASE */
    wrmsr
    ret
.size mort64_set_user_fs, . - mort64_set_user_fs

.global mort64_rdrand_supported
.type mort64_rdrand_supported, @function
mort64_rdrand_supported:
    push %rbx
    mov $1, %eax
    cpuid
    bt $30, %ecx
    setc %al
    movzbl %al, %eax
    pop %rbx
    ret
.size mort64_rdrand_supported, . - mort64_rdrand_supported

.global mort64_rdrand_store
.type mort64_rdrand_store, @function
mort64_rdrand_store:
    mov $10, %ecx
.Lrdrand_retry:
    rdrand %rax
    jc .Lrdrand_ready
    loop .Lrdrand_retry
    xor %eax, %eax
    ret
.Lrdrand_ready:
    mov %rax, (%rdi)
    mov $1, %eax
    ret
.size mort64_rdrand_store, . - mort64_rdrand_store

.type mort64_syscall_entry, @function
mort64_syscall_entry:
    cmp $232, %rax                  /* blocking epoll_wait */
    jne .Lnot_epoll_wait
    cmp $0, %r10
    jne .Lsyscall_epoll_wait
.Lnot_epoll_wait:
    cmp $7, %rax                    /* blocking poll returns to scheduler */
    jne .Lnot_poll_wait
    cmp $0, %rdx
    jne .Lsyscall_poll_wait
.Lnot_poll_wait:
    cmp $202, %rax                  /* FUTEX_WAIT needs a scheduler return */
    jne .Lnot_futex_wait
    cmp $0, %rsi
    je .Lsyscall_futex_wait
.Lnot_futex_wait:
    cmp $401, %rax                  /* blocking MortOS thread_join */
    je .Lsyscall_thread_join
    cmp $24, %rax                   /* cooperative process yield */
    je .Lsyscall_yield
    cmp $60, %rax                   /* process exit */
    je .Lsyscall_exit

    mov %rsp, mort64_user_rsp(%rip)
    mov mort64_kernel_rsp(%rip), %rsp
    push %r11
    push %rcx
    push %rbx
    push %rbp
    push %r12
    push %r13
    push %r14
    push %r15
    push %rdi
    push %rsi
    push %rdx
    push %r8
    push %r9
    push %r10
    /*
     * System V call:
     * dispatcher(number, arg0, arg1, arg2, arg3, arg4, arg5).
     * The seventh C argument is passed on the stack.
     */
    mov 8(%rsp), %r11              /* original R9: syscall arg5 */
    mov 0(%rsp), %r8               /* original R10: syscall arg3 */
    mov 16(%rsp), %r9              /* original R8: syscall arg4 */
    mov 24(%rsp), %rcx             /* original RDX: syscall arg2 */
    mov 32(%rsp), %rdx             /* original RSI: syscall arg1 */
    mov 40(%rsp), %rsi             /* original RDI: syscall arg0 */
    mov %rax, %rdi
    push %r11                      /* arg5 and call-site alignment */
    call mort_syscall_dispatch64
    add $8, %rsp
    pop %r10
    pop %r9
    pop %r8
    pop %rdx
    pop %rsi
    pop %rdi
    pop %r15
    pop %r14
    pop %r13
    pop %r12
    pop %rbp
    pop %rbx
    pop %rcx
    pop %r11
    mov mort64_user_rsp(%rip), %rsp
    sysretq

.Lsyscall_yield:
    /*
     * A syscall is a natural cooperative switch boundary: RCX/R11 contain the
     * resume RIP/RFLAGS and the System V callee-saved registers must survive
     * the Mort-callable yield wrapper.
     */
    mov %rsp, mort64_yield_rsp(%rip)
    mov %rcx, mort64_yield_rip(%rip)
    mov %r11, mort64_yield_rflags(%rip)
    mov %rbx, mort64_yield_rbx(%rip)
    mov %rbp, mort64_yield_rbp(%rip)
    mov %r12, mort64_yield_r12(%rip)
    mov %r13, mort64_yield_r13(%rip)
    mov %r14, mort64_yield_r14(%rip)
    mov %r15, mort64_yield_r15(%rip)
    mov mort64_kernel_rsp(%rip), %rsp
    cld
    sub $8, %rsp
    call mort_on_user_yield64
    add $8, %rsp
    test %rax, %rax
    jz .Lyield_return_kernel
.Lsave_blocked_context:
    mov mort64_yield_r15(%rip), %rdx
    mov %rdx, 0(%rax)
    mov mort64_yield_r14(%rip), %rdx
    mov %rdx, 8(%rax)
    mov mort64_yield_r13(%rip), %rdx
    mov %rdx, 16(%rax)
    mov mort64_yield_r12(%rip), %rdx
    mov %rdx, 24(%rax)
    movq $0, 32(%rax)               /* syscall-clobbered R11 */
    movq $0, 40(%rax)
    movq $0, 48(%rax)
    movq $0, 56(%rax)
    movq $0, 64(%rax)
    movq $0, 72(%rax)
    mov mort64_yield_rbp(%rip), %rdx
    mov %rdx, 80(%rax)
    movq $0, 88(%rax)
    movq $0, 96(%rax)               /* syscall-clobbered RCX */
    mov mort64_yield_rbx(%rip), %rdx
    mov %rdx, 104(%rax)
    movq $0, 112(%rax)              /* successful yield return */
    mov mort64_yield_rip(%rip), %rdx
    mov %rdx, 120(%rax)
    mov mort64_yield_rflags(%rip), %rdx
    or $0x200, %rdx                 /* keep timer delivery enabled */
    mov %rdx, 128(%rax)
    mov mort64_yield_rsp(%rip), %rdx
    mov %rdx, 136(%rax)
.Lyield_return_kernel:
    mov mort64_kernel_cr3(%rip), %rax
    mov %rax, %cr3
    pop %r15
    pop %r14
    pop %r13
    pop %r12
    pop %rbp
    pop %rbx
    ret

.Lsyscall_futex_wait:
    /*
     * Capture the syscall boundary exactly like yield, but let Mort policy
     * atomically validate the futex word and move this task to WAITING.
     */
    mov %rdi, mort64_futex_address(%rip)
    mov %rdx, mort64_futex_expected(%rip)
    mov %r10, mort64_futex_timeout(%rip)
    mov %rsp, mort64_yield_rsp(%rip)
    mov %rcx, mort64_yield_rip(%rip)
    mov %r11, mort64_yield_rflags(%rip)
    mov %rbx, mort64_yield_rbx(%rip)
    mov %rbp, mort64_yield_rbp(%rip)
    mov %r12, mort64_yield_r12(%rip)
    mov %r13, mort64_yield_r13(%rip)
    mov %r14, mort64_yield_r14(%rip)
    mov %r15, mort64_yield_r15(%rip)
    mov mort64_kernel_rsp(%rip), %rsp
    mov mort64_futex_address(%rip), %rdi
    mov mort64_futex_expected(%rip), %rsi
    mov mort64_futex_timeout(%rip), %rdx
    cld
    sub $8, %rsp
    call mort_on_futex_wait64
    add $8, %rsp
    test %rax, %rax
    js .Lfutex_wait_error
    jmp .Lsave_blocked_context

.Lfutex_wait_error:
    /* The word changed or the pointer was invalid; stay in the same task. */
    mov mort64_yield_rbx(%rip), %rbx
    mov mort64_yield_rbp(%rip), %rbp
    mov mort64_yield_r12(%rip), %r12
    mov mort64_yield_r13(%rip), %r13
    mov mort64_yield_r14(%rip), %r14
    mov mort64_yield_r15(%rip), %r15
    mov mort64_yield_rip(%rip), %rcx
    mov mort64_yield_rflags(%rip), %r11
    mov mort64_yield_rsp(%rip), %rsp
    sysretq

.Lsyscall_thread_join:
    mov %rdi, mort64_join_tid(%rip)
    mov %rsi, mort64_join_status(%rip)
    mov %rsp, mort64_yield_rsp(%rip)
    mov %rcx, mort64_yield_rip(%rip)
    mov %r11, mort64_yield_rflags(%rip)
    mov %rbx, mort64_yield_rbx(%rip)
    mov %rbp, mort64_yield_rbp(%rip)
    mov %r12, mort64_yield_r12(%rip)
    mov %r13, mort64_yield_r13(%rip)
    mov %r14, mort64_yield_r14(%rip)
    mov %r15, mort64_yield_r15(%rip)
    mov mort64_kernel_rsp(%rip), %rsp
    mov mort64_join_tid(%rip), %rdi
    mov mort64_join_status(%rip), %rsi
    cld
    sub $8, %rsp
    call mort_on_thread_join64
    add $8, %rsp
    test %rax, %rax
    jg .Lsave_blocked_context
    jmp .Lfutex_wait_error

.Lsyscall_poll_wait:
    mov %rdi, mort64_pollfds(%rip)
    mov %rsi, mort64_poll_count(%rip)
    mov %rdx, mort64_poll_timeout(%rip)
    mov %rsp, mort64_yield_rsp(%rip)
    mov %rcx, mort64_yield_rip(%rip)
    mov %r11, mort64_yield_rflags(%rip)
    mov %rbx, mort64_yield_rbx(%rip)
    mov %rbp, mort64_yield_rbp(%rip)
    mov %r12, mort64_yield_r12(%rip)
    mov %r13, mort64_yield_r13(%rip)
    mov %r14, mort64_yield_r14(%rip)
    mov %r15, mort64_yield_r15(%rip)
    mov mort64_kernel_rsp(%rip), %rsp
    mov mort64_pollfds(%rip), %rdi
    mov mort64_poll_count(%rip), %rsi
    mov mort64_poll_timeout(%rip), %rdx
    cld
    sub $8, %rsp
    call mort_on_poll_wait64
    add $8, %rsp
    test %rax, %rax
    jns .Lsave_blocked_context

    /* Bit 63 marks a direct return; bit 62 distinguishes an errno. */
.Lwait_direct_result:
    bt $62, %rax
    jc .Lpoll_wait_direct_error
    btr $63, %rax
    jmp .Lpoll_wait_direct_return
.Lpoll_wait_direct_error:
    and $0xFFF, %eax
    neg %rax
.Lpoll_wait_direct_return:
    mov mort64_yield_rbx(%rip), %rbx
    mov mort64_yield_rbp(%rip), %rbp
    mov mort64_yield_r12(%rip), %r12
    mov mort64_yield_r13(%rip), %r13
    mov mort64_yield_r14(%rip), %r14
    mov mort64_yield_r15(%rip), %r15
    mov mort64_yield_rip(%rip), %rcx
    mov mort64_yield_rflags(%rip), %r11
    mov mort64_yield_rsp(%rip), %rsp
    sysretq

.Lsyscall_epoll_wait:
    mov %rdi, mort64_epoll_descriptor(%rip)
    mov %rsi, mort64_epoll_events(%rip)
    mov %rdx, mort64_epoll_maxevents(%rip)
    mov %r10, mort64_epoll_timeout(%rip)
    mov %rsp, mort64_yield_rsp(%rip)
    mov %rcx, mort64_yield_rip(%rip)
    mov %r11, mort64_yield_rflags(%rip)
    mov %rbx, mort64_yield_rbx(%rip)
    mov %rbp, mort64_yield_rbp(%rip)
    mov %r12, mort64_yield_r12(%rip)
    mov %r13, mort64_yield_r13(%rip)
    mov %r14, mort64_yield_r14(%rip)
    mov %r15, mort64_yield_r15(%rip)
    mov mort64_kernel_rsp(%rip), %rsp
    mov mort64_epoll_descriptor(%rip), %rdi
    mov mort64_epoll_events(%rip), %rsi
    mov mort64_epoll_maxevents(%rip), %rdx
    mov mort64_epoll_timeout(%rip), %rcx
    cld
    sub $8, %rsp
    call mort_on_epoll_wait64
    add $8, %rsp
    test %rax, %rax
    jns .Lsave_blocked_context
    jmp .Lwait_direct_result

.Lsyscall_exit:
    /* rdi already contains the userspace exit status. */
    mov %rsp, mort64_user_rsp(%rip)
    mov mort64_kernel_rsp(%rip), %rsp
    sub $8, %rsp
    call mort_on_user_exit64
    add $8, %rsp
    mov mort64_kernel_cr3(%rip), %rax
    mov %rax, %cr3
    pop %r15
    pop %r14
    pop %r13
    pop %r12
    pop %rbp
    pop %rbx
    ret
.size mort64_syscall_entry, . - mort64_syscall_entry

/*
 * Exception frame after the per-vector stub:
 *   vector, error, RIP, CS, RFLAGS, [RSP, SS on privilege change]
 */
.type mort64_exception_common, @function
mort64_exception_common:
    cld
    push %rax
    push %rbx
    push %rcx
    push %rdx
    push %rbp
    push %rdi
    push %rsi
    push %r8
    push %r9
    push %r10
    push %r11
    push %r12
    push %r13
    push %r14
    push %r15
    mov %rsp, %r12
    cmpq $32, 120(%r12)
    je .Ltimer_interrupt
    mov 120(%r12), %rdi             /* vector */
    mov 128(%r12), %rsi             /* error */
    mov 136(%r12), %rdx             /* RIP */
    mov 144(%r12), %rcx             /* CS */
    and $-16, %rsp
    call mort_on_exception64
    cmp $1, %rax
    je .Lexception_abort_user
.Lexception_restore:
    mov %r12, %rsp
    pop %r15
    pop %r14
    pop %r13
    pop %r12
    pop %r11
    pop %r10
    pop %r9
    pop %r8
    pop %rsi
    pop %rdi
    pop %rbp
    pop %rdx
    pop %rcx
    pop %rbx
    pop %rax
    add $16, %rsp
    iretq

.Ltimer_interrupt:
    mov 144(%r12), %rdi             /* interrupted CS */
    and $-16, %rsp
    call mort_on_timer_tick64
    mov %rax, %r13                  /* zero or process context */
    mov $0x20, %al
    out %al, $0x20                  /* master PIC EOI */
    test %r13, %r13
    jz .Lexception_restore

    /* Copy the complete user interrupt frame into the selected context. */
    mov 0(%r12), %rdx
    mov %rdx, 0(%r13)               /* R15 */
    mov 8(%r12), %rdx
    mov %rdx, 8(%r13)               /* R14 */
    mov 16(%r12), %rdx
    mov %rdx, 16(%r13)              /* R13 */
    mov 24(%r12), %rdx
    mov %rdx, 24(%r13)              /* R12 */
    mov 32(%r12), %rdx
    mov %rdx, 32(%r13)              /* R11 */
    mov 40(%r12), %rdx
    mov %rdx, 40(%r13)              /* R10 */
    mov 48(%r12), %rdx
    mov %rdx, 48(%r13)              /* R9 */
    mov 56(%r12), %rdx
    mov %rdx, 56(%r13)              /* R8 */
    mov 64(%r12), %rdx
    mov %rdx, 64(%r13)              /* RSI */
    mov 72(%r12), %rdx
    mov %rdx, 72(%r13)              /* RDI */
    mov 80(%r12), %rdx
    mov %rdx, 80(%r13)              /* RBP */
    mov 88(%r12), %rdx
    mov %rdx, 88(%r13)              /* RDX */
    mov 96(%r12), %rdx
    mov %rdx, 96(%r13)              /* RCX */
    mov 104(%r12), %rdx
    mov %rdx, 104(%r13)             /* RBX */
    mov 112(%r12), %rdx
    mov %rdx, 112(%r13)             /* RAX */
    mov 136(%r12), %rdx
    mov %rdx, 120(%r13)             /* RIP */
    mov 152(%r12), %rdx
    mov %rdx, 128(%r13)             /* RFLAGS */
    mov 160(%r12), %rdx
    mov %rdx, 136(%r13)             /* RSP */
    jmp .Lexception_abort_user

.Lexception_abort_user:
    /*
     * A user fault terminates the current process. Discard the interrupt frame,
     * restore the kernel page root and the suspended mort64_enter_user frame,
     * then return to Mort policy code.
     */
    mov mort64_kernel_cr3(%rip), %rax
    mov %rax, %cr3
    mov mort64_kernel_rsp(%rip), %rsp
    pop %r15
    pop %r14
    pop %r13
    pop %r12
    pop %rbp
    pop %rbx
    ret
.size mort64_exception_common, . - mort64_exception_common

.macro ISR_NO_ERROR number
.global mort64_isr\number
mort64_isr\number:
    pushq $0
    pushq $\number
    jmp mort64_exception_common
.endm

.macro ISR_ERROR number
.global mort64_isr\number
mort64_isr\number:
    pushq $\number
    jmp mort64_exception_common
.endm

ISR_NO_ERROR 0
ISR_NO_ERROR 1
ISR_NO_ERROR 2
ISR_NO_ERROR 3
ISR_NO_ERROR 4
ISR_NO_ERROR 5
ISR_NO_ERROR 6
ISR_NO_ERROR 7
ISR_ERROR    8
ISR_NO_ERROR 9
ISR_ERROR    10
ISR_ERROR    11
ISR_ERROR    12
ISR_ERROR    13
ISR_ERROR    14
ISR_NO_ERROR 15
ISR_NO_ERROR 16
ISR_ERROR    17
ISR_NO_ERROR 18
ISR_NO_ERROR 19
ISR_NO_ERROR 20
ISR_ERROR    21
ISR_NO_ERROR 22
ISR_NO_ERROR 23
ISR_NO_ERROR 24
ISR_NO_ERROR 25
ISR_NO_ERROR 26
ISR_NO_ERROR 27
ISR_NO_ERROR 28
ISR_ERROR    29
ISR_ERROR    30
ISR_NO_ERROR 31

.global mort64_irq0
mort64_irq0:
    pushq $0
    pushq $32
    jmp mort64_exception_common

.section .rodata
.align 8
mort64_exception_stub_table:
    .quad mort64_isr0, mort64_isr1, mort64_isr2, mort64_isr3
    .quad mort64_isr4, mort64_isr5, mort64_isr6, mort64_isr7
    .quad mort64_isr8, mort64_isr9, mort64_isr10, mort64_isr11
    .quad mort64_isr12, mort64_isr13, mort64_isr14, mort64_isr15
    .quad mort64_isr16, mort64_isr17, mort64_isr18, mort64_isr19
    .quad mort64_isr20, mort64_isr21, mort64_isr22, mort64_isr23
    .quad mort64_isr24, mort64_isr25, mort64_isr26, mort64_isr27
    .quad mort64_isr28, mort64_isr29, mort64_isr30, mort64_isr31

.align 16
mort64_gdt:
    .quad 0x0000000000000000        /* 0x00 null */
    .quad 0x00AF9A000000FFFF        /* 0x08 ring-0 64-bit code */
    .quad 0x00CF92000000FFFF        /* 0x10 ring-0 data */
    .quad 0x00CFF2000000FFFF        /* 0x18 ring-3 data */
    .quad 0x00AFFA000000FFFF        /* 0x20 ring-3 64-bit code */
mort64_tss_descriptor:
    .quad 0
    .quad 0
mort64_gdt_end:

mort64_gdt_pointer:
    .word mort64_gdt_end - mort64_gdt - 1
    .quad mort64_gdt

mort64_idt_pointer:
    .word (256 * 16) - 1
    .quad mort64_idt

.section .bss
.align 16
mort64_tss:
    .skip 104

.align 16
mort64_idt:
    .skip 256 * 16

.align 8
mort64_kernel_rsp:
    .quad 0
mort64_user_rsp:
    .quad 0
mort64_kernel_cr3:
    .quad 0
mort64_resume_context:
    .quad 0
mort64_yield_rsp:
    .quad 0
mort64_yield_rip:
    .quad 0
mort64_yield_rflags:
    .quad 0
mort64_yield_rbx:
    .quad 0
mort64_yield_rbp:
    .quad 0
mort64_yield_r12:
    .quad 0
mort64_yield_r13:
    .quad 0
mort64_yield_r14:
    .quad 0
mort64_yield_r15:
    .quad 0
mort64_futex_address:
    .quad 0
mort64_futex_expected:
    .quad 0
mort64_futex_timeout:
    .quad 0
mort64_join_tid:
    .quad 0
mort64_join_status:
    .quad 0
mort64_pollfds:
    .quad 0
mort64_poll_count:
    .quad 0
mort64_poll_timeout:
    .quad 0
mort64_epoll_descriptor:
    .quad 0
mort64_epoll_events:
    .quad 0
mort64_epoll_maxevents:
    .quad 0
mort64_epoll_timeout:
    .quad 0
