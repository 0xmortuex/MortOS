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

`acct_init()` (`kmain.mx:3534`-`3538`) fills exactly two of the eight slots on
every boot:

| User | uid | Password |
|---|---|---|
| `root` | 0 | `toor` |
| `mortuex` | 1 | `mort` |

Passwords are stored as a djb2 hash (`hash_pw`, `kmain.mx:3494`-`3502`) rather
than plaintext. The source is explicit that this is a toy-`/etc/passwd`-grade
measure, not a cryptographic one (`kmain.mx:3488`-`3490`).

Three consequences of the table being in-memory and fixed:

- **Nothing persists.** `passwd` (`kmain.mx:3281`-`3294`) writes the new hash
  into `g_acct_hash` and prints `password updated (this session)` — the next
  boot re-runs `acct_init()` and restores `toor`/`mort`.
- **There is no way to add an account.** `acct_add` (`kmain.mx:3504`-`3519`)
  exists and enforces the 8-slot cap, but the only caller is `acct_init()`;
  no shell command reaches it. So `su <name>` can only ever target `root` or
  `mortuex` — anything else fails `acct_find`'s missing-name sentinel (`64`,
  `kmain.mx:3521`-`3531`) and prints `su: no such user`.
- **A uid need not have an account.** `chown` writes the raw number you type
  into the entry (`kmain.mx:3362`), with no check that any account has that
  uid.

## Login is automatic

There is no login prompt. `kmain()` calls, in this order
(`kmain.mx:3781`-`3784`):

1. `acct_init()` — build the account table.
2. `ensure_home()` (`kmain.mx:3629`-`3642`) — create `/home/mortuex` and chown
   it to uid 1. This runs *before* login, so it runs as uid 0 (`g_uid`'s
   initial value, `kmain.mx:25`), which is what lets it create a directory
   inside root-owned `/home`.
3. `login_default()` (`kmain.mx:3540`-`3543`) — set `g_uid = 1` and
   `g_username = "mortuex"`. That is the whole of "logging in".
4. `cwd_init()` (`kmain.mx:3546`-`3561`) — start the shell in
   `/home/<user>`, falling back to `/` if that directory doesn't exist or
   isn't a directory.

The same before-login-runs-as-root ordering is why the standard layout
(`fs_ensure_layout`, `kmain.mx:1901`-`1909`: `/bin /etc /home /var`) and the
`0755` re-mode of seeded programs (`fs_populate_bin`, `kmain.mx:1936`-`1937`)
are root-owned on a fresh disk — both run at `kmain.mx:3779`-`3780`, ahead of
`acct_init()`.

## The seeded `hello.txt` belongs to root, not to you

The paragraph above notes that the standard layout and reparented `*.bin`
programs are root-owned on a fresh disk. The seeded `hello.txt` is a sharper
case of the same fact, and one a new user is likely to hit directly.

`mkfs.py`'s `make()` stamps *every* entry it writes — including `hello.txt` —
with uid 0 (root) and mode `0644`
(`struct.pack("<BBBBII", 0, 255, 0, 0, 0o644, 0)`, `mkfs.py:122`-`123`), and
`ensure_disk()` seeds `hello.txt` this way on every fresh disk image
(`build.py:387`-`411`). Unlike the seeded `*.bin` programs, `hello.txt` is
never touched by `fs_populate_bin` — that function only reparents names
ending in `.bin` (`ends_with_bin`, `kmain.mx:1912`-`1920`) — so it stays at
the filesystem root, owned by root, mode `0644`, for the life of the disk
image.

That matters because the default session is `mortuex`, uid 1, not root (see
"Login is automatic" above). Tracing `can_write(uid, mode)`
(`kmain.mx:3607`-`3615`) for `hello.txt`'s stored `uid=0`/`mode=0644` against
`g_uid=1`: the root case (`g_uid == 0`) doesn't apply, the owner case
(`g_uid == uid`) doesn't apply, and `0644`'s other-write bit (`0002`) is
unset — so the check fails. Concretely: `cat hello.txt` and `exec hello.bin`
both work (read and exec are never checked — see "What is not checked"
below), but `write hello.txt <text>` and `rm hello.txt`
(`kmain.mx:3110`, `kmain.mx:3152`) both print `permission denied` for the
default user, until you `su root` first. Files `mortuex` creates itself are
unaffected: `fs_create_full` stamps new entries with the creating session's
own uid (`g_uid`, `kmain.mx:1854`), so anything you create yourself stays
writable and removable by you.

