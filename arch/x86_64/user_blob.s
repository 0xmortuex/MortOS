/* Embedded ELF64 userspace executables; the Mort kernel parses and loads them. */

.section .rodata.user_image, "a", @progbits
.align 16
.global mort64_probe_image_blob
mort64_probe_image_blob:
.incbin "build/x86_64/user_probe.elf"
.global mort64_probe_image_end
mort64_probe_image_end:

.align 16
.global mort64_isolation_image_blob
mort64_isolation_image_blob:
.incbin "build/x86_64/user_isolation.elf"
.global mort64_isolation_image_end
mort64_isolation_image_end:

.align 16
.global mort64_survivor_image_blob
mort64_survivor_image_blob:
.incbin "build/x86_64/user_survivor.elf"
.global mort64_survivor_image_end
mort64_survivor_image_end:

.section .text.user_image, "ax", @progbits
.global mort64_probe_image
.type mort64_probe_image, @function
mort64_probe_image:
    lea mort64_probe_image_blob(%rip), %rax
    ret

.global mort64_probe_image_size
.type mort64_probe_image_size, @function
mort64_probe_image_size:
    mov $(mort64_probe_image_end - mort64_probe_image_blob), %rax
    ret

.global mort64_isolation_image
.type mort64_isolation_image, @function
mort64_isolation_image:
    lea mort64_isolation_image_blob(%rip), %rax
    ret

.global mort64_isolation_image_size
.type mort64_isolation_image_size, @function
mort64_isolation_image_size:
    mov $(mort64_isolation_image_end - mort64_isolation_image_blob), %rax
    ret

.global mort64_survivor_image
.type mort64_survivor_image, @function
mort64_survivor_image:
    lea mort64_survivor_image_blob(%rip), %rax
    ret

.global mort64_survivor_image_size
.type mort64_survivor_image_size, @function
mort64_survivor_image_size:
    mov $(mort64_survivor_image_end - mort64_survivor_image_blob), %rax
    ret
