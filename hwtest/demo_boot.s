/* hwtest/demo_boot.s — a minimal multiboot boot stub for the E1000 driver demo.
 *
 * Not part of the OS. Where the real boot.s reloads the GDT, remaps the PIC and
 * installs the IDT (kernel_setup, idt.s), this stub does the bare minimum: it
 * carries a multiboot header so `qemu-system-i386 -kernel` loads us at 1 MB in
 * flat protected mode, sets up a stack, and calls the Mort demo entry
 * (mort_kmain). The demo takes no interrupts (the E1000 driver masks them and we
 * never `sti`), so no IDT is needed. */

.set MB_MAGIC, 0x1BADB002
.set MB_FLAGS, 0x00000000
.set MB_CHECK, -(MB_MAGIC + MB_FLAGS)

.section .multiboot, "a", @progbits
.align 4
.long MB_MAGIC
.long MB_FLAGS
.long MB_CHECK

.section .bss
.align 16
stack_bottom:
.skip 16384
stack_top:

.section .text
.global _start
.type _start, @function
_start:
    mov $stack_top, %esp
    push %ebx                     /* multiboot info ptr -> kmain arg */
    call mort_kmain
    cli
.Lhang:
    hlt
    jmp .Lhang
.size _start, . - _start
