/* First instructions in the genuine ELF64 payload. */

.section .text.entry, "ax", @progbits
.code64
.global _payload_start
.type _payload_start, @function
_payload_start:
    mov $0x10, %ax
    mov %ax, %ds
    mov %ax, %es
    mov %ax, %ss
    xor %ax, %ax
    mov %ax, %fs
    mov %ax, %gs

    /*
     * The bootstrap stack lives below 2 MiB and remains identity-mapped.
     * RSP's upper half is already zero because the transition assigned ESP.
     */
    and $-16, %rsp
    xor %rbp, %rbp
    mov %esi, %edi                  /* System V arg 1: Multiboot info pointer */
    call mort_kmain64
.Lhalt:
    cli
    hlt
    jmp .Lhalt
.size _payload_start, . - _payload_start
