# Shell command reference

Every command line goes through `run_command` (`kmain.mx:2099`), which expands
`$VAR` references via `expand_vars` (`kmain.mx:1989`) and then dispatches on an
`if streq(cmd, "...")` / `if starts_with(cmd, "...")` chain in
`run_command_impl` (`kmain.mx:2104`-`2606`). This table lists every command
recognized there, in source order, with the line where its match starts.

Commands marked **disk** call `fs_guard()` (`kmain.mx:1747`) first, which
refuses with `no disk (boot with -hda disk.img)` or
`bad filesystem (host: python kernel/mkfs.py disk.img)` if no disk image is
attached or its filesystem didn't parse.

| Command | Disk? | Behavior | Source |
|---|---|---|---|
| `help` | | Prints six lines (`kmain.mx:2109`-`2120`): one unlabeled bare list of command names (`help clear about echo uptime crash readme mem`), then five labeled groups — `files:`, `net:`, `power:`, `users:`, `env:`. `mods` (below) is the one command in this whole table that appears in none of the six lines, so `help` alone won't tell you it exists. | `kmain.mx:2108` |
| `readme` | | Shows the multiboot module text passed in by the bootloader (`show_module`, `kmain.mx:841`). | `kmain.mx:2123` |
| `mem` | | Sums the multiboot memory map's usable (type 1) regions and prints total RAM in MB. | `kmain.mx:2127`, `kmain.mx:917` |
| `mods` | | Lists the multiboot modules loaded at boot, with sizes. | `kmain.mx:2131`, `kmain.mx:945` |
| `net` | | Runs DHCP over the RTL8139 NIC to lease an IP (`net_dhcp`, `net/netapp.mx:46`). | `kmain.mx:2135` |
| `httpd` | | Serves an HTML page on TCP port 80 (`net_httpd`, `net/netapp.mx:176`). | `kmain.mx:2139` |
| `pwd` | | Prints the current working directory path (`g_cwdpath`). | `kmain.mx:2143` |
| `cd [dir]` | disk | Changes directory; no argument goes to `/home/<user>`. Errors: `no such directory`, `not a directory`. Rebuilds `g_cwdpath` for `pwd` via `path_of`, which has no bound on path length, and the next prompt redraw copies it into its own smaller, also-unbounded buffer — see [`docs/fs-design.md`](fs-design.md)'s directory section for both concrete overflows. | `kmain.mx:2148` |
| `ls [dir]` | disk | Lists entries in the current directory (or `dir`): type (`d`/`-`), octal mode, name, size, owning uid. Prints `(empty)` if nothing matches. | `kmain.mx:2174` |
| `mkdir <dir>` | disk | Creates a directory. Errors: `parent directory does not exist`, `already exists` — plus a mislabeled second message for several other failures, see below. | `kmain.mx:2226` |
| `rmdir <dir>` | disk | Removes an empty directory. Errors: `no such directory`, `not a directory`, `directory not empty`. | `kmain.mx:2239` |
| `cat <file>` | disk | Reads the file into `FILEBUF` (`0x00810000`) and prints its contents. Errors: `not found: <name>`, `cat: is a directory`. | `kmain.mx:2262` |
| `write <file> <text>` | disk | Appends `<text>` as a line to `<file>`, creating it (in the resolved parent directory) if it doesn't exist. Silent on success. Errors: `usage: write <name> <text>`, `write: is a directory`, `permission denied`, `write: parent directory does not exist`, `file full (max 64 KB)`. | `kmain.mx:2282` |
| `rm <file>` | disk | Removes a file. Errors: `not found: <name>`, `rm: is a directory (use rmdir)`, `permission denied`. | `kmain.mx:2323` |
| `run <file>` | disk | Reads `<file>` and runs each line as a shell command (`run_file`, `kmain.mx:894`). Refuses to nest (`run: nested run not allowed`) because a script's `run` would clobber the shared `FILEBUF`. | `kmain.mx:2346` |
| `exec <file>` | disk | Loads a compiled Mort program from `<file>` into the fixed program window at `0x00A00000` and jumps to it (`exec_file`, `kmain.mx:1896`); the program talks back to the kernel via `int 0x80` syscalls. Errors: `not found: <name>`, `empty program`. | `kmain.mx:2351` |
| `whoami` | | Prints the current username and uid. | `kmain.mx:2356` |
| `export NAME=value` | | Sets a shell environment variable (`env_set`). Usage error if there's no `=`. Custom variables are capped at 8 slots (`g_env_name`/`g_env_val`, `kmain.mx:36`-`37`); a 9th *new* variable name is silently dropped with no error (`env_set`'s `g_env_count >= 8` check, `kmain.mx:1945`-`1947`) — re-`export`-ing an *existing* name still updates its value past the cap, since that path skips the count check. | `kmain.mx:2366` |
| `env` | | Prints `USER`, `HOME`, `PATH`, `PWD`, then every variable set via `export`. | `kmain.mx:2384` |
| `unset NAME` | | Removes a variable set via `export` (no-op if unset). | `kmain.mx:2396` |
| `su [user]` | | Prompts for a password and, if it matches, switches the session uid/username to `user` (default `root`). Error: `su: no such user`, `su: authentication failure`. | `kmain.mx:2410` |
| `sudo <cmd>` | | Prompts for the current user's password, then runs `<cmd>` once with uid 0 if it matches. No-op prompt if already root. Error: `sudo: authentication failure`. | `kmain.mx:2435` |
| `passwd` | | Prompts for a new password and updates it for the current account, for this boot session only (not persisted to disk). | `kmain.mx:2461` |
| `chmod <octal> <path>` | disk | Sets a file/directory's octal permission bits. Only the owner or root may do this (`chmod: not permitted`). Error: `usage: chmod <octal> <path>`, `chmod: not found`. | `kmain.mx:2475` |
| `chown <uid> <path>` | disk | Changes a file/directory's owning uid; root only (`chown: not permitted (root only)`). Error: `usage: chown <uid> <path>`, `chown: not found`. | `kmain.mx:2508` |
| `reboot` / `restart` | | Reboots the machine (`reboot`, `kmain.mx:1024`-`1029`) by pulsing the 8042 keyboard controller's reset line — `outb(0x64, 0xFE)` (`kmain.mx:1025`), the pre-ACPI trick of asking the keyboard controller to pulse output line 0, which is wired to the CPU's reset pin on PC-compatible hardware — then falls into a `hlt` loop (`kmain.mx:1026`-`1028`) in case the reset doesn't land immediately. | `kmain.mx:2541`, `kmain.mx:2545` |
| `shutdown` / `poweroff` | | Powers the machine off (`poweroff`, `kmain.mx:3245`-`3263`): prints "It is now safe to turn off your computer.", then writes three emulator-specific ACPI shutdown values in sequence — `outw(0x604, 0x2000)`, `outw(0xB004, 0x2000)`, `outw(0x4004, 0x3400)` (`kmain.mx:3256`-`3258`), labeled in source as QEMU/Bochs/VirtualBox's respective magic ports in that order — then falls into a `cli`+`hlt` loop (`kmain.mx:3259`-`3262`) for bare metal, where none of those port writes do anything. | `kmain.mx:2549`, `kmain.mx:2553` |
| `power` | | Opens the `F12` power menu (Lock/Sleep/Restart/Shut down) from the shell (`open_power_menu`, `kmain.mx:3149`). In VGA text mode it silently does nothing — `open_power_menu` returns immediately `if !g_gfx`, no message printed (`kmain.mx:3150`-`3152`). | `kmain.mx:2557` |
| `memtest` | | Not a physical RAM test: a smoke test for the `kmalloc`/`kfree` heap allocator (`memtest`, `kmain.mx:971-1021`) — allocate two blocks, verify their writes don't clobber each other, free and reallocate to confirm first-fit reuse, free both to confirm coalescing, then print heap base/size and a PASS/FAIL line. See [`docs/memory-map.md`](memory-map.md)'s heap-allocator section for the allocator design this exercises. | `kmain.mx:2561` |
| `lock` | | Shows the password lock screen (`open_lock`, `kmain.mx:3203`). In VGA text mode it prints `lock needs the graphical desktop` instead of opening the screen (`kmain.mx:3204`-`3207`). | `kmain.mx:2565` |
| `sleep` | | Blanks the display until a keypress (`open_sleep`, `kmain.mx:3233`). In VGA text mode it prints `sleep needs the graphical desktop` instead of blanking (`kmain.mx:3234`-`3237`). | `kmain.mx:2569` |
| `crash` | | Executes `ud2` to raise a #UD exception, to demo the exception-reporting handlers. | `kmain.mx:2573` |
| `uptime` | | Prints seconds since boot, from the PIT tick counter (`g_ticks / 100`, ~100 Hz). | `kmain.mx:2577` |
| `clear` | | Clears the screen and resets the cursor row. | `kmain.mx:2585` |
| `about` | | Prints a one-line description of MORT OS. | `kmain.mx:2590` |
| `echo <text>` | | Prints `<text>` (everything after `echo `). | `kmain.mx:2595` |
| *(anything else)* | | Tried as a program name on `$PATH` (`try_exec_path`, `kmain.mx:2060`): as typed, as `/bin/<name>`, as `<name>.bin`, then `/bin/<name>.bin`, each checked with `exec_if_program`. Falls through to `unknown command` if none match. | `kmain.mx:2600` |
| *(empty line)* | | No-op. | `kmain.mx:2105` |

