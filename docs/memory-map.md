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
| `0x000B8000` | 80×25 cells, 2 bytes each | VGA text-mode buffer | fixed | `kmain.mx:747` (`put_index`), `kmain.mx:810-817` (`scroll_up`) |
| *(read from multiboot info)* | `width × height × 4` bytes | linear framebuffer base (`g_fb`) | dynamic | `kmain.mx:63`, `kmain.mx:357` (loaded from multiboot info offset 88 in `fb_init`, `kmain.mx:347-366`) |
| `0x00800000` (8 MiB) | 512 B | `SECBUF` — single-sector disk scratch, also what `exec` reads through (`fs_read_at`, `kmain.mx:2027-2056`, called from `exec_file` at `kmain.mx:2674`) | fixed | `kmain.mx:1508` (buffer-layout comment), used e.g. `kmain.mx:1984`, `1998`, `2002`, `2041` |
| `0x00801000` | 4608 B (9 sectors) | `TABCACHE` — in-RAM MortFS superblock + file table | fixed | `kmain.mx:1509`, `1513-1515` (`fs_entry_addr`), read at `kmain.mx:1558`, `1564` |
| `0x00810000` | 64 KiB | `FILEBUF` — whole-file read buffer (`cat`/`run`) | fixed | `kmain.mx:1510`, filled by `fs_read_file` at `kmain.mx:1950-1966`, read by `cat` at `kmain.mx:3083`/`3089` and `run` at `kmain.mx:1140`/`1146` |
| `0x009F0000` | 4 B | syscall number (program → kernel) | fixed | `kmain.mx:2156` (mailbox comment), read at `kmain.mx:2575` |
| `0x009F0004` | 4 B | syscall arg0 | fixed | `kmain.mx:2156`, read at `kmain.mx:2576` |
| `0x009F000C` | 4 B | syscall return value (kernel → program) | fixed | `kmain.mx:2157`, written at `kmain.mx:2438` (`sys_ret`), called by `sys_fail` at `kmain.mx:2442` |
| `0x009F0010` | 4 B | loaded program's entry address (kernel-internal) | fixed | `kmain.mx:2157`, written at `kmain.mx:2680`, called through at `kmain.mx:2641` (`exec_enter`) |
| `0x009F0100` | 120 usable bytes + NUL | syscall #4 input line buffer, filled by `read_line` (echoes with no 80-column wrap check — see [`docs/programs.md`](programs.md#typing-a-long-answer-to-syscall-4-corrupts-the-row-below-it)) | fixed | `kmain.mx:2196-2243`, returned at `kmain.mx:2595` |
| `0x009F0008`, `0x009F0014`, `0x009F0018` | 4 B each | syscall arg1, arg2, arg3 | fixed | `docs/programs.md` |
| `0x009F001C`, `0x009F0020`, `0x009F0024` | 4 B each | saved kernel stack, returned status, status for the exit path (kernel-internal) | fixed | `exec_enter`, `proc_leave` |
| `0x009F0200` | 0x600 B | argc, 16 argv pointers, and the argument strings (from `0x009F0400`) | fixed | `args_setup` |
| `0x00A00000` (10 MiB) | 64 KiB (zeroed then filled) | program load base — where `exec <name>` copies a flat binary and calls into it | fixed | `kmain.mx:2647-2689` (`exec_file`); also `programs/prog.ld:5` (`. = 0x00A00000;`) on the program-build side |
| `0x00A10000` | 64 KiB, grows down from `0x00A20000` | program stack | fixed | `exec_enter` |
| `0x01000000` (16 MiB) | up to `top - base` | kernel heap base (`g_heap_base`), first byte handed out by `kmalloc` | fixed | `kmain.mx:1280`, in `heap_init` (`kmain.mx:1278-1296`) |
| `0x04000000` (64 MiB) | — | heap top **fallback**, used only if the multiboot mem-lower/upper flag (bit 0) is absent | fixed | `kmain.mx:1281` |
| *(computed)* | — | heap top in the common case: `0x00100000 + mem_upper_kib * 1024`, clamped to `0x20000000` (512 MiB) if `mem_upper` looks absurd | dynamic | `kmain.mx:1282-1289` |

## The kernel heap allocator (`kmalloc`/`kfree`)

The heap region above (`0x01000000` up to the computed top) isn't just a
range — it's carved into blocks by a first-fit allocator with block headers
(`kmain.mx:1268-1276`'s own header comment lays out the design; the code
below matches it exactly). Every block starts with an 8-byte header,
`[size: u32][used: u32]`, immediately followed by the payload; `kmalloc`
hands back `blk + 8`, i.e. the address right after the header.

- **`kmalloc(size)`** (`kmain.mx:1299-1332`) rounds `size` up to `need =
  (size + 8 + 7) & 0xFFFFFFF8` (header plus payload, 8-byte aligned), then
  scans every block from `g_heap_base` to the current break `g_heap_brk`
  looking for a free (`used == 0`) block whose `size` is at least `need`.
  A fitting block big enough to leave 16+ spare bytes is split in place
  (`kmain.mx:1311-1316`: the remainder becomes its own free block, the front
  part gets marked used); otherwise the whole block is handed out as-is. If
  no free block fits, `kmalloc` grows the heap by bumping `g_heap_brk` past
  a brand-new block (`kmain.mx:1324-1330`), returning `0` if that would
  cross `g_heap_end`.
