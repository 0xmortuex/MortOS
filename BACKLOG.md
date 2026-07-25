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
- [ ] `docs/memory-map.md` — a single table of every fixed address the kernel uses (payload load address, the user ELF window at `0x01000000`, heap base/cap, stack pages, the mmap arena), each row citing the source line that defines it.
- [ ] `docs/shell.md` — a reference table of the built-in shell commands (read them out of `kmain.mx`), one line of behavior each.
- [ ] `docs/networking.md` — the mortnet layers (RTL8139 → ARP → IPv4 → UDP → DHCP → DNS → TCP → HTTP) and which `net/*.mx` file implements each.
- [ ] README: a "build and boot it yourself" quickstart — the real `build.py` subcommands and QEMU invocation, with the expected first lines of serial output. Verify command names against the actual `build.py`.

## Doc quality
- [ ] Audit `README.md` and `docs/` for claims that have drifted from the current source (feature list vs. what is actually implemented) and correct them, citing the source for each fix.
