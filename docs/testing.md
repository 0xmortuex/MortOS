# Testing

MORT OS has no unit tests in the usual sense — nothing here can run outside a
booted kernel, since a from-scratch OS has no host runtime to link against.
All five test scripts instead boot the *real* kernel headless in QEMU and
drive it like a person would — typing on the emulated PS/2 keyboard through
QEMU's human monitor (`test_fs.py`, `test_exec.py`, the keyboard half of
`test_gfx.py`) or over a serial line (`test_boot.py`, `test_serial.py`) —
then reading assertions back out of guest video memory or the COM1 stream.
`test.py` is the shared harness the other five import; it has no tests of
its own beyond the `smoke` subcommand.

```bash
python test.py smoke      # boot + shell basics (text-mode -kernel path)
python test_boot.py       # exact COM1 assertions: boot, shell commands, persistence, exec, faults, a flaky disk
python test_fs.py         # the disk stack, incl. write-reboot-cat persistence
python test_exec.py       # build programs, seed, boot, exec, check syscall output
python test_gfx.py        # boot the ISO, drive the Borehole interface, assert on screendumps and guest memory
python test_serial.py     # the COM1 console itself: text/ISO shells, overruns, floods, PS/2 alongside serial
```

All six need `qemu-system-i386` on `PATH` (found via `build._find_qemu()`,
`build.py`); `test_boot.py`, `test_exec.py`, and `test_serial.py` also need
`pip install ziglang`, since each compiles the sample programs first
(`build._program_sources()`/`build.build_program()`). `test_gfx.py` and
`test_serial.py` also boot via `build.iso()`, which runs on Windows and
Linux. Linux needs `xorriso` installed; see the ISO note in
[`README.md`](../README.md#a-real-bootable-iso). CI runs every script on
`windows-latest` and `ubuntu-latest` from a clean checkout. None of the six
scripts touch files in the repo — scratch disk images and screendumps go to
the system temp dir (`tempfile.mkdtemp`).

## `test_boot.py`: the boot-test suite

`test_boot.py` boots the real kernel headless and drives the shell over COM1 in
lock-step: wait for the prompt, send one command, read its output. Every
assertion is on serial output, and values are random per run. It covers the boot
banner, `help`, `ls`, `cat`, `echo`, creating files, persistence across a warm
`reboot` and a real power cycle, `exec` of compiled programs, error paths, a
missing or unformatted disk, a CPU exception, `shutdown`, and a disk that is slow
or fails.

Three sessions change how the disk behaves. `slowdisk` makes QEMU hold each
sector write for 500 ms and checks the write still lands and survives a power
cycle. `slowio` does the same for slow reads, and throttles a write until the
kernel gives up, which must print an error and promise no file. `ioerror` uses
QEMU's blkdebug driver to fail writes, flushes or reads with `EIO`: `write`,
`rm`, `mkdir`, `rmdir`, `chmod`, `chown`, `ed`, `cat`, `run` and `exec` must each
report the failure, change nothing, and leave the disk intact after a power cycle.

```bash
python test_boot.py                 # build, then every session
python test_boot.py files errors    # only these sessions
python test_boot.py --no-build      # reuse build/
```

Each session writes its transcript to `build/test-logs/boot/<session>.log`: every
command sent, the raw COM1 text, each check, and QEMU's stderr. A session that
hangs or faults also records the VGA screen and `info registers`. A failing
session prints its transcript as well.

## `test_serial.py`: the serial console acceptance suite

Where `test_boot.py` drives the shell over COM1 to check shell *behavior*,
`test_serial.py` (943 lines) is about the COM1 console itself — the 16550
UART driver, its interaction with the framebuffer console and PS/2, and its
behavior under load. It runs 19 independent sessions
(`SESSIONS`, `test_serial.py:902`-`907`), each its own fresh QEMU boot:

- **`text`** (`test_serial.py:147`-`175`) — the baseline: boots the bare
  `-kernel` path with COM1 on QEMU's stdio pipe and drives `echo` (and
  `$USER` expansion), `uptime`, `help`, an unknown command, a shifted
  character (`echo Up_Case:?`), and line editing with DEL and Backspace —
  all typed and read back over serial alone, no VGA involved.
- **`line_endings`** (`:276`-`296`) — a bare CR and a CRLF pair sent over a
  TCP-backed COM1 each end exactly one line (CRLF must not produce two
  prompts), and the same output lands on the VGA console too.
