# Testing

MORT OS has no unit tests in the usual sense — nothing here can run outside a
booted kernel, since a from-scratch OS has no host runtime to link against.
All four test scripts instead boot the *real* kernel headless in QEMU and
drive it like a person would: typing on the emulated PS/2 keyboard through
QEMU's human monitor, then reading assertions back out of guest video memory.
`test.py` is the shared harness the other three import; it has no tests of
its own beyond the `smoke` subcommand.

```bash
python test.py smoke      # boot + shell basics (text-mode -kernel path)
python test_fs.py         # the disk stack, incl. write-reboot-cat persistence
python test_exec.py       # build programs, seed, boot, exec, check syscall output
python test_gfx.py        # boot the ISO, screendump, assert the desktop + console rendered
```

All four need `qemu-system-i386` on `PATH` (found via `build._find_qemu()`,
`build.py`); `test_exec.py` also needs `pip install ziglang` since it
compiles the sample programs first. `test_gfx.py` additionally only runs on
Windows: it boots via `build.iso()`, which fetches and directly executes
Windows `.exe` binaries for Limine/xorriso with no Wine fallback — see the
ISO note in [`README.md`](../README.md#a-real-bootable-iso). None of the four
scripts touch files in the repo — scratch disk images and screendumps go to
the system temp dir (`tempfile.mkdtemp`).

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

### `test_gfx.py` — the graphical desktop

The only script that boots the ISO path (`build.iso()`) instead of the bare
`-kernel` path, since that's the one that gets a Limine-provided
framebuffer. Screendumps the framebuffer as a PPM (parsed by hand,
`parse_ppm`, `test_gfx.py:38`-`53`) and checks specific pixel colors: the
framebuffer is 1024x768, the top bar and a window title bar render with
their expected background colors, and typing `help` produces at least 50
non-background pixels in the console area (i.e. glyphs actually drew).

It also asserts on **per-app top-bar tab highlighting** across F1/F2/F3
switches (`test_gfx.py:105`-`140`) — e.g. that pixel `(296, 10)` is the
active-tab color at boot and after switching back to F1, and the
inactive-tab color after `F2`. That assertion does not match the kernel as
currently written: `draw_topbar()` (`kmain.mx:467`-`473`, called from
`switch_app()` at `kmain.mx:2845`) draws only the "MORT OS" label, the "F5
home"/"F12 power" hints, and the clock — no per-app tabs. The helper that
would draw a highlighted tab, `draw_tab()` (`kmain.mx:453`-`462`), is
defined but never called anywhere in the source (confirmed by grep), and
nothing else in `kmain.mx` paints the active-tab color (`0x2c5364`) inside
the top bar's row (y ≈ 0-24). This looks like a test written against an
intended feature that `draw_tab()`'s own comment (`kmain.mx:452`) already
flags as unused — see the existing backlog item about wiring it up or
deleting it. Whether `test_gfx.py` currently passes this assertion is
something only a human with a local QEMU + ISO toolchain can confirm; this
doc doesn't claim it fails, only that no source path currently produces the
pixels it's checking for.

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

## Not covered by any of the four scripts

Networking (`net`, `httpd`, and everything under `net/` except
`net/hardware.mx`/`net/audio.mx`/`net/hci_usb.mx`) has no automated coverage
at all — see [`docs/networking.md`](networking.md#not-covered-by-automated-tests)
for the grounded detail. Settings, the file manager (Files app), and the Vex
browser app also have no dedicated assertions in any of the four scripts
beyond `test_gfx.py`'s generic "tab switched" pixel checks.