## Where the current user shows up

| Surface | Source |
|---|---|
| The shell prompt (`~ $` in `/home/<user>`) | `draw_prompt`, `kmain.mx:939`-`957` |
| `whoami` — name and uid | `kmain.mx:3176`-`3185` |
| `$USER`, and `$HOME` as `/home/<user>` | `env_get`, `kmain.mx:2728`-`2736` |
| `ls`'s trailing `uid N` column | `kmain.mx:3015`-`3016` |
| The lock screen's password check | `ui_lock_ok`, `ui/borehole.mx:1675`-`1682` |

The lock screen is worth calling out: `ui_lock_ok` (moved out of `kmain.mx`
into `ui/borehole.mx` by the Borehole rewrite, same logic) hashes what you
typed and compares it against **the current user's** account hash, not a
fixed string. So the lock password is `mort` for the auto-logged-in user —
but after `su root`, locking the screen requires `toor`, and after a
`passwd` it requires whatever you just set for this session.

Password entry everywhere (`su`, `sudo`, `passwd`, `kmain.mx:3245`/`3268`/
`3286`) goes through `kread_line(buf, mask)` (`kmain.mx:3565`-`3602`), which
reads via `input_wait()` (PS/2 or COM1) and echoes `*` per character when
`mask` is true. The polling is deliberate: interrupts are off inside a shell
command, so the IRQ1 keyboard path isn't running (`kmain.mx:3563`-`3564`).

## Switching users

- `su [user]` (`kmain.mx:3230`-`3254`) prompts, and on a hash match assigns
  `g_uid`/`g_username` from the account slot. There is no session stack — `su`
  is a one-way switch, and there is no `exit` command to switch back (the
  command table in [`docs/shell.md`](shell.md) has no such entry); use
  `su mortuex` to go back the other way.
- `sudo <cmd>` (`kmain.mx:3255`-`3280`) prompts for the *current* user's
  password, sets `g_uid = 0` for exactly one `run_command` call, then restores
  the saved uid (`kmain.mx:3271`-`3274`). If you are already root it runs the
  command with no prompt at all.

### `sudo`'s password prompt can overflow past column 79, unlike `su`'s or `passwd`'s