- **`escape`** (`:299`-`309`) — CSI and SS3 escape sequences (arrow/function
  keys, as a terminal emulator would send them) are swallowed outright
  rather than echoed or run as command text.
- **`burst`** (`:312`-`324`) and **`cat_burst`** (`:327`-`355`) — an unpaced
  write of several lines, comfortably under the 512-byte receive ring, must
  all run; and 56 bytes typed while `cat` is mid-transmit (interrupts off,
  so only the ring — not the 16-byte hardware FIFO — can hold them) must
  still arrive in full.
- **`exec_paced`** (`:593`-`605`) — 37 bytes typed immediately after `exec`,
  before the loaded program has had a chance to print its own prompt, must
  not be dropped.
- **`polled_input`** (`:178`-`204`) — the two places a *command* polls
  hardware for more input mid-execution, both driven from serial: `sudo`'s
  password prompt (masked echo, accepted password) and `/bin/ask.bin`'s
  read-line syscall.
- **`ps2_alongside`** (`:677`-`699`) — one boot with both inputs live (PS/2
  over the QEMU monitor, COM1 on stdio): a keyboard command's output is
  mirrored to serial, and each input still works after the other has been
  used.
- **`overflow`** (`:619`-`636`) and **`stall`** (`:648`-`674`) — more input
  than the ring holds (counted as `ring-lost`), and output that backs up
  because nothing is reading the far end of a TCP-backed COM1 (counted as
  `tx-dropped`) — both must leave the shell answering afterward, with the
  loss reflected in the `serial` command's own counters.
- **`lsr_overrun`** (`:547`-`590`) — forces real UART overrun bits via
  loopback mode and the QEMU monitor's `o /b` port-write command, then
  checks the `overrun` counter catches every one. Before booting anything,
  it also greps `kmain.mx` itself for every function reading port `0x3FD`
  (the Line Status Register) and asserts the set is exactly
  `{serial_init, serial_lsr}` (`:559`-`564`) — a source-level guard that a
  future change can't add a second, uncounted LSR read without failing this
  test.
- **`flood`** (`:539`-`540`) and **`iso_flood`** (`:543`-`544`) — a
  sustained flood of input (bare CRs, then repeated `uptime`s) on the
  `-kernel` and ISO paths respectively must not starve the PIT (`g_ticks`
  keeps advancing) or stall a PS/2 key queued mid-flood, and the shell must
  still answer `uptime`/`echo` correctly once it ends.
- **`no_uart`** (`:885`-`899`) — with `-serial none`, the VGA console must
  report `serial: COM1 unavailable` (the same text `serial_status`,
  `kmain.mx:554`-`574`, prints) and the shell must still work from PS/2.
- **`iso`** (`:759`-`784`) — on the Borehole/ISO path, a command run from
  serial also draws on the framebuffer console (checked with a screendump
  diff), not just VGA text.
- **`iso_no_uart`** (`:787`-`803`) — the Surface screen's own on-screen UART
  report must differ between `-serial none` and a UART present — not only a
  fact visible in a log a player would never see.
- **`iso_junk`** (`:806`-`833`) — NUL and `0xFF` bytes sent over serial at
  the Surface screen must change nothing on screen and echo nothing, while
  real input typed right after still reaches the shell.
- **`iso_lock`** (`:836`-`860`) — bytes typed over serial while the lock
  screen is up are discarded outright (never echoed, never run once
  unlocked), even though the real unlock happens over the keyboard in the
  same session.
- **`iso_fault`** (`:863`-`882`) — the CPU-exception report and the
  `shutdown` notice both bypass the normal `put_cell_at` console path, so
  this session confirms both still reach serial.

```bash
python test_serial.py                  # build, then every session
python test_serial.py --no-build text  # reuse the build, chosen sessions
```

Pass session names to run only those (`list(SESSIONS)` for the full set,
`test_serial.py:929`). Timing assumptions are called out in the module
docstring (`test_serial.py:2`-`20`): stdio input is paced one byte per
kernel tick because QEMU's Windows stdio backend drops a byte rather than
wait when its FIFO trigger level is reached, and stdio strips CR — so
CR-vs-CRLF line-ending behavior (`line_endings`) and any burst over the
512-byte ring (`burst`, `session_overflow`) are driven over a TCP-backed
COM1 (`TcpSerial`, `:222`-`273`) instead.

## What the keyboard-driven scripts really prove

