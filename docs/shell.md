# Shell command reference

Every command line goes through `run_command` (`kmain.mx:2095`), which expands
`$VAR` references via `expand_vars` (`kmain.mx:1985`) and then dispatches on an
`if streq(cmd, "...")` / `if starts_with(cmd, "...")` chain in
`run_command_impl` (`kmain.mx:2100`-`2602`). This table lists every command
recognized there, in source order, with the line where its match starts.

Commands marked **disk** call `fs_guard()` (`kmain.mx:1743`) first, which
refuses with `no disk (boot with -hda disk.img)` or
`bad filesystem (host: python kernel/mkfs.py disk.img)` if no disk image is
attached or its filesystem didn't parse.

| Command | Disk? | Behavior | Source |
|---|---|---|---|
| `help` | | Prints the five command-group summary lines shown below. | `kmain.mx:2104` |
| `readme` | | Shows the multiboot module text passed in by the bootloader (`show_module`, `kmain.mx:841`). | `kmain.mx:2119` |
| `mem` | | Sums the multiboot memory map's usable (type 1) regions and prints total RAM in MB. | `kmain.mx:2123`, `kmain.mx:917` |
| `mods` | | Lists the multiboot modules loaded at boot, with sizes. | `kmain.mx:2127`, `kmain.mx:945` |
| `net` | | Runs DHCP over the RTL8139 NIC to lease an IP (`net_dhcp`, `net/netapp.mx:46`). | `kmain.mx:2131` |
| `httpd` | | Serves an HTML page on TCP port 80 (`net_httpd`, `net/netapp.mx:176`). | `kmain.mx:2135` |
| `pwd` | | Prints the current working directory path (`g_cwdpath`). | `kmain.mx:2139` |
| `cd [dir]` | disk | Changes directory; no argument goes to `/home/<user>`. Errors: `no such directory`, `not a directory`. | `kmain.mx:2144` |
| `ls [dir]` | disk | Lists entries in the current directory (or `dir`): type (`d`/`-`), octal mode, name, size, owning uid. Prints `(empty)` if nothing matches. | `kmain.mx:2170` |
| `mkdir <dir>` | disk | Creates a directory. Errors: `parent directory does not exist`, `already exists`. | `kmain.mx:2222` |
| `rmdir <dir>` | disk | Removes an empty directory. Errors: `no such directory`, `not a directory`, `directory not empty`. | `kmain.mx:2235` |
| `cat <file>` | disk | Reads the file into `FILEBUF` (`0x00810000`) and prints its contents. Errors: `not found: <name>`, `cat: is a directory`. | `kmain.mx:2258` |
| `write <file> <text>` | disk | Appends `<text>` as a line to `<file>`, creating it (in the resolved parent directory) if it doesn't exist. Silent on success. Errors: `usage: write <name> <text>`, `write: is a directory`, `permission denied`, `write: parent directory does not exist`, `file full (max 64 KB)`. | `kmain.mx:2278` |
| `rm <file>` | disk | Removes a file. Errors: `not found: <name>`, `rm: is a directory (use rmdir)`, `permission denied`. | `kmain.mx:2319` |
| `run <file>` | disk | Reads `<file>` and runs each line as a shell command (`run_file`, `kmain.mx:894`). Refuses to nest (`run: nested run not allowed`) because a script's `run` would clobber the shared `FILEBUF`. | `kmain.mx:2342` |
| `exec <file>` | disk | Loads a compiled Mort program from `<file>` into the fixed program window at `0x00A00000` and jumps to it (`exec_file`, `kmain.mx:1892`); the program talks back to the kernel via `int 0x80` syscalls. Errors: `not found: <name>`, `empty program`. | `kmain.mx:2347` |
| `whoami` | | Prints the current username and uid. | `kmain.mx:2352` |
| `export NAME=value` | | Sets a shell environment variable (`env_set`). Usage error if there's no `=`. Custom variables are capped at 8 slots (`g_env_name`/`g_env_val`, `kmain.mx:36`-`37`); a 9th *new* variable name is silently dropped with no error (`env_set`'s `g_env_count >= 8` check, `kmain.mx:1941`-`1943`) — re-`export`-ing an *existing* name still updates its value past the cap, since that path skips the count check. | `kmain.mx:2362` |
| `env` | | Prints `USER`, `HOME`, `PATH`, `PWD`, then every variable set via `export`. | `kmain.mx:2380` |
| `unset NAME` | | Removes a variable set via `export` (no-op if unset). | `kmain.mx:2392` |
| `su [user]` | | Prompts for a password and, if it matches, switches the session uid/username to `user` (default `root`). Error: `su: no such user`, `su: authentication failure`. | `kmain.mx:2406` |
| `sudo <cmd>` | | Prompts for the current user's password, then runs `<cmd>` once with uid 0 if it matches. No-op prompt if already root. Error: `sudo: authentication failure`. | `kmain.mx:2431` |
| `passwd` | | Prompts for a new password and updates it for the current account, for this boot session only (not persisted to disk). | `kmain.mx:2457` |
| `chmod <octal> <path>` | disk | Sets a file/directory's octal permission bits. Only the owner or root may do this (`chmod: not permitted`). Error: `usage: chmod <octal> <path>`, `chmod: not found`. | `kmain.mx:2471` |
| `chown <uid> <path>` | disk | Changes a file/directory's owning uid; root only (`chown: not permitted (root only)`). Error: `usage: chown <uid> <path>`, `chown: not found`. | `kmain.mx:2504` |
| `reboot` / `restart` | | Reboots the machine (`reboot`, `kmain.mx:1024`). | `kmain.mx:2537`, `kmain.mx:2541` |
| `shutdown` / `poweroff` | | Powers the machine off — ACPI on emulators, or a halt with an "It is now safe..." message on bare metal (`poweroff`, `kmain.mx:3241`). | `kmain.mx:2545`, `kmain.mx:2549` |
| `power` | | Opens the `F12` power menu (Lock/Sleep/Restart/Shut down) from the shell (`open_power_menu`, `kmain.mx:3145`). In VGA text mode it silently does nothing — `open_power_menu` returns immediately `if !g_gfx`, no message printed (`kmain.mx:3146`-`3148`). | `kmain.mx:2553` |
| `memtest` | | Runs a RAM test (`memtest`, `kmain.mx:971`). | `kmain.mx:2557` |
| `lock` | | Shows the password lock screen (`open_lock`, `kmain.mx:3199`). In VGA text mode it prints `lock needs the graphical desktop` instead of opening the screen (`kmain.mx:3200`-`3203`). | `kmain.mx:2561` |
| `sleep` | | Blanks the display until a keypress (`open_sleep`, `kmain.mx:3229`). In VGA text mode it prints `sleep needs the graphical desktop` instead of blanking (`kmain.mx:3230`-`3233`). | `kmain.mx:2565` |
| `crash` | | Executes `ud2` to raise a #UD exception, to demo the exception-reporting handlers. | `kmain.mx:2569` |
| `uptime` | | Prints seconds since boot, from the PIT tick counter (`g_ticks / 100`, ~100 Hz). | `kmain.mx:2573` |
| `clear` | | Clears the screen and resets the cursor row. | `kmain.mx:2581` |
| `about` | | Prints a one-line description of MORT OS. | `kmain.mx:2586` |
| `echo <text>` | | Prints `<text>` (everything after `echo `). | `kmain.mx:2591` |
| *(anything else)* | | Tried as a program name on `$PATH` (`try_exec_path`, `kmain.mx:2056`): as typed, as `/bin/<name>`, as `<name>.bin`, then `/bin/<name>.bin`, each checked with `exec_if_program`. Falls through to `unknown command` if none match. | `kmain.mx:2596` |
| *(empty line)* | | No-op. | `kmain.mx:2101` |

## `$VAR` expansion

Every command — typed at the prompt, run from a script via `run`, or the
tail of a `sudo`/`su` invocation — is passed through `expand_vars`
(`kmain.mx:1985`) before dispatch, so `echo $USER` or `cd $HOME` work
anywhere a command line is accepted.

## Line editing

Independent of the command table above, the input loop that builds `cmd`
supports Backspace line editing and command history: a ring buffer of the
last 8 lines (`g_history`, `kmain.mx:754`-`758`), recalled with Up/Down
arrows once the keyboard handler has decoded the `0xE0` extended-scancode
prefix (`kmain.mx:3520`) that PS/2 sends before arrow-key scancodes.
