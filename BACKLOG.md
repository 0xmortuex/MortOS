# Backlog

Real, finishable improvements — the daily agent picks ONE and ships it end-to-end.
Rules: check items off when done, add follow-ups you discover, never do two at once,
smallest reviewable change wins.

**Safety — read this first.** MORT OS is a from-scratch kernel whose behavior can
only be verified by **booting it in QEMU**, and the daily cloud agent has **no QEMU
and cannot build or boot the kernel**. So the agent works on **documentation and
non-behavioral text only** — `README.md`, files under `docs/`, and source code
*comments*. It must **not** change kernel logic (the behavior of any `*.mx` file),
`build.py` behavior, assembly (`*.s`), or linker scripts — those require a local
QEMU boot test that a human runs. Every factual claim in a doc must be grounded in
the actual source (cite `file:line`); if the only useful work would touch kernel
behavior, add a backlog item describing it and stop.

## Documentation
- [ ] `docs/architecture.md` — the boot chain (multiboot/Limine → 32-bit entry → long mode), the memory map, and the major subsystems (framebuffer, RTL8139 network stack, VexFS, scheduler, shell). Ground every claim in source with `file:line` citations.
- [x] `docs/memory-map.md` — a single table of every fixed address the kernel uses, each row citing the source line that defines it. Done 2026-07-26: kernel load (1 MiB), VGA buffer (`0xB8000`), disk buffers (SECBUF/TABCACHE/FILEBUF), syscall mailbox (`0x009F0000`-`0x009F0179`), program load base (`0x00A00000`, not `0x01000000` — that address is actually the heap base per `kmain.mx:1043`, so this item's own description had the wrong address; corrected in the doc), heap base/top. Framebuffer address is dynamic (read from multiboot info), noted as such rather than listed as fixed.
- [x] `docs/shell.md` — a reference table of the built-in shell commands (read them out of `kmain.mx`), one line of behavior each. Done 2026-07-25: every command in `run_command_impl` (`kmain.mx:2100`-`2602`), cited by line, plus `$VAR` expansion and command history.
- [ ] `docs/networking.md` — the mortnet layers (RTL8139 → ARP → IPv4 → UDP → DHCP → DNS → TCP → HTTP) and which `net/*.mx` file implements each.
- [ ] README: a "build and boot it yourself" quickstart — the real `build.py` subcommands and QEMU invocation, with the expected first lines of serial output. Verify command names against the actual `build.py`.

## Doc quality
- [ ] Audit `README.md` and `docs/` for claims that have drifted from the current source (feature list vs. what is actually implemented) and correct them, citing the source for each fix.
- [x] `docs/fs-design.md` opens with "Nothing here is implemented yet; this is the spec to implement from" (line 3), but MortFS is fully implemented and shipping (`kmain.mx` has `fs_init`/`fs_read_file`/etc., `docs/shell.md` documents `ls`/`cat`/`write`/`rm`/`run` as working commands). Done 2026-07-27: replaced the header with a "Status: implemented" note citing the real functions (`fs_init` `kmain.mx:1296`, `fs_create` `kmain.mx:1587`, `fs_read_file` `kmain.mx:1662`, `fs_remove` `kmain.mx:1732`, `ata_init`/`ata_read`/`ata_write` `kmain.mx:1175`-`1241`, `g_run_depth` guard `kmain.mx:40`/`895`) and flagging that Sections 0-5 are historical (drafting-time paths like `kernel/kmain.mx`/`kernel/mkfs.py`/`mort/typechecker.py` were not rewritten, only the header), Section 6 is the executed plan not a to-do, Section 7's non-goals are current limitations. Body sections 1-5 left untouched per the item's own scope.
- [ ] `docs/fs-design.md` sections 1 and 5.1 still say `kernel/kmain.mx` and `kernel/mkfs.py` — the real files are `kmain.mx` and `mkfs.py` at the repo root. Small mechanical path fix if anyone wants it (noted but left alone in the 2026-07-27 header pass to keep that change minimal and reviewable).
- [ ] `power`, `lock`, and `sleep` shell commands silently no-op in VGA text mode — `open_power_menu` (`kmain.mx:3145`), `open_lock` (`kmain.mx:3199`), and `open_sleep` (`kmain.mx:3229`) all `return` immediately `if !g_gfx`. Worth a doc note (or, as a code change for a human with a local QEMU boot test, a `no display` message instead of silent no-op).