`test.py smoke`, `test_fs.py` and the keyboard half of `test_exec.py` show that
the kernel boots, that the PS/2-to-shell path works, and that the commands they
run do not crash the machine. They prove little about what those commands print.
Their checks search the whole VGA screen, and the command the script just typed
is on that screen, so looking for the text of a command passes even when its
output is wrong. Only checks for text that was never typed, such as an error
message or a file size, can fail on wrong output.

An independent review ran 5 kernel mutants. `test_boot.py` caught all 5. These
scripts stayed green on 4 of them, including with `echo` broken. On the fifth, the
exec mutant, `test_exec.py` failed (10 passed, 1 failed). They are kept for the
keyboard path, which `test_boot.py` does not use. Put a check for what a command
does in `test_boot.py`, where the assertions are exact.

## What each script checks

### `test.py smoke`

The shared harness's own smoke test (`smoke()`, `test.py:302`-`339`): builds
the kernel, boots it with no disk attached, and checks four things on the
VGA text screen — the `MORT OS` boot banner, that `help` lists commands
(matches `clear about echo`), that `echo hi-there` echoes back, and that
`uptime` reports a value (matches `uptime:`).

### `test_fs.py` — the disk stack

Runs the kernel through four separate boot sessions against three fixture
images (a `mkfs.py`-seeded disk, a 16 MiB zeroed non-MortFS image, and no
disk at all). As of 2026-10-09 (`265537a`) the suite was rewritten for the
user/cwd/`$PATH` layout — the shell now auto-logs-in as `mortuex` and starts
in `/home/mortuex` rather than `/` (`login_default`/`cwd_init`,
`kmain.mx:2910`/`2916`, see [`docs/accounts.md`](accounts.md)), so a bare
`ls`/`cat <name>` no longer sees root-level files:

