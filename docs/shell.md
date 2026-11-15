# Shell command reference

Every command line goes through `run_command` (`kmain.mx:2893`), which expands
`$VAR` references via `expand_vars` (`kmain.mx:2754`) and then dispatches on an
`if streq(cmd, "...")` / `if starts_with(cmd, "...")` chain in
`run_command_impl` (`kmain.mx:2901`-`3447`, exactly 45 such branches). This
table lists every command recognized there, in source order, with the line
where its match starts.

**`ls`, `cat`, and `echo` are usually not the builtins below.** Before any of
the 45 branches run, `run_command_impl` calls `try_migrated_program`
(`kmain.mx:2873`-`2886`), which intercepts exactly these three command names
and, if the filesystem is mounted, tries to run the compiled program at
`/bin/ls.bin`, `/bin/cat.bin`, or `/bin/echo.bin` instead, via
`exec_if_program` (`kmain.mx:2813`-`2829`). `fs_populate_bin`
(`kmain.mx:1925`-`1946`) marks every seeded `*.bin` executable on a normal
boot, so on a normal boot these three commands run the real program
(`programs/ls.mx`, `programs/cat.mx`, `programs/echo.mx` — see
[`docs/programs.md`](programs.md)), not the kernel code described in their
rows below. The builtins are the fallback: `try_migrated_program` returns
`false` (falling through to the rows below) whenever there is no disk
(`!g_fs_ok`), the binary is missing, it resolves to a directory, or it has no
execute bit (`exec_if_program`'s own checks, `kmain.mx:2814`-`2823`).

Commands marked **disk** call `fs_guard()` (`kmain.mx:2116`-`2132`) first,
which refuses with `no disk (boot with -hda disk.img)` if no disk image is
attached, `bad filesystem (host: python kernel/mkfs.py disk.img)` if one is
attached but didn't parse, or — a check this function gained since those two
messages were last documented — `i/o error: disk read failed`
(`report_read_error`, `kmain.mx:1790`-`1793`) if the disk parsed fine at boot
but a later read of it failed. Several disk-mutating commands below
(`write`, `rm`, `rmdir`, `mkdir`, `chmod`, `chown`) can also fail *after*
their own checks pass, if the actual write to disk fails: `rm`/`rmdir`/
`chmod`/`chown` call `report_write_error()` directly (`kmain.mx:1785`-
`1788`), while `mkdir` and `write`'s create path get the identical message
from `fs_create_full`'s own undo branch (`fs_fail(5, "i/o error: disk
write failed")`, `kmain.mx:1856`-`1860`). Either way the command's row
below lists only its own usage/permission errors, not this shared one.

| Command | Disk? | Behavior | Source |
|---|---|---|---|
| `help` | | Prints seven lines (`kmain.mx:2909`-`2922`): one unlabeled bare list of command names (`help clear about echo uptime crash readme mem serial`), then six labeled groups — `files:`, `programs in /bin:`, `net:`, `power:`, `users:`, `env:`. `mods` (below) is the one command in this whole table that appears in none of the seven lines, so `help` alone won't tell you it exists. | `kmain.mx:2908` |
| `readme` | | Shows the multiboot module text passed in by the bootloader (`show_module`, `kmain.mx:1071`-`1080`). | `kmain.mx:2925` |
| `mem` | | Sums the multiboot memory map's usable (type 1) regions and prints total RAM in MB. | `kmain.mx:2929`, `kmain.mx:1154` |
| `mods` | | Lists the multiboot modules loaded at boot, with sizes. | `kmain.mx:2933`, `kmain.mx:1182` |
| `net` | | Runs DHCP over the RTL8139 NIC to lease an IP (`net_dhcp`, `net/netapp.mx:46`). | `kmain.mx:2937` |
| `httpd` | | Serves an HTML page on TCP port 80 (`net_httpd`, `net/netapp.mx:176`). | `kmain.mx:2941` |
| `pwd` | | Prints the current working directory path (`g_cwdpath`). | `kmain.mx:2945` |
| `cd [dir]` | disk | Changes directory; no argument goes to `/home/<user>`. Errors: `no such directory`, `not a directory`. Rebuilds `g_cwdpath` for `pwd` via `path_of`, which has no bound on path length, and the next prompt redraw copies it into its own smaller, also-unbounded buffer — see [`docs/fs-design.md`](fs-design.md)'s directory section for both concrete overflows. | `kmain.mx:2950` |
| `ls [dir]` | disk | **Builtin fallback only — see the migration note above.** Lists entries in the current directory (or `dir`): type (`d`/`-`), octal mode, name, size, owning uid. Prints `(empty)` if nothing matches. | `kmain.mx:2976` |
| `mkdir <dir>` | disk | Creates a directory. Errors: `parent directory does not exist`, `already exists`. A long enough `<dir>` overflows a fixed stack buffer before any of those checks run, see below. | `kmain.mx:3028` |
| `rmdir <dir>` | disk | Removes an empty directory. Errors: `no such directory`, `not a directory`, `directory not empty`. | `kmain.mx:3041` |
| `cat <file>` | disk | **Builtin fallback only — see the migration note above.** Reads the file into `FILEBUF` (`0x00810000`) and prints its contents. Errors: `not found: <name>`, `cat: is a directory`. | `kmain.mx:3068` |
| `write <file> <text>` | disk | Appends `<text>` as a line to `<file>`, creating it (in the resolved parent directory) if it doesn't exist. Silent on success. Errors: `usage: write <name> <text>`, `write: is a directory`, `permission denied`, `write: parent directory does not exist`, `file full (max 64 KB)`. A long enough `<file>` overflows the same fixed stack buffer `mkdir` does, resolving the parent — see `mkdir`'s row above. | `kmain.mx:3092` |
| `rm <file>` | disk | Removes a file. Errors: `not found: <name>`, `rm: is a directory (use rmdir)`, `permission denied`. **Does not free the file's disk space**: `fs_remove` (`kmain.mx:2100`-`2113`) only clears the `used` flag and decrements `file_count` — the 128-sector (64 KiB) extent `fs_create_full` gave the file is never returned to the bump allocator (`kmain.mx:1844`-`1852`), in either the v1 or v2 on-disk format. Every create-after-delete cycle permanently burns another 64 KiB until the disk reports full (`"disk full (rm does not reclaim; re-run mkfs)"`, `kmain.mx:1848`) even if `ls` shows only a few live files; the only fix is re-running `mkfs.py` on the host. See [`docs/fs-design.md`](fs-design.md#26-deletion--documented-limitation) for the original design rationale, including the exact 255-creates-before-full math for the default 16 MiB image. | `kmain.mx:3137` |
| `run <file>` | disk | Reads `<file>` and runs each line as a shell command (`run_file`, `kmain.mx:1127`-`1147`). Refuses to nest (`run: nested run not allowed`) because a script's `run` would clobber the shared `FILEBUF`. | `kmain.mx:3160` |
| `exec <file>` | disk | Loads a compiled Mort program from `<file>` into the fixed program window at `0x00A00000` and jumps to it (`exec_file`, `kmain.mx:2647`-`2689`); the program talks back to the kernel via `int 0x80` syscalls, with its own process-table entry and `$?` exit status — see [`docs/programs.md`](programs.md) for that machinery. Errors: `not found: <name>`, `empty program`, `too many arguments (max 16)`. | `kmain.mx:3165` |
| `whoami` | | Prints the current username and uid. | `kmain.mx:3176` |
| `export NAME=value` | | Sets a shell environment variable (`env_set`). Usage error if there's no `=`. Custom variables are capped at 8 slots (`g_env_name`/`g_env_val`, `kmain.mx:36`-`37`); a 9th *new* variable name is silently dropped with no error (`env_set`'s `g_env_count >= 8` check, `kmain.mx:2710`-`2712`) — re-`export`-ing an *existing* name still updates its value past the cap, since that path skips the count check. | `kmain.mx:3186` |
| `env` | | Prints `USER`, `HOME`, `PATH`, `PWD`, then every variable set via `export`. | `kmain.mx:3204` |
| `unset NAME` | | Removes a variable set via `export` (no-op if unset). | `kmain.mx:3216` |
| `su [user]` | | Prompts for a password and, if it matches, switches the session uid/username to `user` (default `root`). Error: `su: no such user`, `su: authentication failure`. | `kmain.mx:3230` |
| `sudo <cmd>` | | Prompts for the current user's password, then runs `<cmd>` once with uid 0 if it matches. No-op prompt if already root. Error: `sudo: authentication failure`. A password of 52+ characters overflows the prompt's row — see [`docs/accounts.md`](accounts.md#sudos-password-prompt-can-overflow-past-column-79-unlike-sus-or-passwds). | `kmain.mx:3255` |
| `passwd` | | Prompts for a new password and updates it for the current account, for this boot session only (not persisted to disk). | `kmain.mx:3281` |
| `chmod <octal> <path>` | disk | Sets a file/directory's octal permission bits. Only the owner or root may do this (`chmod: not permitted`). Error: `usage: chmod <octal> <path>`, `chmod: not found`. | `kmain.mx:3295` |
| `chown <uid> <path>` | disk | Changes a file/directory's owning uid; root only (`chown: not permitted (root only)`). Error: `usage: chown <uid> <path>`, `chown: not found`. | `kmain.mx:3332` |
| `reboot` / `restart` | | Reboots the machine (`reboot`, `kmain.mx:1261`-`1266`) by pulsing the 8042 keyboard controller's reset line — `outb(0x64, 0xFE)` (`kmain.mx:1262`), the pre-ACPI trick of asking the keyboard controller to pulse output line 0, which is wired to the CPU's reset pin on PC-compatible hardware — then falls into a `hlt` loop (`kmain.mx:1263`-`1265`) in case the reset doesn't land immediately. | `kmain.mx:3369`, `kmain.mx:3373` |
| `shutdown` / `poweroff` | | Powers the machine off (`poweroff`, `kmain.mx:3668`-`3686`). What it prints depends on `g_gfx`: in VGA text mode it prints "It is now safe to turn off your computer." directly to the screen (`kmain.mx:3675`); in graphics mode it instead sends that same line out over the serial port (`serial_puts`, `kmain.mx:3670`-`3672`) and calls `ui_capped()` to draw a Borehole screen, so a graphics-mode reader watching only the display never sees that exact sentence. Either way it then writes three emulator-specific ACPI shutdown values in sequence — `outw(0x604, 0x2000)`, `outw(0xB004, 0x2000)`, `outw(0x4004, 0x3400)` (`kmain.mx:3679`-`3681`), labeled in source as QEMU/Bochs/VirtualBox's respective magic ports in that order — then falls into a `cli`+`hlt` loop (`kmain.mx:3682`-`3685`) for bare metal, where none of those port writes do anything. | `kmain.mx:3377`, `kmain.mx:3381` |
| `power` | | Opens the Terminate stratum (Lock/Sleep/Restart/Shut down) from the shell (`ui_open_terminate`, `ui/borehole.mx:1596`-`1605`). In VGA text mode it prints `power needs the graphical interface` (`ui/borehole.mx:1597`-`1600`) instead of opening it. | `kmain.mx:3385` |
| `memtest` | | Not a physical RAM test: a smoke test for the `kmalloc`/`kfree` heap allocator (`memtest`, `kmain.mx:1208`-`1258`) — allocate two blocks, verify their writes don't clobber each other, free and reallocate to confirm first-fit reuse, then free both (`kmain.mx:1240`-`1241`), which runs `kfree`'s forward-coalescing path, before printing heap base/size and a PASS/FAIL line. Prints `heap: unavailable` instead and skips all of that if `heap_init()` never found usable RAM (`!g_heap_ok`, `kmain.mx:1210`-`1213`). The PASS/FAIL itself only reflects the three checks above it (the two allocations' writes, and the first-fit reuse) — nothing after the final `kfree` calls inspects the merged block, so a coalescing bug that produced a wrong size (rather than a hang) would still print PASS. See [`docs/memory-map.md`](memory-map.md#the-kernel-heap-allocator-kmallockfree) for the allocator design this exercises. | `kmain.mx:3397` |
| `lock` | | Seals the screen until the account password is given (`ui_open_lock`, `ui/borehole.mx:1661`-`1673`), then returns to the shell. In VGA text mode it prints `lock needs the graphical interface` (`ui/borehole.mx:1662`-`1665`) instead. | `kmain.mx:3401` |
| `sleep` | | Blanks the display until a keypress (`ui_open_sleep`, `ui/borehole.mx:1718`-`1727`), then returns to the shell. In VGA text mode it prints `sleep needs the graphical interface` (`ui/borehole.mx:1719`-`1722`) instead. | `kmain.mx:3405` |
| `drawprobe` | | Test support, graphics only, shell gallery only. Runs every drawing primitive deliberately outside the screen, then prints `back= fb= pitch=`. `drawprobe info` only prints the addresses. `test_gfx.py` diffs guest memory around it. | `kmain.mx:3389`, `ui_drawprobe` `ui/borehole.mx:1778` |
| `crash` | | Executes `ud2` to raise a #UD exception, to demo the exception-reporting handlers. | `kmain.mx:3409` |
| `uptime` | | Prints seconds since boot, from the PIT tick counter (`g_ticks / 100`, ~100 Hz). | `kmain.mx:3413` |
| `clear` | | Clears the screen and resets the cursor row. | `kmain.mx:3421` |
| `serial` | | Prints COM1's status (`serial_status`, `kmain.mx:554`-`574`): `serial: COM1 unavailable` if the port never initialized (`!g_serial_ok`), else `serial: COM1 115200` followed by three running counters — `overrun` (bytes the receive ISR dropped because its ring was full), `ring-lost` (bytes `serial_service` found it had already lost once it got around to draining the ring), and `tx-dropped` (output bytes dropped because the transmitter stayed busy too long). Not in [`docs/networking.md`](networking.md) — COM1 is a local serial console/shell-input path, unrelated to the mortnet stack. | `kmain.mx:3426` |
| `about` | | Prints a one-line description of MORT OS. | `kmain.mx:3430` |
| `echo <text>` | | **Builtin fallback only — see the migration note above.** Prints `<text>` (everything after `echo `). | `kmain.mx:3435` |
| *(anything else)* | | Tried as a program name on `$PATH` (`try_exec_path`, `kmain.mx:2834`-`2869`): as typed, as `/bin/<name>`, as `<name>.bin`, then `/bin/<name>.bin`, each checked with `exec_if_program`. Falls through to `unknown command` (and sets `$?` to 127) if none match. | `kmain.mx:3440` |
| *(empty line)* | | No-op. | `kmain.mx:2902` |

## `mkdir`'s double error message is fixed; a buffer overflow is not

**This section used to document a live bug; it no longer applies, but is
kept (corrected) since the fix landed without a doc update.** `fs_mkdir`
(`kmain.mx:1877`-`1890`) returns a `u32` with four meanings: `65` for
"already exists", `66` for any other `fs_create_full` failure (added by
`dd76371`, "kernel: report disk errors instead of pretending a write
worked" — see `BACKLOG.md`'s now-checked-off item for this), a resolved
slot index on success, and `64` only for the genuine "parent missing"
case. The `mkdir` dispatch (`kmain.mx:3028`-`3039`) still only checks for
`64` and `65`:

```
let r: u32 = fs_mkdir((cmd as u32 + 6) as u64);
if r == 64 {
    feed();
    print_string("mkdir: parent directory does not exist", g_row, 12);
}
if r == 65 {
    feed();
    print_string("mkdir: already exists", g_row, 12);
}
```

— but that is now correct, not a bug: `fs_mkdir` returns `64` *only* when
`fs_parent_of` (`kmain.mx:1705`-`1747`) itself returns `64` because the
parent component doesn't resolve or isn't a directory (`kmain.mx:1738`-
`1744`), which `fs_mkdir` passes straight through (`kmain.mx:1879`-`1881`).
Once the parent *does* resolve, `fs_mkdir` hands it to `fs_create_full`
(`kmain.mx:1816`-`1863`); if that fails, `fs_mkdir` now maps the result to
`66` (`kmain.mx:1886`-`1888`), which matches neither dispatch check, so no
second "parent directory does not exist" is printed on top of whichever
message `fs_create_full` already gave (name too long `kmain.mx:1818`-
`1819`, permission denied `kmain.mx:1821`-`1822`, file table full
`kmain.mx:1825`-`1826`, or disk full `kmain.mx:1846`-`1848`). Concretely,
`cd /etc` as the default `mortuex` user (`/etc` is root-owned, mode `0755`,
for the reasons [`docs/accounts.md`](accounts.md#the-seeded-hellotxt-belongs-to-root-not-to-you)
explains), then `mkdir foo`, now prints only `permission denied` — no
trailing false message.

A 24+ character name is a separate, still-live bug: `fs_mkdir` and
`write`'s create path both hand `fs_parent_of` a 24-byte `leaf` buffer
(`kmain.mx:1878`, `kmain.mx:3117`), and `fs_parent_of` writes the name into
it with no length check of its own — the 23-character cap mentioned above
is `fs_create_full`'s, enforced only once `fs_parent_of` has already
returned. A name of 24 characters or more (or, with a `/` in the path, a
parent prefix of 64 characters or more) overflows that buffer, or a second
one inside the same function, before any error message prints. See
[`docs/fs-design.md`](fs-design.md)'s directory section for the full trace
and the exact one-line repro — the same class of bug as `path_of`'s and
`draw_prompt`'s overflows documented just above it, but reachable in a
single `mkdir`/`write` with no nesting needed.

`write`'s create path (`kmain.mx:3116`-`3125`) is `fs_mkdir`'s nearly
identical twin: it checks `fs_parent_of`'s result on its own first and
only *then* calls `fs_create_full`, trusting that call's own error message
with no second message tacked on (`kmain.mx:3124`, `// prints its own
error`) — the same shape `fs_mkdir` now has too, since the `66` sentinel
fix.

## After Enter: feed, redraw, or leave it alone

**`on_key` is now a one-line wrapper**: `on_key()` (`kmain.mx:3688`-`3690`)
just calls `key_event(inb(0x60))`, and `key_event(sc)` (`kmain.mx:3692`-
`3761`) is where all the scancode-decoding logic — including Enter —
actually lives. It has a second caller besides the keyboard IRQ:
`serial_service()` (`kmain.mx:735`, per [`docs/architecture.md`](architecture.md))
feeds bytes typed over COM1 through the same function, so a command typed
over the serial console runs through identical handling to one typed on
the keyboard.

`run_command` (`kmain.mx:2893`-`2899`) returns whatever `run_command_impl`
returns, and `key_event`'s Enter handler (`kmain.mx:3724`-`3739`) uses that
`bool` to decide whether to call `feed()` before redrawing the prompt:

- `if g_len > 0 { hist_store(g_buf); }` (`kmain.mx:3726`-`3728`) records
  the line, then `run_command(g_buf)` runs it (`kmain.mx:3730`).
- If it returned `false`, `feed()` (`kmain.mx:827`-`835`) runs first
  (`kmain.mx:3731`-`3733`); either way, `key_event` then always clears
  `g_len`, redraws the prompt, and repositions the cursor
  (`kmain.mx:3734`-`3737`).

That last point is a real change from how this section used to read: the
old GUI had a `g_overlay` flag that let a command (`power`/`lock`/`sleep`
in graphics mode) skip the prompt redraw entirely, since an overlay
repainted the whole screen itself. `g_overlay` no longer exists anywhere
in the source (confirmed by grep) — the Borehole rewrite replaced the
overlay system with the scene state machine (`g_scene`) described in
[`docs/architecture.md`](architecture.md). `key_event`'s Enter handler has
no scene-aware branch any more; it runs the same `feed()`-or-not-then-
redraw sequence regardless of what `run_command` did. **Not independently
verified**: how that unconditional terminal-prompt redraw interacts with a
scene like `SC_LOCK` that `ui_open_lock` just switched to — whether the
scene's own draw happens to run again afterward (e.g. from the timer tick)
and simply overwrites it, or something else — needs tracing through
`ui_reveal`/`ui_start`/the per-tick redraw path in `ui/borehole.mx`, which
this pass did not do; left as a follow-up in `BACKLOG.md`.

The returned `bool` itself still has exactly one real use. Despite the
name suggesting a general "did this command finish cleanly" signal,
`clear` (`kmain.mx:3421`-`3425`) is the *only* branch in all of
`run_command_impl`'s 45-way dispatch that returns `true` — confirmed by
grep, there is exactly one `return true` in the whole function
(`kmain.mx:3424`), and every other path, including every error message,
`exec`, `run`, `su`/`sudo` failures, and even the unreachable lines after
`reboot`/`poweroff`'s `hlt` loops, returns `false`. `clear` returning
`true` suppresses the post-command `feed()` specifically because
`clear_screen()` already blanked the console and reset `g_row` to `0`
itself (`kmain.mx:3422`-`3423`); an unconditional `feed()` right after
would scroll the freshly blanked screen by one line and misplace the next
prompt at row 1 instead of row 0. Every other command relies on that same
`feed()` call to both separate its own output from the next prompt and
perform the actual line-advance/scroll.

## `$VAR` expansion

Every command — typed at the prompt, run from a script via `run`, or the
tail of a `sudo`/`su` invocation — is passed through `expand_vars`
(`kmain.mx:2754`-`2799`) before dispatch, so `echo $USER` or `cd $HOME`
work anywhere a command line is accepted.

### `$?` is a special case inside `expand_vars`, not a stored variable

`expand_vars` checks for the literal two-character sequence `$?` before
its general `$NAME` handling (`kmain.mx:2762`-`2770`): if it matches, it
substitutes the decimal value of `g_last_status` — the exit status of the
last command, reset to `0` at the top of every `run_command`
(`kmain.mx:2895`-`2896`) and set by whichever command last ran (e.g.
`exec_file`, `kmain.mx:2688`, or the `unknown command` fallback,
`kmain.mx:3445`, which sets it to `127`). `?` is not a valid name
character per `is_name_char` (`kmain.mx:2745`-`2751`, letters/digits/`_`
only), so `$?` could never reach `env_get` through the general path below
even if someone tried; it is handled entirely separately, and there is no
way to `export`, `unset`, or otherwise store a variable literally named
`?`. [`docs/programs.md`](programs.md#running-one) already notes `$?` and
the `ls`/`cat`/`echo` program/builtin split (see the migration note at the
top of this file) from the programs side; this is the shell-side
mechanism behind the `$?` half of that.

### `export`ing `USER`, `HOME`, `PATH`, or `PWD` is invisible

`export` (`kmain.mx:3186`-`3203`) has no reserved-name check — it hands
whatever name follows `export ` straight to `env_set`
(`kmain.mx:2707`-`2724`), which has no such check either. But `env_get`
(`kmain.mx:2728`-`2743`), the function every read goes through, tests for
four computed built-ins with `streq` *before* it ever consults the custom
table (`env_find`, `kmain.mx:2695`-`2705`): `USER` and `PWD` return live
kernel state, `PATH` returns the hardcoded literal `"/bin"`
(`kmain.mx:2731`), and `HOME` is rebuilt from the current username
(`kmain.mx:2732`-`2735`). One consequence, not previously documented:

- `export PATH=/custom` (or `USER=`/`HOME=`/`PWD=`) does create a real
  entry in the 8-slot custom-variable table, and does count against the
  cap (`kmain.mx:2713`-`2714`) — it isn't rejected. But every subsequent
  read of `$PATH` (via `expand_vars`) or `env`'s `PATH=` line still calls
  `env_get("PATH")`, which returns `/bin` regardless: the exported value
  is stored but never once read back anywhere in the source.
- `env` (`kmain.mx:3204`-`3215`) prints the four built-ins first (via the
  `env_print` helper), then loops over every custom entry and prints it
  by name (`kmain.mx:3210`-`3212`) — through the same `env_get`. So a
  `PATH` entry that exists only because it was exported still resolves
  through the built-in check, and `env` shows `PATH=/bin` twice,
  identically, rather than showing what was actually exported.
- Separately, `try_exec_path` (`kmain.mx:2834`-`2869`) — the code that
  turns an unrecognized command into `/bin/<name>` or `/bin/<name>.bin` —
  never calls `env_get("PATH")` at all; the `/bin/` prefix is a literal
  string. `PATH`'s built-in value and the shell's actual command-lookup
  path are unconnected code, so no `export` could ever change where
  commands are found even if the shadowing above didn't exist.

`unset PATH` (or `USER`/`HOME`/`PWD`) still works as an escape hatch: it
removes the shadowed entry via `env_find`, which only ever searches the
custom table (`kmain.mx:2695`-`2705`), freeing the wasted slot — though
the read behavior it was hiding was never affected either way.

## Line editing

Independent of the command table above, `key_event` (the input handler
behind both the keyboard IRQ and the serial console — see "After Enter"
above) supports Backspace line editing and command history: a ring buffer
of the last 8 lines (`g_history`, 8 slots x 80 bytes, `kmain.mx:78`),
recalled with Up/Down arrows once `key_event` has decoded the `0xE0`
extended-scancode prefix (`kmain.mx:3697`-`3699`) that PS/2 sends before
arrow-key scancodes (`kmain.mx:3701`-`3710`).

On Enter, only a non-empty line gets appended to the ring, via `hist_store`
(`kmain.mx:987`-`991`) — an empty Enter press is never recorded
(`kmain.mx:3726`-`3728`). Nothing de-duplicates: entering the same command
twice in a row stores it twice, each in its own slot. Storage always writes
slot `g_hist_n % 8` and increments the total-commands counter `g_hist_n`
(`kmain.mx:21`), so once more than 8 commands have been entered, each new
one silently overwrites the oldest surviving slot.

`g_hist_nav` (`kmain.mx:22`) tracks how far back the currently-displayed
line has been recalled: `0` means the live line the user is typing, `k`
means the `k`-th most recent stored command. Up arrow calls `history_up`
(`kmain.mx:1015`-`1022`), which increments `g_hist_nav` (capped at
`min(g_hist_n, 8)`, so it stops at the oldest command still in the ring)
and replaces the input line with that slot's text. Down arrow calls
`history_down` (`kmain.mx:1024`-`1032`): above `1` it steps back toward
more recent commands the same way; at `1` or already `0` it resets
`g_hist_nav` to `0` and clears the line to blank — so pressing Down
repeatedly past the newest recalled command, or while already on a blank
live line, just keeps clearing it. Typing any character also resets
`g_hist_nav` to `0` (`kmain.mx:3753`), so editing a recalled command and
pressing Enter stores the edited text as a new entry rather than modifying
history in place.
