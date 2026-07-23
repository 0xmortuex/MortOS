/*
 * MORT OS x86-64 bootstrap.
 *
 * Multiboot enters in 32-bit protected mode. This stub verifies that the CPU
 * supports long mode, builds a temporary identity map for the first GiB,
 * enables PAE + long mode + paging, and jumps to 64-bit Mort code.
 *
 * This is intentionally a parallel boot path. The existing 32-bit desktop
 * remains bootable while its drivers and services are migrated.
 */

.set MB_ALIGN, 1 << 0
.set MB_MEMINFO, 1 << 1
.set MB_FLAGS, MB_ALIGN | MB_MEMINFO
.set MB_MAGIC, 0x1BADB002
.set MB_CHECK, -(MB_MAGIC + MB_FLAGS)

.section .multiboot, "a", @progbits
.align 4
.long MB_MAGIC
.long MB_FLAGS
.long MB_CHECK

.section .text
.code32
.global _start64
.type _start64, @function
_start64:
    cli
    mov $bootstrap_stack_top, %esp
    mov %ebx, %esi                  /* preserve Multiboot information pointer */

    /* CPUID extended leaf 0x80000001, EDX bit 29 = long-mode support. */
    mov $0x80000000, %eax
    cpuid
    cmp $0x80000001, %eax
    jb .Lno_long_mode
    mov $0x80000001, %eax
    cpuid
    test $(1 << 29), %edx
    jz .Lno_long_mode

    /* PML4[0] -> PDPT[0] -> a page directory of 512 x 2 MiB pages. */
    mov $pml4_table, %edi
    xor %eax, %eax
    mov $(4096 * 3 / 4), %ecx
    rep stosl

    mov $pdpt_table, %eax
    or $0x03, %eax
    mov %eax, pml4_table

    mov $pd_table, %eax
    or $0x03, %eax
    mov %eax, pdpt_table

    mov $pd_table, %edi
    xor %ebx, %ebx
    mov $512, %ecx
.Lmap_2m_page:
    mov %ebx, %eax
    or $0x83, %eax                  /* present | writable | 2 MiB page */
    mov %eax, (%edi)
    movl $0, 4(%edi)
    add $0x200000, %ebx
    add $8, %edi
    loop .Lmap_2m_page

    mov %cr4, %eax
    or $(1 << 5), %eax              /* CR4.PAE */
    mov %eax, %cr4

    mov $pml4_table, %eax
    mov %eax, %cr3

    mov $0xC0000080, %ecx           /* IA32_EFER */
    rdmsr
    or $(1 << 8), %eax              /* EFER.LME */
    wrmsr

    lgdt gdt64_pointer
    mov %cr0, %eax
    or $(1 << 31), %eax             /* CR0.PG; PE is already set */
    mov %eax, %cr0
    /* The ELF64 payload is linked and embedded at this fixed physical base. */
    ljmp $0x08, $0x00200000

.Lno_long_mode:
    mov $no_long_mode_message, %esi
    call serial_write32
.Lhalt32:
    hlt
    jmp .Lhalt32

/* Tiny 32-bit serial error path; successful output is handled by Mort code. */
serial_write32:
    mov $0x3F9, %dx
    xor %eax, %eax
    out %al, %dx
    mov $0x3FB, %dx
    mov $0x80, %al
    out %al, %dx
    mov $0x3F8, %dx
    mov $0x03, %al
    out %al, %dx
    mov $0x3F9, %dx
    xor %eax, %eax
    out %al, %dx
    mov $0x3FB, %dx
    mov $0x03, %al
    out %al, %dx
.Lserial_next32:
    lodsb
    test %al, %al
    jz .Lserial_done32
    mov %al, %cl
.Lserial_wait32:
    mov $0x3FD, %dx
    in %dx, %al
    test $0x20, %al
    jz .Lserial_wait32
    mov $0x3F8, %dx
    mov %cl, %al
    out %al, %dx
    jmp .Lserial_next32
.Lserial_done32:
    ret

.size _start64, . - _start64

.section .rodata
no_long_mode_message:
    .asciz "MORT64 ERROR: this CPU does not support x86-64 long mode\r\n"

.align 8
gdt64:
    .quad 0x0000000000000000        /* null */
    .quad 0x00AF9A000000FFFF        /* 0x08: 64-bit kernel code */
    .quad 0x00CF92000000FFFF        /* 0x10: kernel data */
gdt64_end:

gdt64_pointer:
    .word gdt64_end - gdt64 - 1
    .long gdt64

.section .bss
.align 4096
pml4_table:
    .skip 4096
pdpt_table:
    .skip 4096
pd_table:
    .skip 4096

.align 16
bootstrap_stack_bottom:
    .skip 32768
bootstrap_stack_top:

/* Filled by build64 after the genuine ELF64 payload has been linked. */
.section .payload, "a", @progbits
.incbin "build/x86_64/payload.bin"
