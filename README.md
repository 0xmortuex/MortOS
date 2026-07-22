# mort-repo

The package repository for **`mpkg`**, the [MORT OS](https://github.com/0xmortuex/MortOS) package manager (apt/npm for an OS written from scratch in [Mort](https://github.com/0xmortuex/Mort)).

A package is just a program compiled to a flat `.bin`; `mpkg` downloads it into `/bin` and marks it executable, so it runs by name from the shell.

## Layout

```
index                 # the package list (see format below)
packages/*.bin         # the compiled programs
serve.py               # a plain-HTTP server for the demo
```

## Index format

One package per line, pipe-delimited, `#` for comments:

```
name|version|file|size|description
hello|1.0|hello.bin|225|A friendly greeting program
```

Chosen to be trivially parseable in Mort (split on `|`) — no JSON parser needed in the kernel.

## How `mpkg` uses it (client, in MORT OS)

```
mpkg update            # HTTP GET <repo>/index  -> /var/mpkg/index
mpkg list              # print packages from the cached index
mpkg search <term>     # filter the index
mpkg install <name>    # GET <repo>/packages/<file> -> /bin/<file> (0755), register
mpkg remove <name>     # delete from /bin, unregister
```

Installed packages are tracked in `/var/mpkg/installed`.

## Hosting

MORT OS has no TLS yet, so it fetches over **plain HTTP**. For the demo, run `python serve.py` on the host — under QEMU user networking MORT OS reaches it at `http://10.0.2.2:8000/`. Any plain-HTTP endpoint works for real deployment (TLS in MORT OS is a later milestone).
