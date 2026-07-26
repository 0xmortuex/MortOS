# MORT OS — Physical Memory Map

MORT OS runs in 32-bit protected mode with no paging set up anywhere in the
boot path (`boot.s`, `idt.s` never touch CR0's PG bit or CR3), so every
address below is a plain physical address — exactly what a Mort
`*((addr) as *T)` load or store touches on real hardware or under QEMU.
There is no MMU, no virtual memory, and no per-process address space:
the kernel and the one program it can run at a time share this one map.

Addresses marked **fixed** are hard-coded integer literals in the source.
Addresses marked **dynamic** are read from the multiboot info struct at
boot and vary by machine/bootloader.

| Address | Size | Name | Kind | Defined at |
|---|---|---|---|---|
| `0x00100000` (1 MiB) | kernel image (`.text`/`.rodata`/`.data`/`.bss`) | kernel load address | fixed | `linker.ld:8` (`. = 1M;`) |
| `0x000B8000` | 80×25 cells, 2 bytes each | VGA text-mode buffer | fixed | `kmain.mx:500`, `kmain.mx:579-586` |
| *(read from multiboot info)* | `width × height × 4` bytes | linear framebuffer base (`g_fb`) | dynamic | `kmain.mx:43`, `kmain.mx:350` (loaded from multiboot info offset 88 in `fb_init`, `kmain.mx:341-353`) |
| `0x00800000` (8 MiB) | 512 B | `SECBUF` — single-sector disk scratch | fixed | `kmain.mx:1252`, used e.g. `kmain.mx:1694`, `1708`, `1712`, `1723` |
| `0x00801000` | 4608 B (9 sectors) | `TABCACHE` — in-RAM MortFS superblock + file table | fixed | `kmain.mx:1253`, `1257` (`fs_entry_addr`), read at `kmain.mx:1302`, `1307` |
| `0x00810000` | 64 KiB | `FILEBUF` — whole-file read buffer (`cat`/`run`/`exec`) | fixed | `kmain.mx:1254`, filled by `fs_read_file` at `kmain.mx:1672`, read at `kmain.mx:909`, `1913`, `2275`, `2686` |
| `0x009F0000` | 4 B | syscall number (program → kernel) | fixed | `kmain.mx:1778`, read at `kmain.mx:1861` |
| `0x009F0004` | 4 B | syscall arg0 | fixed | `kmain.mx:1778`, read at `kmain.mx:1863`, `1869` |
| `0x009F000C` | 4 B | syscall return value (kernel → program) | fixed | `kmain.mx:1779`, written at `kmain.mx:1873`, `1878` |
| `0x009F0010` | 4 B | loaded program's entry address (kernel-internal) | fixed | `kmain.mx:1779`, written at `kmain.mx:1916`, called through at `kmain.mx:1887` (`exec_enter`) |
| `0x009F0100` | 120 usable bytes + NUL | syscall #4 input line buffer, filled by `read_line` | fixed | `kmain.mx:1805-1807`, returned at `kmain.mx:1878` |
| `0x00A00000` (10 MiB) | 64 KiB (zeroed then filled) | program load base — where `exec <name>` copies a flat binary and calls into it | fixed | `kmain.mx:1775`, `1890-1919`; also `programs/prog.ld:4` (`. = 0x00A00000;`) on the program-build side |
| `0x01000000` (16 MiB) | up to `top - base` | kernel heap base (`g_heap_base`), first byte handed out by `kmalloc` | fixed | `kmain.mx:1043`, in `heap_init` (`kmain.mx:1041-1059`) |
| `0x04000000` (64 MiB) | — | heap top **fallback**, used only if the multiboot mem-lower/upper flag (bit 0) is absent | fixed | `kmain.mx:1044` |
| *(computed)* | — | heap top in the common case: `0x00100000 + mem_upper_kib * 1024`, clamped to `0x20000000` (512 MiB) if `mem_upper` looks absurd | dynamic | `kmain.mx:1046-1051` |

## Notes

- **The boot stack** is a fixed-size (16 KiB) `.bss` region (`boot.s:33-37`,
  `stack_bottom`/`stack_top`), but its address is chosen by the linker, not a
  literal in the source, so it has no fixed numeric address to list above.
  There is exactly one stack: the kernel and every `exec`'d program run on it
  — `exec_enter` (`kmain.mx:1886-1888`) does a plain `call`, not a stack
  switch, so a program that overflows the stack corrupts kernel state.
- **Gaps are deliberate slack**, not accidents: `TABCACHE` could grow to 16
  sectors without touching `FILEBUF`, and `FILEBUF` sits on a clean 64 KiB
  boundary. See `docs/fs-design.md` section 3 for the disk-buffer layout in
  more detail (superblock/file-table format, why 8 MiB was chosen as the
  buffer region).
- **Nothing between the syscall mailbox and the heap overlaps**: the mailbox
  and its 121-byte input buffer (120 chars + NUL, capped at `kmain.mx:1840`)
  span `0x009F0000`–`0x009F0179`, the program area spans
  `0x00A00000`–`0x00A10000`, and the heap starts at `0x01000000` — well above
  both, per the `heap_init` comment "above the program load area"
  (`kmain.mx:1035`, `1043`).
- The colored `0x00RRGGBB` values used throughout the framebuffer renderer
  (e.g. `kmain.mx:401-416`) are pixel colors, not memory addresses, and are
  intentionally left out of this table.
