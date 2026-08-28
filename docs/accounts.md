# Users, login, and file permissions

MORT OS has a two-account user model, a password prompt, and Unix-style
owner/mode bits on every MortFS entry. This doc covers what that model
actually is in the source: where accounts come from, what "logging in" means
here, and — the part most worth knowing — exactly which permission bits the
kernel enforces and which it only stores and displays.

For the per-command syntax of `su`/`sudo`/`passwd`/`chmod`/`chown`, see
[`docs/shell.md`](shell.md); this doc is the model behind them.

## The account table

Accounts live entirely in RAM, in four parallel globals declared at
`kmain.mx:25`-`31`:

| Global | What it holds |
|---|---|
| `g_uid` | the current session's user id (`kmain.mx:25`) |
| `g_username` | the current session's name, 24 bytes (`kmain.mx:27`) |
| `g_acct_name` | 8 slots x 24 bytes of account names (`kmain.mx:29`) |
| `g_acct_uid` | each slot's uid (`kmain.mx:30`) |
| `g_acct_hash` | each slot's password hash (`kmain.mx:31`) |

`acct_init()` (`kmain.mx:2904`-`2908`) fills exactly two of the eight slots on
every boot:

| User | uid | Password |
|---|---|---|
| `root` | 0 | `toor` |
| `mortuex` | 1 | `mort` |

Passwords are stored as a djb2 hash (`hash_pw`, `kmain.mx:2864`-`2872`) rather
than plaintext. The source is explicit that this is a toy-`/etc/passwd`-grade
measure, not a cryptographic one (`kmain.mx:2858`-`2860`).

Three consequences of the table being in-memory and fixed:

- **Nothing persists.** `passwd` (`kmain.mx:2461`-`2474`) writes the new hash
  into `g_acct_hash` and prints `password updated (this session)` — the next
  boot re-runs `acct_init()` and restores `toor`/`mort`.
- **There is no way to add an account.** `acct_add` (`kmain.mx:2874`-`2889`)
  exists and enforces the 8-slot cap, but the only caller is `acct_init()`;
  no shell command reaches it. So `su <name>` can only ever target `root` or
  `mortuex` — anything else fails `acct_find`'s missing-name sentinel (`64`,
  `kmain.mx:2891`-`2901`) and prints `su: no such user`.
- **A uid need not have an account.** `chown` writes the raw number you type
  into the entry (`kmain.mx:2537`), with no check that any account has that
  uid.

## Login is automatic

There is no login prompt. `kmain()` calls, in this order
(`kmain.mx:3607`-`3610`):

1. `acct_init()` — build the account table.
2. `ensure_home()` (`kmain.mx:3000`-`3013`) — create `/home/mortuex` and chown
   it to uid 1. This runs *before* login, so it runs as uid 0 (`g_uid`'s
   initial value, `kmain.mx:25`), which is what lets it create a directory
   inside root-owned `/home`.
3. `login_default()` (`kmain.mx:2910`-`2913`) — set `g_uid = 1` and
   `g_username = "mortuex"`. That is the whole of "logging in".
4. `cwd_init()` (`kmain.mx:2916`-`2931`) — start the shell in
   `/home/<user>`, falling back to `/` if that directory doesn't exist or
   isn't a directory.

The same before-login-runs-as-root ordering is why the standard layout
(`fs_ensure_layout`, `kmain.mx:1617`-`1625`: `/bin /etc /home /var`) and the
`0755` re-mode of seeded programs (`fs_populate_bin`, `kmain.mx:1652`-`1653`)
are root-owned on a fresh disk — both run at `kmain.mx:3605`-`3606`, ahead of
`acct_init()`.

## Where the current user shows up

| Surface | Source |
|---|---|
| The shell prompt (`~ $` in `/home/<user>`) | `draw_prompt`, `kmain.mx:709`-`727` |
| `whoami` — name and uid | `kmain.mx:2356`-`2365` |
| `$USER`, and `$HOME` as `/home/<user>` | `env_get`, `kmain.mx:1963`-`1970` |
| `ls`'s trailing `uid N` column | `kmain.mx:2212`-`2213` |
| The home launcher's `welcome, <user>` line | `draw_launcher`, `kmain.mx:3342`-`3345` |
| The lock screen's password check | `lock_ok`, `kmain.mx:3216`-`3223` |

