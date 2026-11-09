/* Flat program image: everything at the fixed load base, Mort's main first.
 * The kernel enters at byte 0. */
ENTRY(mort_main)
SECTIONS {
    . = 0x00A00000;
    .text : {
        *(.text.mort_main)
        *(.text*)
    }
    .rodata : { *(.rodata*) }
    .data   : { *(.data*) }
    .bss    : { *(.bss*) *(COMMON) }
    _prog_end = .;
    /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
ASSERT(mort_main == 0x00A00000, "program entry is not at byte 0")
ASSERT(_prog_end <= 0x00A10000, "program image + bss exceeds the 64 KiB load area")
