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
compiles the sample programs first. None of them touch files in the repo —
scratch disk images and screendumps go to the system temp dir
(`tempfile.mkdtemp`).

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
disk at all):

1. **Session 1** (seeded disk): `ls`/`cat` against the seeded file, `write`
   to create a file, a second `write` to the same name (append), `cat` on a
   missing file (`not found: <name>`), `write` with no text (usage
   message), `rm` then `cat` (removed), authoring a two-line script with
   `write` and running it with `run`, and a nested `run` (`run` inside a
   script) being rejected while the outer script keeps going.
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
`exec`: `ls` shows the seeded `.bin` files; `exec hello.bin` prints its
syscall output and the shell is still alive afterward (`echo` works); `exec
count.bin` prints `one` and `three`; `exec ask.bin` (the interactive sample)
prompts, reads a typed name via the read-line syscall, and greets it; `exec
nope.bin` reports `not found: nope.bin`; and the shell survives cleanly
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
`switch_app()` at `kmain.mx:2841`) draws only the "MORT OS" label, the "F5
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
| `boot(disk_img=None, kernel_elf=ELF)` | Launches `qemu-system-i386 -display none -monitor stdio -kernel <elf>` (plus `-hda <disk_img>` if given) and waits for the first monitor prompt. |
| `type_line(handle, text)` | Sends each character as a QEMU `sendkey` monitor command (`key_name()` maps it to QEMU's key names, including `shift-`-prefixed symbols), then `ret`. |
| `screen_text(handle)` | Dumps `0xB8000`..`0xB8FA0` (the 80x25 VGA text buffer) via the monitor's `memsave`, falling back to parsing `xp` hex output if `memsave` fails, and returns it as 25 newline-joined lines. |
| `wait_for(handle, substring, timeout_s=10)` | Polls `screen_text()` every 0.25s until `substring` appears or the timeout elapses. |
| `shutdown(handle)` | Sends monitor `quit`, kills the process if it lingers, and cleans up the temp VGA dump file. Never raises. |

`sendkey` holds each key down for `KEY_HOLD_MS` (40ms) with a `KEY_GAP_S`
(0.07s) pause after — the comment at `test.py:35`-`39` notes the gap must
exceed the hold time, since a faster next key would land while a `shift-`
sendkey is still releasing.

## Not covered by any of the four scripts

Networking (`net`, `httpd`, and everything under `net/` except
`net/hardware.mx`/`net/audio.mx`/`net/hci_usb.mx`) has no automated coverage
at all — see [`docs/networking.md`](networking.md#not-covered-by-automated-tests)
for the grounded detail. Settings, the file manager (Files app), and the Vex
browser app also have no dedicated assertions in any of the four scripts
beyond `test_gfx.py`'s generic "tab switched" pixel checks.
