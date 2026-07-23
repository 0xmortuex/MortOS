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
    pushq $0x2                      /* reserved RFLAGS bit; interrupts off */
    pushq $USER_CODE
    push %rdi
    iretq
.size mort64_enter_user, . - mort64_enter_user

.global mort64_resume_user
.type mort64_resume_user, @function
mort64_resume_user:
    /* rdi=saved cooperative context, rsi=process CR3 */
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

    mov 8(%rdi), %rcx              /* SYSRET RIP */
    mov 16(%rdi), %r11             /* SYSRET RFLAGS */
    mov 24(%rdi), %rbx
    mov 32(%rdi), %rbp
    mov 40(%rdi), %r12
    mov 48(%rdi), %r13
    mov 56(%rdi), %r14
    mov 64(%rdi), %r15
    mov 0(%rdi), %rsp
    xor %eax, %eax                 /* yield returns success */
    sysretq
.size mort64_resume_user, . - mort64_resume_user

.global mort64_flush_tlb
.type mort64_flush_tlb, @function
mort64_flush_tlb:
    mov %cr3, %rax
    mov %rax, %cr3
    ret
.size mort64_flush_tlb, . - mort64_flush_tlb

.type mort64_syscall_entry, @function
mort64_syscall_entry:
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
    /* System V call: dispatcher(number, arg0, arg1, arg2). */
    mov %rdx, %rcx
    mov %rsi, %rdx
    mov %rdi, %rsi
    mov %rax, %rdi
    sub $8, %rsp                    /* align before the System V call */
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
    mov mort64_yield_rsp(%rip), %rdx
    mov %rdx, 0(%rax)
    mov mort64_yield_rip(%rip), %rdx
    mov %rdx, 8(%rax)
    mov mort64_yield_rflags(%rip), %rdx
    mov %rdx, 16(%rax)
    mov mort64_yield_rbx(%rip), %rdx
    mov %rdx, 24(%rax)
    mov mort64_yield_rbp(%rip), %rdx
    mov %rdx, 32(%rax)
    mov mort64_yield_r12(%rip), %rdx
    mov %rdx, 40(%rax)
    mov mort64_yield_r13(%rip), %rdx
    mov %rdx, 48(%rax)
    mov mort64_yield_r14(%rip), %rdx
    mov %rdx, 56(%rax)
    mov mort64_yield_r15(%rip), %rdx
    mov %rdx, 64(%rax)
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
    mov 120(%r12), %rdi             /* vector */
    mov 128(%r12), %rsi             /* error */
    mov 136(%r12), %rdx             /* RIP */
    mov 144(%r12), %rcx             /* CS */
    and $-16, %rsp
    call mort_on_exception64
    cmp $1, %rax
    je .Lexception_abort_user
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
