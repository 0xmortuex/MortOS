/* Minimal multiboot1 stub for the mortnet M1 demo.
 *
 * QEMU's -kernel loader reads the header, drops us at 1 MB in 32-bit protected
 * mode with a flat GDT already in place, and jumps to _start. The RTL8139
 * transmit path is pure polling, so unlike full MORT OS this demo needs no
 * GDT/IDT of its own — we just set a stack and call the Mort kernel.
 */
.set MB_MAGIC, 0x1BADB002
.set MB_FLAGS, 0
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
    call mort_kmain
    cli
.Lhang:
    hlt
    jmp .Lhang
.size _start, . - _start