1. **Session 1** (seeded disk): `ls /`/`cat /seeded.txt` against the
   root-level seeded file (`test_fs.py:60`-`64`), `write` to create a file
   in the cwd (`/home/mortuex`), a second `write` to the same name
   (append), `cat` on a missing file (`not found: <name>`), `write` with no
   text (usage message), `sudo rm /seeded.txt` then the `mortuex` account's
   password (`mort`) then `cat /seeded.txt` (removed) — `mkfs.py` seeds
   `seeded.txt` owned by uid 0 (`mode 0644`), so removing it as the normal
   user needs `sudo` (`test_fs.py:79`-`84`; see
   [`docs/shell.md`](shell.md)'s `sudo` row for the prompt/auth mechanics) —
   authoring a two-line script with `write` and running it with `run`, and
   a nested `run` (`run` inside a script) being rejected while the outer
   script keeps going.
2. **Session 2** (reboot, same image): re-boots the *same* disk image and
   checks the file written in session 1 and its content survived —
   MortFS's actual persistence guarantee, not just an in-memory one.
3. **Session 3** (zeroed image): boots with a disk attached that isn't a
   MortFS volume at all and checks `ls` reports `bad filesystem`.
4. **Session 4** (no disk): checks `ls` reports `no disk` and that `mods`
   (unrelated to the disk) still lists boot modules.

### `test_exec.py` — running compiled programs

Compiles every file `build._program_sources()` finds under `programs/` to a
flat binary, seeds them onto a fresh image via `mkfs.py`, boots, and drives
`exec`. As of 2026-10-09 (`265537a`) this suite was also rewritten for the
user/cwd/`$PATH` layout: `fs_populate_bin` moves every seeded `.bin` from
`/` into `/bin` on first boot (`kmain.mx:1641`-`1653`, see
[`docs/accounts.md`](accounts.md)), so the test checks `ls /bin` (not a
bare `ls`) for the seeded binaries and `exec`s them by full path
(`exec /bin/hello.bin`, not `exec hello.bin`, `test_exec.py:56`-`72`):
`ls /bin` shows the seeded `.bin` files; `exec /bin/hello.bin` prints its
syscall output and the shell is still alive afterward (`echo` works); `exec
/bin/count.bin` prints `one` and `three`; `exec /bin/ask.bin` (the
interactive sample) prompts, reads a typed name via the read-line syscall,
and greets it; `exec nope.bin` (deliberately a bare, non-existent name, not
under `/bin`) reports `not found: nope.bin`; and the shell survives cleanly
after an interactive program returns. See
[`docs/programs.md`](programs.md) for what these sample programs actually
do and the syscall ABI they use.

### `test_gfx.py` — the Borehole interface

The only script that boots the ISO path (`build.iso()`), since that's the one
that gets a Limine-provided framebuffer. It attaches a scratch copy of the
MortFS disk, presses real keys over the QEMU monitor, and asserts on PPM
screendumps. Text is read by decoding pixels against the kernel's own font
table parsed out of `kmain.mx`; console cells must match glyph and background
exactly.

Phases: the surface (lithology, shaft, captions, selection), the shell
(gallery, typed commands, scrolling, returning with the console intact),
Objects and the core sample, Machine, Terminate with exact lock and sleep
screens, the `power`/`lock`/`sleep` commands, long names, directories nested
18 deep, a directory too full to fit (a separate boot with a seeded disk), and a
CPU fault.

`phase_memory` proves nothing draws outside its surface: it dumps about 240 MiB
of guest RAM with `pmemsave` around the short-sky scenes and around the
`drawprobe` command, and diffs them outside the back buffer, plus spare VRAM
past the visible frame and the visible screen edges.

`python test_gfx.py phase_deep phase_full_dir` runs only the named phases.

## The harness API (`test.py`)

`test_fs.py`, `test_exec.py`, and `test_gfx.py`'s keyboard-driven checks (the
first two, not `test_gfx.py`'s screendump path) all build on the same small
API exported by `test.py`:

| Function | What it does |
|---|---|
| `boot(disk_img=None, kernel_elf=ELF)` (`test.py:161`-`182`) | Launches `qemu-system-i386 -display none -monitor stdio -kernel <elf>` (plus `-hda <disk_img>` if given) and waits for the first monitor prompt. |
| `type_line(handle, text)` (`test.py:185`-`191`) | Sends each character as a QEMU `sendkey` monitor command (`key_name()`, `test.py:57`-`67`, maps it to QEMU's key names, including `shift-`-prefixed symbols), then `ret`. |
| `screen_text(handle)` (`test.py:194`-`204`) | Dumps `0xB8000`..`0xB8FA0` (the 80x25 VGA text buffer) via the monitor's `memsave`, falling back to parsing `xp` hex output if `memsave` fails, and returns it as 25 newline-joined lines. |
| `wait_for(handle, substring, timeout_s=10)` (`test.py:207`-`215`) | Polls `screen_text()` every 0.25s until `substring` appears or the timeout elapses. |
| `shutdown(handle)` (`test.py:218`-`246`) | Sends monitor `quit`, kills the process if it lingers, and cleans up the temp VGA dump file. Never raises. |

`sendkey` holds each key down for `KEY_HOLD_MS` (40ms) with a `KEY_GAP_S`
(0.07s) pause after — the comment at `test.py:35`-`39` notes the gap must
exceed the hold time, since a faster next key would land while a `shift-`
sendkey is still releasing.

`screen_text`'s `memsave`-first, `xp`-fallback split is two private
helpers: `_dump_vga_memsave` (`test.py:251`-`271`) asks QEMU to write the
4000-byte VGA text region straight to a host file at `handle._dump` (a
`tempfile.gettempdir()` path) via the monitor's `memsave` command, then
reads that file back. It returns `None` — silently falling through to
`_dump_vga_xp` — in three cases: the dump path contains a space, since
"monitor filename args don't survive spaces" (`test.py:254`-`255`, checked
*before* even trying the command); the file wasn't written or isn't
exactly 4000 bytes; or the monitor's own reply contains `"could not"` or
`"error"`. The space check matters beyond Windows usernames with a space
in them — the default on any host is whatever `tempfile.gettempdir()`
returns, which runs through `memsave` unmodified except for `os.sep`
normalization (`test.py:261`). `_dump_vga_xp` (`test.py:274`-`291`) takes
the slower path instead: it parses the monitor's `xp /2000wx 0xb8000` text
output (hex words, one VGA cell pair per nibble group) by hand, and unlike
the primary path it `raise`s rather than returning `None` if it parses
fewer than 4000 bytes — a parse failure here fails the test outright
instead of falling back further.

## Not covered by any script

Networking (`net`, `httpd`, and everything under `net/` except
`net/hardware.mx`/`net/audio.mx`/`net/hci_usb.mx`) has no automated coverage
at all — see [`docs/networking.md`](networking.md#not-covered-by-automated-tests)
for the grounded detail. The Machine stratum's hardware actions (DHCP, speaker,
AC'97) are listed by `test_gfx.py` but not run by it.
