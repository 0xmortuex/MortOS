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
| `help` | | Prints the five command-group summary lines shown below. | `kmain.mx:2108` |
| `readme` | | Shows the multiboot module text passed in by the bootloader (`show_module`, `kmain.mx:841`). | `kmain.mx:2123` |
| `mem` | | Sums the multiboot memory map's usable (type 1) regions and prints total RAM in MB. | `kmain.mx:2127`, `kmain.mx:917` |
| `mods` | | Lists the multiboot modules loaded at boot, with sizes. | `kmain.mx:2131`, `kmain.mx:945` |
| `net` | | Runs DHCP over the RTL8139 NIC to lease an IP (`net_dhcp`, `net/netapp.mx:46`). | `kmain.mx:2135` |
| `httpd` | | Serves an HTML page on TCP port 80 (`net_httpd`, `net/netapp.mx:176`). | `kmain.mx:2139` |
| `pwd` | | Prints the current working directory path (`g_cwdpath`). | `kmain.mx:2143` |
| `cd [dir]` | disk | Changes directory; no argument goes to `/home/<user>`. Errors: `no such directory`, `not a directory`. | `kmain.mx:2148` |
| `ls [dir]` | disk | Lists entries in the current directory (or `dir`): type (`d`/`-`), octal mode, name, size, owning uid. Prints `(empty)` if nothing matches. | `kmain.mx:2174` |
| `mkdir <dir>` | disk | Creates a directory. Errors: `parent directory does not exist`, `already exists`. | `kmain.mx:2226` |
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
