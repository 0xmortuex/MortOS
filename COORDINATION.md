# Parallel-agent coordination (Codex ↔ Claude)

Two agents build MORT OS in parallel. This file is the shared, durable record of
who owns what, so we never step on each other. (We can't message each other
directly; we coordinate through git branches + this file + the user relaying.)

## Branch ownership

| Branch | Owner | Contents |
|--------|-------|----------|
| `settings`, `main` | **Codex** | Settings, Vex browser, USB/Bluetooth, the desktop |
| `claude-hardware` | **Claude** | New hardware drivers (new files only) |
| `claude-shell` | **Claude** | Shell features + `mpkg` (new files + surgical shell hooks) |

**Rule of engagement:** Claude only adds NEW files (`net/e1000.mx`, `net/ahci.mx`,
`net/hda.mx`, `net/acpi.mx`, `net/mpkg.mx`) plus small, additive hooks in
`kmain.mx` (shell dispatch + a Tab-completion branch). Claude never edits Codex's
files (`net/browser*.mx`, `net/settings.mx`, `net/hci_usb.mx`, `net/hardware.mx`,
the desktop). So the merges are additive and conflict-free.

## Ready to merge from Claude (all verified in QEMU)

**`claude-hardware`** — 4 drivers, each with a `hwtest/` verification harness and
integration hooks documented in `hwtest/README.md`. Each is inert until Codex
calls its `_init()` from `kmain.mx`:
- `e1000_init()` (Intel E1000 NIC), `ahci_init()` (SATA disk read),
  `hda_init()` (HD Audio), `acpi_init()` + `acpi_poweroff()` (ACPI power).
- See the per-driver status-globals table in `hwtest/README.md`.

**`claude-shell`** — Tab completion + `history` command + **`mpkg`** (the package
manager: `update`/`list`/`search`/`install`/`remove`, self-contained TCP client,
verified fetching + installing from the mort-repo server). No hooks needed from
Codex; it's wired into the shell already.

## Bugs Claude found in Codex's code (please patch)

Reported from a review of the browser/USB commits. Two are remote memory
corruption (any `http://` page can trigger):
1. **HIGH** `net/browser_net.mx` ~409/416 — chunked decoder: chunk size uncapped,
   `read + size` wraps u32 past the bound → ~4 GB OOB write.
2. **HIGH** `net/browser_net.mx` ~211-219 — TCP receive: IP total-length
   underflow + cap wrap → OOB write.
3. **MED** `net/browser.mx` ~179/308 — history index loaded from disk isn't
   bounds-checked → OOB read on Back.
4. **LOW** `net/hci_usb.mx` ~427 — config-descriptor walk missing `pos+size ≤
   wanted` → small OOB read from a malicious USB device.

(Claude's `net/mpkg.mx` TCP receive path already guards the same length-subtraction
and caps every buffer copy — a reference for the fix pattern.)

## Note on the shared Mort compiler

`../Mort` is edited live (Codex's v0.10+ work), which intermittently breaks builds
for whoever is compiling mid-edit. Claude builds against a pinned clone of the last
release (`MORT_HOME=<clone>`) to stay insulated. If a build fails with a compiler
crash rather than a source error, that's the shared-compiler churn, not the code.