- **`kfree(ptr)`** (`kmain.mx:1335-1355`) marks the block's `used` word `0`,
  then coalesces **forward only**: while the next block (by address) is
  before `g_heap_brk` and is also free, it's absorbed into the current
  block's `size` and the loop repeats, so a chain of consecutive free
  blocks merges into one. There is no backward pass — if the block
  immediately *before* the one just freed is already free, the two are
  never merged (that earlier block's own `kfree` call already finished its
  forward scan before this block existed as free), so first-fit can still
  see them as two separate candidates on the next `kmalloc`. This is a
  real, verifiable fragmentation gap in the allocator, not a hypothetical
  one.
- **`heap_used()`** (`kmain.mx:1358-1369`) walks the same block chain and
  sums the `size` of every block marked used — but has no caller anywhere
  in the repo (confirmed by grep across every `.mx` file). `mem`
  (`kmain.mx:1154-1179`, `docs/shell.md`) reports total RAM from the multiboot
  memory map, not heap usage; `heap_used` isn't wired into it or anywhere
  else.
- **`kmalloc`/`kfree` themselves have exactly one caller pair in the whole
  codebase: `memtest`** (`kmain.mx:1208-1258`, the `memtest` shell command).
  Nothing else in the kernel allocates from this heap — it's foundational
  infrastructure `heap_init`'s own comment describes as being for "the
  shell, the package manager, and the rest" (`kmain.mx:1271`), not yet
  used by any shipped feature. See `docs/shell.md`'s `memtest` row for what
  that command actually verifies — notably, its closing `kfree(b); kfree(c);`
  (`kmain.mx:1240-1241`) does run the forward-coalescing path described
  above, but `memtest` never asserts on the result afterward, so a
  coalescing bug that merges blocks into a wrong (but non-hanging) size
  would still print `PASS`.
- **The Machine stratum's "Heap used" reading displays `g_heap_brk -
  g_heap_base` directly, not `heap_used()`** — `ui_compose_machine()`
  (`ui/borehole.mx:1441-1453`, row at `ui/borehole.mx:1452-1453`) computes
  `(g_heap_brk - g_heap_base) / 1024` itself, rather than calling the
  actually-correct-for-this `heap_used()` above. (The Settings app this
  replaced showed the same raw `g_heap_brk` math as two separate fields,
  "Heap used" and "Heap allocated" — the Borehole rewrite deleted
  `net/settings.mx` along with the rest of that app and collapsed both into
  the single row above.) Since `g_heap_brk` is a high-water mark that only
  rises (never falls on `kfree`) and `memtest` is its only mover, tracing
  the exact byte math shows this reading is static in practice: `memtest`'s
  two allocations round up to 112 and 208 bytes
  (`(100+8+7)&0xFFFFFFF8` and `(200+8+7)&0xFFFFFFF8`, `kmain.mx:1217-1218`,
  `1303`), bumping `g_heap_brk` by 320 bytes total the first time `memtest`
  ever runs; its closing `kfree` calls (`kmain.mx:1240-1241`) forward-coalesce
  that same 320 bytes back into one free block, which every later `memtest`
  run reuses via first-fit (a 112-byte split then an exact 208-byte fit)
  with zero further growth. `320 / 1024` is `0` in this integer division, so
  the reading shows `0 KiB` before `memtest` has ever run and still `0 KiB`
  after — visibly unchanging regardless of the "live" label, since
  `memtest` is the only thing in the kernel that ever calls `kmalloc` (see
  the bullet above) and its own allocations never exceed the 320 bytes
  already accounted for above. See [`docs/settings.md`](settings.md) for
  the Machine stratum's other readings.

## Notes

- **The boot stack** is a fixed-size (16 KiB) `.bss` region (`boot.s:33-37`,
  `stack_bottom`/`stack_top`), but its address is chosen by the linker, not a
  literal in the source, so it has no fixed numeric address to list above.
  The kernel and an `exec`'d program do **not** share that stack:
  `exec_enter` (`kmain.mx:2640-2642`) saves the kernel's `%esp` to
  `0x009F001C`, switches `%esp` to `0x00A20000` — the top of the program
  stack row above — before the `call`, then restores the saved kernel
  `%esp` afterward, matching `docs/programs.md`'s own note that the program
  stack is "the program's own, not the kernel's". A program that overflows
  its 64 KiB stack downward runs into its own image/bss region
  (`0x00A00000`-`0x00A10000`), not kernel state.
- **Gaps are deliberate slack**, not accidents: `TABCACHE` could grow to 16
  sectors without touching `FILEBUF`, and `FILEBUF` sits on a clean 64 KiB
  boundary. See `docs/fs-design.md` section 3 for the disk-buffer layout in
  more detail (superblock/file-table format, why 8 MiB was chosen as the
  buffer region).
- **Nothing between the syscall mailbox and the heap overlaps**: the mailbox
  and its 121-byte input buffer (120 chars + NUL, capped at `kmain.mx:2229`)
  span `0x009F0000`–`0x009F0179`, the program area spans
  `0x00A00000`–`0x00A10000`, and the heap starts at `0x01000000` — well above
  both, per `heap_init`'s own "above the kernel/program area" /
  "above the program load area" comments (`kmain.mx:1272`, `1280`).
- The colored `0x00RRGGBB` values used throughout the framebuffer renderer
  (e.g. `kmain.mx:399-416`) are pixel colors, not memory addresses, and are
  intentionally left out of this table.
- **The linear framebuffer's base address and pitch are dynamic, but the
  interface drawn on it is laid out for exactly 1024x768**: `fb_init()` checks
  only the pixel format, and `ui_init()` then halts with an on-screen error
  for any other size. `ui_init()` also takes the first 3 MiB of the heap
  (1024x768x4, at `0x01000008` on a boot with no earlier `kmalloc`) as the
  back buffer. See [`docs/architecture.md`](architecture.md#the-borehole-interface).
