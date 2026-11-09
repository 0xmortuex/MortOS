# Contributing to MORT OS

MORT OS is a 32-bit x86 kernel written in [Mort](https://github.com/0xmortuex/Mort). This guide
covers setup, tests, and what a change needs before it can be merged. For how the system works,
read [`ARCHITECTURE.md`](ARCHITECTURE.md). For what is missing, read [`ROADMAP.md`](ROADMAP.md).

## Set up

You need [uv](https://docs.astral.sh/uv/), git and QEMU (`qemu-system-i386`). The commands below
work on Linux and Windows. `run-iso` on Linux, and the ISO-based tests there, also need `xorriso`.

```bash
git clone https://github.com/0xmortuex/MortOS && cd MortOS
uv run --no-project --with ziglang --with cryptography python build.py boot
```

`boot` builds the kernel and boots it with the shell on your terminal, over COM1. `Ctrl+A` then
`X` quits QEMU.

### The Mort compiler

A clean checkout fetches the commit named by `MORT_COMMIT` in `build.py` into `.mort/`. If
`$MORT_HOME` is set, or a `../Mort` checkout exists next to this repo, the build uses that
instead and prints a note when it differs from the pin. To move to a newer compiler, change
`MORT_COMMIT` in its own commit, after the tests pass with that compiler.

## Run the tests

Prefix each command with `uv run --no-project --with ziglang --with cryptography`.

| Command | What it covers | Drives the kernel through |
|---|---|---|
| `python test_boot.py` | Boot, shell, files, persistence, programs, error paths, faults, power off | COM1, in lock-step |
| `python test.py smoke` | Boot and shell basics | PS/2 keys, VGA memory |
| `python test_fs.py` | Disk stack and persistence | PS/2 keys, VGA memory |
| `python test_exec.py` | Compiled programs | PS/2 keys, VGA memory |
| `python test_serial.py` | COM1 console, on the text and ISO paths | COM1 and the QEMU monitor |
| `python test_gfx.py` | The Borehole interface on the ISO path | PS/2 keys, screendumps |

Every harness boots the real kernel headless in QEMU, capped at `-m 256 -accel tcg,tb-size=32`.
Run one QEMU at a time on a machine with little memory.

`test_boot.py` accepts session names and `--no-build`, and writes a transcript per session to
`build/test-logs/boot/`. See [`docs/testing.md`](docs/testing.md).

GitHub Actions runs the build and every harness on `ubuntu-latest` and `windows-latest`
(`.github/workflows/ci.yml`) on each push and pull request, and can be started by hand. When a
run fails, its transcripts are uploaded as an artifact.

## Rules for changes

- **OS code stays in Mort.** New kernel code goes in `kmain.mx`, `net/` or `ui/`. The only
  non-Mort code in the image is `boot.s`, `idt.s` and `runtime.c`.
- **Tests first.** Add the check, show it failing, then make it pass. A bug fix comes with a
  regression test.
- **Never delete or weaken a test** to get a green run. If a test is wrong, say why in the commit.
- **Tests assert on real behaviour.** Never hardcode shell output in the kernel to satisfy a test.
- **Serial scripts run in lock-step.** Wait for the prompt after each command. The kernel's
  receive ring holds 512 bytes, and a longer burst can lose bytes. QEMU's stdio backend on Windows
  needs input paced byte by byte. See the serial notes in [`ARCHITECTURE.md`](ARCHITECTURE.md).
- **Diagnose crashes; don't retry them.** Use the QEMU monitor or the gdbstub (`-s`) to find the
  root cause, and add a regression test.
- **GUI changes require real screenshots.** Any change to the Borehole interface must include
  screenshots taken from a real QEMU boot, not mockups, and `test_gfx.py` must cover the change.
- Keep commits to one purpose each, and update the docs a change makes wrong.
- Add user-visible changes to [`CHANGELOG.md`](CHANGELOG.md) under `Unreleased`.