[`docs/programs.md`](programs.md#typing-a-long-answer-to-syscall-4-corrupts-the-row-below-it)
traces `kread_line()` (`kmain.mx:3565`-`3602`, the same masked-input reader
behind `su`, `sudo`, and `passwd`) and finds it safe for `su`/`passwd`
specifically, because their prompts are a fixed length that leaves 60
characters of headroom under the console's 80-column width. `sudo`'s prompt
isn't fixed, and that safety margin doesn't carry over to it: `"[sudo]
password for "` is 20 characters (`kmain.mx:3262`), followed by the
*current username* (`kmain.mx:3263`-`3264`) and `": "` (`kmain.mx:3265`),
so the password's starting column is `22 + len(username)`
(`kmain.mx:3266`). Root never reaches this prompt at all — `g_uid == 0`
short-circuits `sudo` straight to the command with no password check
(`kmain.mx:3257`-`3259`) — so the *only* username this prompt can ever show
in a running kernel is the default `mortuex` (7 characters; the only other
account, `root`, is exactly the one this branch excludes). That puts the
password's start at column 29. Typing the 52nd character of a password
lands at column 80 — well inside `kread_line`'s own 60-character cap
(`kmain.mx:3590`) — and overflows exactly the way `docs/programs.md`
documents for syscall 4's `read_line()`: text mode wraps into column 0 of
the row below instead of scrolling, silently overwriting whatever was
there; graphics mode just draws the glyph further right past the console's
edge. The corruption happens during echo, before the password is checked,
so it reproduces with any wrong 52-character-or-longer guess — no
privileges or special setup needed.

## What the permission bits actually do

Every MortFS v2 entry carries an owner and a mode in its metadata bytes —
`uid` at offset 42, `mode` at offset 44, read back through `fs_uid`/`fs_mode`
(`kmain.mx:1527`-`1528`; the full layout is documented at
`kmain.mx:1517`-`1523`). New entries are stamped with the creating user's uid
and a default mode by `fs_set_meta` (`kmain.mx:1542`-`1549`, called from
`fs_create_full` at `kmain.mx:1854`): `0644` for files, `0755` for
directories (`kmain.mx:1838`, `kmain.mx:1842`).

All enforcement goes through one function, `can_write(uid, mode)`
(`kmain.mx:3607`-`3615`):

- root (`g_uid == 0`) may always write;
- the owner needs the owner-write bit (`0200`);
- anyone else needs the other-write bit (`0002`).

Group bits are stored and printed but never consulted — there is no group id
anywhere in the source. For directories, `dir_owner`/`dir_mode`
(`kmain.mx:3618`-`3625`) supply root's implicit values (root-owned, `0755`),
since the filesystem root is not a table entry.

`can_write` has exactly three call sites:

| Operation | Check | Source |
|---|---|---|
| Creating any entry | write permission on the **parent directory** | `fs_create_full`, `kmain.mx:1821`-`1823` |
| `write` to an existing file | write permission on the file | `kmain.mx:3110`-`3113` |
| `rm` | write permission on the file | `kmain.mx:3152`-`3155` |

All three print `permission denied` and abort.

Two other commands do their own, separate checks:

- `chmod` — owner or root only (`kmain.mx:3319`-`3322`), else
  `chmod: not permitted`.
- `chown` — root only (`kmain.mx:3334`-`3337`), else
  `chown: not permitted (root only)`.

### What is not checked

This is the practical part. Outside the five checks above, the mode bits are
inert:

- **Path traversal is never checked, only the final component.**
  `fs_resolve` (`kmain.mx:1624`-`1678`) is the one function behind every path
  a command takes — `cd` (`kmain.mx:2959`), `ls <path>` (`kmain.mx:2980`),
  `rmdir` (`kmain.mx:3043`), and, through the thin `fs_find` wrapper
  (`kmain.mx:1751`-`1757`), `cat`/`write`/`rm`/`run`/`exec`; `fs_parent_of`
  (`kmain.mx:1705`-`1747`, used by `write`'s create path and `mkdir`'s
  `fs_mkdir`, `kmain.mx:1877`-`1891`) resolves everything but the leaf the
  same way, via its own `fs_resolve` call at `kmain.mx:1737`. The walk
  through each `/`-separated component is a bare `fs_find_in` name lookup
  (`kmain.mx:1657`) — no call to `can_write`, `dir_mode`, or anything else
  permission-related anywhere in the loop. So the "parent directory" row in
  the table above is narrower than it sounds: it fires once, on the
  immediate parent of the thing being created, never on any directory
  higher up the path. A `0700` root-owned directory is fully walkable by
  any user — `cd` into it, `ls` its contents, `cat`/`run` anything inside,
  however many levels deep — and `mkdir a/b/c/newdir` only ever checks
  write permission on `c`, not on `a` or `b`.
- **Read bits are never consulted.** `cat` (`kmain.mx:3068`-`3091`) reads any
  file it can resolve, whatever its mode or owner.
- **Execute bits are never consulted.** `exec_file` (`kmain.mx:2647`-`2689`)
  loads and jumps to any file that resolves and is non-empty. `fs_populate_bin`
  marks seeded programs `0755` (`kmain.mx:1937`), but that mode is decoration —
  a `0600` file in `/bin` runs just as well.
- **`rmdir` checks nothing.** Unlike `rm`, `rmdir` (`kmain.mx:3041`-`3067`)
  goes straight from "is it an empty directory?" to freeing the slot, with no
  `can_write` call — so any user can remove any empty directory they can name,
  including a root-owned one.

None of this is a hole to patch from a doc; it is what the five checks above
add up to today, and it is worth knowing before you assume a mode bit
protects something.
