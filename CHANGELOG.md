# Changelog

Notable changes to MORT OS, newest first. `v1.0.0` and `borehole-gui` are git tags; earlier work
had no releases, so it is listed by date.

## Unreleased

### Added

- COM1 serial console: a 16550 UART driver at 115200 8N1 that mirrors console output and accepts
  shell input, a `serial` command reporting lost-byte counters, and `test_serial.py`.
- `build.py boot` boots headless with the shell on your terminal, on Linux and Windows.
  `build.py boot-check` builds, boots, and exits 0 once the shell prompt is up.
- `test_boot.py`: boot tests that script the shell over COM1 in lock-step, with a transcript per
  session.
- GitHub Actions CI on `ubuntu-latest` and `windows-latest`: builds from a clean checkout, runs
  every test harness, and uploads transcripts on failure.
- `build.py iso` and `run-iso` now work on Linux, with the system `xorriso` and Limine's host tool
  built with Zig.
- `CONTRIBUTING.md` and this changelog.

### Fixed

- `export` with no `=`, and `chmod` or `chown` with no path, now report their usage errors. They
  used to act on bytes left by the previous command, so `chmod 777` could change the last file
  named.
- A disk that is slow to finish a write no longer loses the file. The kernel waited a fixed number
  of status reads, which a busy host could outlast, and `write` then failed without saying so.

### Changed

- The Mort compiler is pinned to a commit (`MORT_COMMIT` in `build.py`) instead of following
  Mort's default branch. Limine and xorriso are pinned to commits too.

## `borehole-gui` (2026-11-08)

- Replaced the whole GUI with Borehole, a geological cross-section you drill through: the
  drill-site start screen, a shell gallery, Objects (MortFS as strata), core samples for files,
  and the Machine and Terminate strata with lock and sleep. Covered by `test_gfx.py`.

## `v1.0.0` (2026-11-07)

The state of the OS when it was first tagged:

- Mort kernel booted through Multiboot 1 or a Limine ISO, in 32-bit protected mode.
- Interrupt-driven PS/2 keyboard and PIT timer, and CPU exception reports.
- Shell with history, `$VAR` expansion, `$PATH` lookup and a working directory.
- MortFS v2 on an ATA PIO disk: directories, owners, modes, and persistence across reboots.
- Compiled Mort programs loaded from disk and run through `int 0x80` syscalls.
- Users, login, `su`, `sudo` and file permissions.
- The vendored mortnet stack: RTL8139, DHCP, TCP and an HTTP server.
- PCI discovery, UHCI USB enumeration, AC'97 audio and the PC speaker.
- A graphical framebuffer desktop, since replaced by Borehole.
