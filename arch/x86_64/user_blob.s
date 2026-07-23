/* Embedded ELF64 userspace executable; the Mort kernel parses and loads it. */

.section .rodata.user_image, "a", @progbits
.align 16
.global mort64_user_image_blob
mort64_user_image_blob:
.incbin "build/x86_64/user_probe.elf"
.global mort64_user_image_end
mort64_user_image_end:

.section .text.user_image, "ax", @progbits
.global mort64_user_image
.type mort64_user_image, @function
mort64_user_image:
    lea mort64_user_image_blob(%rip), %rax
    ret

.global mort64_user_image_size
.type mort64_user_image_size, @function
mort64_user_image_size:
    mov $(mort64_user_image_end - mort64_user_image_blob), %rax
    ret
