/* Flat 32-bit image at 1 MB; multiboot header first. Mirrors MORT OS's script. */
ENTRY(_start)

SECTIONS
{
    . = 1M;

    .multiboot : { KEEP(*(.multiboot)) }
    .text      : { *(.text*) }
    .rodata    : { *(.rodata*) }
    .data      : { *(.data*) }
    .bss       : { *(.bss*) *(COMMON) }

    /DISCARD/  : { *(.eh_frame*) *(.eh_frame_hdr) *(.note*) *(.comment) }
}