The lock screen is worth calling out: `lock_ok` hashes what you typed and
compares it against **the current user's** account hash, not a fixed string.
So the lock password is `mort` for the auto-logged-in user — but after
`su root`, locking the screen requires `toor`, and after a `passwd` it
requires whatever you just set for this session.

Password entry everywhere (`su`, `sudo`, `passwd`, `kmain.mx:2425`/`2448`/
`2466`) goes through `kread_line(buf, mask)` (`kmain.mx:2935`-`2973`), which
polls the keyboard directly and echoes `*` per character when `mask` is true.
The polling is deliberate: interrupts are off inside a shell command, so the
IRQ1 keyboard path isn't running (`kmain.mx:2933`-`2934`).

## Switching users

- `su [user]` (`kmain.mx:2410`-`2434`) prompts, and on a hash match assigns
  `g_uid`/`g_username` from the account slot. There is no session stack — `su`
  is a one-way switch, and there is no `exit` command to switch back (the
  command table in [`docs/shell.md`](shell.md) has no such entry); use
  `su mortuex` to go back the other way.
- `sudo <cmd>` (`kmain.mx:2435`-`2460`) prompts for the *current* user's
  password, sets `g_uid = 0` for exactly one `run_command` call, then restores
  the saved uid (`kmain.mx:2451`-`2454`). If you are already root it runs the
  command with no prompt at all.

## What the permission bits actually do

Every MortFS v2 entry carries an owner and a mode in its metadata bytes —
`uid` at offset 42, `mode` at offset 44, read back through `fs_uid`/`fs_mode`
(`kmain.mx:1271`-`1272`; the full layout is documented at
`kmain.mx:1261`-`1267`). New entries are stamped with the creating user's uid
and a default mode by `fs_set_meta` (`kmain.mx:1578`, `kmain.mx:1286`-`1293`):
`0644` for files, `0755` for directories (`kmain.mx:1560`-`1564`).

All enforcement goes through one function, `can_write(uid, mode)`
(`kmain.mx:2978`-`2986`):

- root (`g_uid == 0`) may always write;
- the owner needs the owner-write bit (`0200`);
- anyone else needs the other-write bit (`0002`).

Group bits are stored and printed but never consulted — there is no group id
anywhere in the source. For directories, `dir_owner`/`dir_mode`
(`kmain.mx:2989`-`2996`) supply root's implicit values (root-owned, `0755`),
since the filesystem root is not a table entry.

`can_write` has exactly three call sites:

| Operation | Check | Source |
|---|---|---|
| Creating any entry | write permission on the **parent directory** | `fs_create_full`, `kmain.mx:1540`-`1544` |
| `write` to an existing file | write permission on the file | `kmain.mx:2300`-`2304` |
| `rm` | write permission on the file | `kmain.mx:2338`-`2342` |

All three print `permission denied` and abort.

Two other commands do their own, separate checks:

- `chmod` — owner or root only (`kmain.mx:2499`-`2503`), else
  `chmod: not permitted`.
- `chown` — root only (`kmain.mx:2510`-`2514`), else
  `chown: not permitted (root only)`.

### What is not checked

This is the practical part. Outside the five checks above, the mode bits are
inert:

- **Read bits are never consulted.** `cat` (`kmain.mx:2262`-`2281`) reads any
  file it can resolve, whatever its mode or owner.
- **Execute bits are never consulted.** `exec_file` (`kmain.mx:1896`-`1924`)
  loads and jumps to any file that resolves and is non-empty. `fs_populate_bin`
  marks seeded programs `0755` (`kmain.mx:1653`), but that mode is decoration —
  a `0600` file in `/bin` runs just as well.
- **`rmdir` checks nothing.** Unlike `rm`, `rmdir` (`kmain.mx:2239`-`2261`)
  goes straight from "is it an empty directory?" to freeing the slot, with no
  `can_write` call — so any user can remove any empty directory they can name,
  including a root-owned one.

None of this is a hole to patch from a doc; it is what the five checks above
add up to today, and it is worth knowing before you assume a mode bit
protects something.
