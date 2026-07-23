/* Genuine ELF64 payload, embedded by the Multiboot bootstrap at 2 MiB. */
OUTPUT_FORMAT(elf64-x86-64)
OUTPUT_ARCH(i386:x86-64)
ENTRY(_payload_start)

SECTIONS
{
    . = 2M;

    .text      : ALIGN(4K) { *(.text.entry) *(.text*) }
    .rodata    : ALIGN(4K) { *(.rodata*) }
    /*
     * The ELF64 image is embedded as a flat payload, so materialize BSS as
     * zero bytes in the payload instead of relying on an ELF loader.
     */
    .data      : ALIGN(4K) { *(.data*) *(.bss*) *(COMMON) BYTE(0) }

    /DISCARD/  : { *(.eh_frame*) *(.eh_frame_hdr) *(.note*) *(.comment) }
}
