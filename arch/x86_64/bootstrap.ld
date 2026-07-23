/*
 * QEMU's direct Multiboot loader requires an ELF32 container. This loader is
 * only the architectural trampoline; it embeds and enters the ELF64 payload.
 */
OUTPUT_FORMAT(elf32-i386)
OUTPUT_ARCH(i386)
ENTRY(_start64)

SECTIONS
{
    . = 1M;

    .multiboot : { KEEP(*(.multiboot)) }
    .text      : ALIGN(4K) { *(.text*) }
    .rodata    : ALIGN(4K) { *(.rodata*) }
    .data      : ALIGN(4K) { *(.data*) }
    .bss       : ALIGN(4K) { *(.bss*) *(COMMON) }

    . = 2M;
    .payload   : ALIGN(4K) { KEEP(*(.payload)) }

    /DISCARD/  : { *(.eh_frame*) *(.eh_frame_hdr) *(.note*) *(.comment) }
}
