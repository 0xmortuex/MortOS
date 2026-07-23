OUTPUT_FORMAT(elf64-x86-64)
OUTPUT_ARCH(i386:x86-64)
ENTRY(_user_start)

SECTIONS
{
    . = 0x01000000;
    .text   : ALIGN(4K) { *(.text.entry) *(.text*) }
    .rodata : ALIGN(4K) { *(.rodata*) }
    .data   : ALIGN(4K) { *(.data*) *(.bss*) *(COMMON) BYTE(0) }
    .userfault 0x01010000 : ALIGN(4K) { *(.userfault) }

    /DISCARD/ : { *(.eh_frame*) *(.eh_frame_hdr) *(.note*) *(.comment) }
}