## `mkdir`'s "parent directory does not exist" is often a lie

`fs_mkdir` (`kmain.mx:1597`-`1607`) returns a single `u32` with three
meanings overloaded onto it: `65` for "already exists", a resolved slot
index on success, and `64` for every failure case. The `mkdir` dispatch
(`kmain.mx:2226`-`2238`) only distinguishes two of those:

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

`64` is accurate when `fs_parent_of` (`kmain.mx:1448`-`1490`) itself
returns `64` because the parent component doesn't resolve or isn't a
directory (`kmain.mx:1481`-`1487`) — `fs_mkdir` passes that straight
through (`kmain.mx:1600`-`1602`). But once the parent *does* resolve,
`fs_mkdir` hands it to `fs_create_full` (`kmain.mx:1533`-`1584`), whose own
four failure branches — name too long (`kmain.mx:1535`-`1538`), permission
denied (`kmain.mx:1540`-`1543`), file table full (`kmain.mx:1546`-`1549`),
and disk full (`kmain.mx:1568`-`1572`) — all `return 64` too, each after
printing its *own*, correct error message first. `fs_mkdir` passes that
`64` straight through as well (`kmain.mx:1606`), so the `mkdir` dispatch
can't tell the two cases apart: it always treats `64` as "parent missing"
and prints that message *in addition to* whichever real message
`fs_create_full` already printed. A concrete, reachable case: `/etc` (one
of the four directories `fs_ensure_layout` seeds at boot, `kmain.mx:1617`-
`1625`) is created while `g_uid` is still `0`, before `login_default()`
switches the session to the normal user (see
[`docs/accounts.md`](accounts.md#the-seeded-hellotxt-belongs-to-root-not-to-you)
for the same root-owned-at-boot pattern), so it ends up root-owned, mode
`0755` — owner-write only, no `0002` other-write bit (`can_write`,
`kmain.mx:2978`-`2986`). `cd /etc` as the default `mortuex` user, then
`mkdir foo`, prints `permission denied` immediately followed by the false
`mkdir: parent directory does not exist`, even though `/etc` resolved
just fine. The same double message fires for a 24+ character name and for a full
64-entry file table.

Contrast with `write`'s otherwise-identical create path
(`kmain.mx:2306`-`2316`): it checks `fs_parent_of`'s result on its own
first and only *then* calls `fs_create_full`, trusting that call's own
error message with no second message tacked on (`kmain.mx:2314`-`2315`,
`// prints its own error`) — the asymmetry is in `fs_mkdir`'s wrapper, not
in `fs_create_full` itself. See `BACKLOG.md`'s "Code follow-ups" section
for the one-line fix (give `fs_mkdir` its own sentinel for "parent
missing" distinct from `fs_create_full`'s generic failure) a human can
make with a local QEMU boot test.

## After Enter: feed, redraw, or leave it alone

`run_command` (`kmain.mx:2099`-`2102`) returns whatever `run_command_impl`
returns, and `on_key`'s Enter handler (`kmain.mx:3551`-`3568`) uses that
`bool` — plus `g_overlay` — to decide what happens to the screen next:

- **A command opened an overlay** (`g_overlay != 0` after the call, e.g.
  `power`/`lock`/`sleep` in graphics mode): `on_key` returns immediately
  (`kmain.mx:3558`-`3560`) with no `feed()` and no prompt redraw. The
  overlay repaints the whole screen itself, so the terminal's `g_row`/
  `g_col` are left exactly as they were and the prompt reappears unchanged
  once the overlay closes.
- **Otherwise**, the returned `bool` decides whether `feed()`
  (`kmain.mx:596`-`602`) runs before the next prompt is drawn
  (`kmain.mx:3561`-`3563`). Despite the name suggesting a general
  "did this command finish cleanly" signal, it has exactly one real use:
  `clear` (`kmain.mx:2585`-`2589`) is the *only* branch in all of
  `run_command_impl`'s roughly 45-way dispatch that returns `true` —
  confirmed by grep, there is exactly one `return true` in the whole
  function (`kmain.mx:2588`), and every other path, including every error
  message, `exec`, `run`, `su`/`sudo` failures, and even the unreachable
  lines after `reboot`/`poweroff`'s `hlt` loops, returns `false`. `clear`
  returning `true` suppresses the post-command `feed()` specifically
  because `clear_screen()` already blanked the console and reset `g_row`
  to `0` itself (`kmain.mx:2586`-`2587`); an unconditional `feed()` right
  after would scroll the freshly blanked screen by one line and misplace
  the next prompt at row 1 instead of row 0. Every other command relies on
  that same `feed()` call to both separate its own output from the next
  prompt and perform the actual line-advance/scroll.

## `$VAR` expansion

Every command — typed at the prompt, run from a script via `run`, or the
tail of a `sudo`/`su` invocation — is passed through `expand_vars`
(`kmain.mx:1985`) before dispatch, so `echo $USER` or `cd $HOME` work
anywhere a command line is accepted.

### `export`ing `USER`, `HOME`, `PATH`, or `PWD` is invisible

`export` (`kmain.mx:2366`-`2383`) has no reserved-name check — it hands
whatever name follows `export ` straight to `env_set`
(`kmain.mx:1942`-`1959`), which has no such check either. But `env_get`
(`kmain.mx:1963`-`1978`), the function every read goes through, tests for
four computed built-ins with `streq` *before* it ever consults the custom
table (`env_find`, `kmain.mx:1930`-`1940`): `USER` and `PWD` return live
kernel state, `PATH` returns the hardcoded literal `"/bin"`
(`kmain.mx:1966`), and `HOME` is rebuilt from the current username
(`kmain.mx:1967`-`1970`). One consequence, not previously documented:

- `export PATH=/custom` (or `USER=`/`HOME=`/`PWD=`) does create a real
  entry in the 8-slot custom-variable table, and does count against the
  cap (`kmain.mx:1946`-`1947`) — it isn't rejected. But every subsequent
  read of `$PATH` (via `expand_vars`) or `env`'s `PATH=` line still calls
  `env_get("PATH")`, which returns `/bin` regardless: the exported value
  is stored but never once read back anywhere in the source.
- `env` (`kmain.mx:2384`-`2395`) prints the four built-ins first, then
  loops over every custom entry and prints it by name
  (`kmain.mx:2390`-`2392`) — through the same `env_get`. So a `PATH`
  entry that exists only because it was exported still resolves through
  the built-in check, and `env` shows `PATH=/bin` twice, identically,
  rather than showing what was actually exported.
- Separately, `try_exec_path` (`kmain.mx:2060`-`2096`) — the code that
  turns an unrecognized command into `/bin/<name>` or `/bin/<name>.bin`
  (`kmain.mx:2081`, `kmain.mx:2090`) — never calls `env_get("PATH")` at
  all; the `/bin/` prefix is a literal string on both lines. `PATH`'s
  built-in value and the shell's actual command-lookup path are
  unconnected code, so no `export` could ever change where commands are
  found even if the shadowing above didn't exist.

`unset PATH` (or `USER`/`HOME`/`PWD`) still works as an escape hatch: it
removes the shadowed entry via `env_find`, which only ever searches the
custom table (`kmain.mx:1930`-`1940`), freeing the wasted slot — though
the read behavior it was hiding was never affected either way.

## Line editing

Independent of the command table above, the input loop that builds `cmd`
supports Backspace line editing and command history: a ring buffer of the
last 8 lines (`g_history`, 8 slots x 80 bytes, `kmain.mx:71`), recalled with
Up/Down arrows once the keyboard handler has decoded the `0xE0`
extended-scancode prefix (`kmain.mx:3524`) that PS/2 sends before arrow-key
scancodes.

On Enter, only a non-empty line gets appended to the ring, via `hist_store`
(`kmain.mx:757`-`761`) — an empty Enter press is never recorded
(`kmain.mx:3553`-`3554`). Nothing de-duplicates: entering the same command
twice in a row stores it twice, each in its own slot. Storage always writes
slot `g_hist_n % 8` and increments the total-commands counter `g_hist_n`
(`kmain.mx:21`), so once more than 8 commands have been entered, each new
one silently overwrites the oldest surviving slot.

`g_hist_nav` (`kmain.mx:22`) tracks how far back the currently-displayed
line has been recalled: `0` means the live line the user is typing, `k`
means the `k`-th most recent stored command. Up arrow calls `history_up`
(`kmain.mx:785`-`792`), which increments `g_hist_nav` (capped at
`min(g_hist_n, 8)`, so it stops at the oldest command still in the ring)
and replaces the input line with that slot's text. Down arrow calls
`history_down` (`kmain.mx:794`-`802`): above `1` it steps back toward more
recent commands the same way; at `1` or already `0` it resets
`g_hist_nav` to `0` and clears the line to blank — so pressing Down
repeatedly past the newest recalled command, or while already on a blank
live line, just keeps clearing it. Typing any character also resets
`g_hist_nav` to `0` (`kmain.mx:3583`), so editing a recalled command and
pressing Enter stores the edited text as a new entry rather than modifying
history in place.
