#!/usr/bin/env python3
"""Boot tests: the real kernel in headless QEMU, driven over COM1 in lock-step.

Wait for the prompt, send one command, read what came back, assert on it. Every
assertion is on serial output. Tokens are random per run, so a kernel cannot pass
by printing canned text.

    python test_boot.py                   # build, then every session
    python test_boot.py files errors      # only these sessions
    python test_boot.py --no-build        # reuse build/
    python test_boot.py --kernel x.elf    # test another kernel image

Each session writes a transcript to build/test-logs/boot/<session>.log, and a
failing session prints its transcript too. Exit code 0 = all passed.

COM1 is a TCP connection from QEMU to this script, made before the guest starts,
so the banner cannot be missed. The monitor is on QEMU's stdio; it quits QEMU
cleanly, and captures the screen and registers when a test fails.
"""
import argparse
import os
import re
import secrets
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import build  # noqa: E402  (kernel, programs, QEMU discovery)
import mkfs  # noqa: E402
import test as T  # noqa: E402  (monitor helpers)

BANNER = "MORT OS -- interrupt-driven. type 'help', Enter"
FAULT = "*** CPU EXCEPTION"
USER = "mortuex"
PASSWORD = "mort"
LOG_DIR = os.path.join(build.BUILD, "test-logs", "boot")

CMD_TIMEOUT_S = 20               # one command, prompt to prompt
BOOT_TIMEOUT_S = 60              # power-on or reset to the first prompt
QUIT_TIMEOUT_S = 15              # monitor `quit` to process exit
SLOW_READ_TIMEOUT_S = 60         # one program start on a disk reading 1 sector a second
STUCK_WRITE_TIMEOUT_S = 150      # how long the kernel may wait before giving up on a write
SLOW_WRITE_TIMEOUT_S = 60        # one `write` on the throttled disk: 10 sector writes
WRITE_ERROR = "i/o error: disk write failed"
READ_ERROR = "i/o error: disk read failed"
GUEST_LIMIT_S = 180              # watchdog: no QEMU outlives this

passed = 0
failed = 0


class GuestFailure(Exception):
    """The session cannot go on: a hang, a fault, or QEMU died."""


class Transcript:
    """Everything a session did, in order, for the failure log."""

    def __init__(self, session):
        self.session = session
        self.path = os.path.join(LOG_DIR, session + ".log")
        self.failures = 0
        self.lines = []

    def add(self, text):
        self.lines.append(text)

    def check(self, label, ok, detail=None):
        global passed, failed
        name = f"{self.session}: {label}"
        if ok:
            passed += 1
            print(f"PASS: {name}")
            self.add(f"PASS: {label}")
            return True
        failed += 1
        self.failures += 1
        print(f"FAIL: {name}")
        self.add(f"FAIL: {label}")
        if detail is not None:
            print(f"      {detail}")
            self.add(f"      {detail}")
        return False

    def write(self):
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(self.path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(self.lines) + "\n")


class Guest:
    """One QEMU process with COM1 on a socket and the monitor on stdio."""

    def __init__(self, log, kernel, disk=None, tag="boot", drive_opts="", faults=None):
        self.log = log
        self.tag = tag
        self.rx = bytearray()
        self.rx_lock = threading.Lock()
        self.fault_ok = False
        self.powered_off = False
        self.proc = None

        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(BOOT_TIMEOUT_S)
        port = listener.getsockname()[1]
        cmd = [build._find_qemu(), *build.QEMU_HEADLESS, "-monitor", "stdio",
               "-serial", f"tcp:127.0.0.1:{port}", "-kernel", kernel]
        if disk:
            source = f"file={disk}"
            if faults:               # blkdebug makes QEMU fail the I/O the config names
                source = (f"file.driver=blkdebug,file.config={faults},"
                          f"file.image.driver=file,file.image.filename={disk}")
            cmd += ["-drive", f"{source},format=raw,if=ide,index=0,media=disk{drive_opts}"]
        log.add(f"=== {tag}: {' '.join(cmd)}")
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, bufsize=0)
        self.mon = T.QemuHandle(self.proc)
        self.watchdog = threading.Timer(GUEST_LIMIT_S, self._expire)
        self.watchdog.daemon = True
        self.watchdog.start()
        self.expired = False
        try:
            self.sock, _ = listener.accept()
        except OSError as exc:
            self._kill()
            raise GuestFailure(f"QEMU never connected COM1 ({exc}); {self.mon.tail()}")
        finally:
            listener.close()
        self.reader = threading.Thread(target=self._pump, daemon=True)
        self.reader.start()

    def _expire(self):
        self.expired = True
        self.proc.kill()

    def _pump(self):
        while True:
            try:
                chunk = self.sock.recv(65536)
            except OSError:
                return
            if not chunk:
                return
            with self.rx_lock:
                self.rx.extend(chunk)

    def mark(self):
        with self.rx_lock:
            return len(self.rx)

    def text(self, mark=0):
        with self.rx_lock:
            return bytes(self.rx[mark:]).decode("ascii", "replace")

    def _wait(self, pred, mark, timeout_s, what):
        """Poll COM1 from mark until pred(text); raise if the guest cannot get there."""
        deadline = time.monotonic() + timeout_s
        while True:
            out = self.text(mark)
            if pred(out):
                return out
            if FAULT in out and not self.fault_ok:
                raise GuestFailure(f"CPU exception while waiting for {what}: {out!r}")
            if self.proc.poll() is not None:
                why = "watchdog expired" if self.expired else f"exit {self.proc.returncode}"
                raise GuestFailure(f"QEMU is gone ({why}) while waiting for {what}: {out!r}")
            if time.monotonic() >= deadline:
                raise GuestFailure(f"timed out after {timeout_s} s waiting for {what}: {out!r}")
            time.sleep(0.01)

    def wait_booted(self, mark=0):
        """Wait for the banner and first prompt; return all COM1 text from mark."""
        out = self._wait(lambda s: BANNER in s and build.SHELL_PROMPT.search(s), mark,
                         BOOT_TIMEOUT_S, "the banner and first prompt")
        self.log.add(f"<<< {out!r}")
        return out

    def send(self, line):
        self.log.add(f">>> {line}")
        self.sock.sendall(line.encode("ascii") + b"\r")

    def cmd(self, line, timeout_s=CMD_TIMEOUT_S):
        """Send one command, wait for the next prompt, return its output lines."""
        mark = self.mark()
        self.send(line)
        return self._lines(line, self._wait(build.SHELL_PROMPT.search, mark, timeout_s,
                                            f"the prompt after {line!r}"))

    def _lines(self, line, out):
        self.log.add(f"<<< {out!r}")
        lines = out.split("\r\n")
        lines.pop()                  # the prompt
        if not lines or lines[0] != line:
            raise GuestFailure(f"shell did not echo {line!r} as typed: {out!r}")
        lines = lines[1:]
        while lines and lines[-1] == "":     # cat and programs end on a blank feed
            lines.pop()
        return lines

    def send_until(self, line, needle, timeout_s=CMD_TIMEOUT_S):
        """Send a line that makes the guest ask for more; return text up to the question."""
        mark = self.mark()
        self.send(line)
        out = self._wait(lambda s: needle in s, mark, timeout_s, f"{needle!r} after {line!r}")
        self.log.add(f"<<< {out!r}")
        return out

    def answer(self, line, timeout_s=CMD_TIMEOUT_S):
        """Answer a question asked by send_until; return text up to the next prompt."""
        mark = self.mark()
        self.log.add(">>> (answer) " + line)
        self.sock.sendall(line.encode("ascii") + b"\r")
        out = self._wait(build.SHELL_PROMPT.search, mark, timeout_s, "the prompt after the answer")
        self.log.add(f"<<< {out!r}")
        return out

    def wait_text(self, needle, mark=0, timeout_s=CMD_TIMEOUT_S):
        return self._wait(lambda s: needle in s, mark, timeout_s, repr(needle))

    def wait_exit(self, timeout_s=QUIT_TIMEOUT_S):
        """Wait for the guest to power QEMU off by itself; return the exit code."""
        try:
            return self.proc.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            return None

    def capture_state(self):
        """Screen and registers for the failure log. Never hides the original failure."""
        if self.proc.poll() is not None:
            self.log.add(f"(QEMU already exited, code {self.proc.returncode})")
            return
        try:
            self.log.add("--- VGA screen ---\n" + T.screen_text(self.mon))
            self.log.add("--- info registers ---\n" + T._monitor(self.mon, "info registers"))
        except (OSError, RuntimeError, TimeoutError) as exc:
            self.log.add(f"(could not capture guest state: {exc!r})")

    def _kill(self):
        self.proc.kill()
        self.proc.wait(timeout=10)

    def close(self):
        """Quit QEMU through its monitor; a QEMU that will not quit is a failure."""
        self.watchdog.cancel()
        clean = True
        if self.proc.poll() is None:
            self.proc.stdin.write(b"quit\n")
            self.proc.stdin.flush()
            try:
                self.proc.wait(timeout=QUIT_TIMEOUT_S)
            except subprocess.TimeoutExpired:
                clean = False
                self._kill()
        self.sock.close()
        for pipe in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
            pipe.close()
        self.log.add(f"=== {self.tag}: QEMU exit code {self.proc.returncode}")
        self.log.add(f"--- complete COM1 stream of {self.tag} ---\n" + self.text())
        stderr = bytes(self.mon.err).decode("ascii", "replace").strip()
        if stderr:
            self.log.add(f"--- QEMU stderr ---\n{stderr}")
        if not clean:
            raise GuestFailure(f"{self.tag}: QEMU ignored the monitor's quit and was killed")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self.capture_state()
        self.close()
        return False


class Run:
    """What the sessions share: the kernel under test and throwaway images."""

    def __init__(self, kernel):
        self.kernel = kernel
        self.tmp = tempfile.mkdtemp(prefix="mortboot-test-")
        self.bins = []

    def image(self, name, adds=()):
        """A fresh MortFS image with the programs and these (name, content) files."""
        path = os.path.join(self.tmp, name + ".img")
        specs = []
        for fname, content in adds:
            host = os.path.join(self.tmp, name + "-" + fname)
            with open(host, "w", newline="\n") as fh:
                fh.write(content)
            specs.append((host, fname))
        mkfs.make(path, adds=specs, bins=self.bins)
        return path

    def faults(self, name, *rules):
        """A blkdebug config: each rule is (event, sector or None), failing with EIO."""
        path = os.path.join(self.tmp, name + ".blkdebug")
        with open(path, "w", newline="\n") as fh:
            for event, sector in rules:
                # An active rule hits every kind of I/O unless told which one.
                iotype = {"write_aio": "write", "flush_to_disk": "flush", "read_aio": "read"}[event]
                fh.write(f'[inject-error]\nevent = "{event}"\niotype = "{iotype}"\nerrno = "5"\n')
                if sector is not None:
                    fh.write(f'sector = "{sector}"\n')
        return path


TOKEN = lambda: "t" + secrets.token_hex(4)  # noqa: E731
SEEDED = "first line from mkfs\nsecond line from mkfs\n"


def check_lines(log, label, got, want):
    return log.check(label, got == want, f"got {got!r}, want {want!r}")


def boot_ok(log, guest, label="boot", prompt="~ $ "):
    out = guest.wait_booted()
    first = out.split("\r\n")
    log.check(f"{label}: the banner is on COM1", BANNER in first, repr(first[:3]))
    log.check(f"{label}: the shell prompt follows", out.endswith(prompt), repr(out[-20:]))
    log.check(f"{label}: no CPU exception", FAULT not in out, repr(out))


def lost_nothing(log, guest):
    """Lock-step input must never overrun the kernel's receive path."""
    out = guest.cmd("serial")
    found = re.search(r"overrun (\d+) ring-lost (\d+) tx-dropped (\d+)", " ".join(out))
    log.check("serial counters report no lost bytes",
              found is not None and found.groups() == ("0", "0", "0"), repr(out))


LS_ENTRY = r"^[-d] (?P<mode>[0-7]{3}) +%s +\d+ bytes +uid +(?P<uid>\d+)$"


def ls_field(guest, name, field, where=""):
    """The mode or owner `ls` shows for name in directory where (default: cwd), or None."""
    for line in guest.cmd(f"ls {where}".strip()):
        found = re.match(LS_ENTRY % re.escape(name), line)
        if found:
            return found.group(field)
    return None


# ----- sessions -----

def session_boot(run, log):
    """Power-on to prompt, with a disk and with the machine exactly as `-kernel` leaves it."""
    with Guest(log, run.kernel, disk=run.image("boot")) as g:
        boot_ok(log, g)
        log.check("boot: first command is accepted", g.cmd("echo ready") == ["ready"])
        lost_nothing(log, g)


def session_shell(run, log):
    with Guest(log, run.kernel, disk=run.image("shell")) as g:
        boot_ok(log, g)
        out = g.cmd("help")
        joined = " ".join(out).split()
        for name in ("help", "about", "echo", "uptime", "serial", "pwd", "cd", "ls", "cat",
                     "write", "rm", "mkdir", "rmdir", "run", "exec", "whoami", "su", "sudo",
                     "passwd", "chmod", "chown", "env", "export", "unset"):
            log.check(f"help lists {name}", name in joined, repr(out))
        tok = TOKEN()
        check_lines(log, "echo prints exactly its argument", g.cmd(f"echo {tok} two"), [f"{tok} two"])
        check_lines(log, "$USER expands", g.cmd("echo u-$USER-$NOPE-"), [f"u-{USER}--"])
        g.cmd(f"export TOK={tok}")
        check_lines(log, "export sets a variable", g.cmd("echo $TOK"), [tok])
        g.cmd("unset TOK")
        check_lines(log, "unset removes it", g.cmd("echo x$TOK"), ["x"])
        log.check("whoami names the login user", USER in " ".join(g.cmd("whoami")))
        check_lines(log, "pwd is the home directory", g.cmd("pwd"), [f"/home/{USER}"])
        about = " ".join(g.cmd("about"))
        log.check("about describes the OS", "MORT" in about, repr(about))
        up = " ".join(g.cmd("uptime"))
        log.check("uptime reports seconds", re.search(r"uptime: \d+ s", up) is not None, repr(up))
        check_lines(log, "an empty line just prompts again", g.cmd(""), [])
        lost_nothing(log, g)


def session_files(run, log):
    disk = run.image("files", adds=[("seeded.txt", SEEDED)])
    with Guest(log, run.kernel, disk=disk) as g:
        boot_ok(log, g)
        root = g.cmd("ls /")
        seeded = [ln for ln in root if " seeded.txt" in ln]
        log.check("ls / shows the seeded file", len(seeded) == 1, repr(root))
        log.check("ls shows its real size", "43 bytes" in " ".join(seeded), repr(seeded))
        for d in ("bin", "etc", "home"):
            log.check(f"ls / shows {d}", any(ln.startswith("d ") and f" {d} " in ln + " " for ln in root),
                      repr(root))
        check_lines(log, "ls of an empty home says so", g.cmd("ls"), ["(empty)"])
        check_lines(log, "cat prints every line in order", g.cmd("cat /seeded.txt"),
                    ["first line from mkfs", "second line from mkfs"])

        one, two = TOKEN(), TOKEN()
        check_lines(log, "write creates a file silently", g.cmd(f"write a.txt {one}"), [])
        log.check("ls shows the new file", any(" a.txt" in ln for ln in g.cmd("ls")))
        check_lines(log, "cat reads back what write stored", g.cmd("cat a.txt"), [one])
        g.cmd(f"write a.txt {two}")
        check_lines(log, "write appends a line", g.cmd("cat a.txt"), [one, two])

        g.cmd("mkdir sub")
        g.cmd("cd sub")
        check_lines(log, "cd enters a new directory", g.cmd("pwd"), [f"/home/{USER}/sub"])
        g.cmd(f"write inner.txt {one}")
        g.cmd("cd ..")
        check_lines(log, "cd .. returns", g.cmd("pwd"), [f"/home/{USER}"])
        check_lines(log, "a relative path reaches the file", g.cmd("cat sub/inner.txt"), [one])

        g.cmd(f"write job.txt echo {two}")
        g.cmd("write job.txt pwd")
        check_lines(log, "run executes a file of commands", g.cmd("run job.txt"),
                    [f"~ $ echo {two}", two, "~ $ pwd", f"/home/{USER}"])

        g.cmd("rm a.txt")
        check_lines(log, "rm removes the file", g.cmd("cat a.txt"), ["cat: not found: a.txt"])
        log.check("rm drops it from ls", not any(" a.txt" in ln for ln in g.cmd("ls")))
        g.cmd("rm sub/inner.txt")
        g.cmd("rmdir sub")
        log.check("rmdir removes the directory", not any(" sub" in ln for ln in g.cmd("ls")))
        lost_nothing(log, g)


def session_persistence(run, log):
    """Everything on disk survives a warm reset and then a real power cycle."""
    disk = run.image("persist", adds=[("doomed.txt", "bye\n")])
    keep, more = TOKEN(), TOKEN()
    with Guest(log, run.kernel, disk=disk, tag="first boot") as g:
        boot_ok(log, g, "first boot")
        g.cmd(f"write keep.txt {keep}")
        g.cmd(f"write keep.txt {more}")
        g.cmd("mkdir kept")
        g.cmd(f"write kept/deep.txt {more}")
        g.send_until("sudo rm /doomed.txt", "password for")
        g.answer(PASSWORD)

        mark = g.mark()
        g.send("reboot")
        out = g._wait(lambda s: BANNER in s and build.SHELL_PROMPT.search(s), mark,
                      BOOT_TIMEOUT_S, "the banner after reboot")
        log.add(f"<<< {out!r}")
        log.check("reboot: the kernel comes back up", out.endswith("~ $ "), repr(out[-20:]))
        check_lines(log, "reboot: the file survives", g.cmd("cat keep.txt"), [keep, more])
        check_lines(log, "reboot: a nested file survives", g.cmd("cat kept/deep.txt"), [more])
        check_lines(log, "reboot: the removed file stays gone", g.cmd("cat /doomed.txt"),
                    ["cat: not found: /doomed.txt"])
        third = TOKEN()
        g.cmd(f"write keep.txt {third}")
    with Guest(log, run.kernel, disk=disk, tag="second boot") as g:
        boot_ok(log, g, "power cycle")
        check_lines(log, "power cycle: the file survives with its later append",
                    g.cmd("cat keep.txt"), [keep, more, third])
        check_lines(log, "power cycle: a nested file survives", g.cmd("cat kept/deep.txt"), [more])
        check_lines(log, "power cycle: the removed file stays gone", g.cmd("cat /doomed.txt"),
                    ["cat: not found: /doomed.txt"])
        lost_nothing(log, g)


def session_exec(run, log):
    disk = run.image("exec", adds=[("empty.bin", "")])
    with Guest(log, run.kernel, disk=disk) as g:
        boot_ok(log, g)
        check_lines(log, "exec runs a compiled program", g.cmd("exec /bin/hello.bin"),
                    ["hello from a real mort program!",
                     "i was compiled from hello.mx and loaded off the MortFS disk.",
                     "goodbye."])
        tok = TOKEN()
        check_lines(log, "the shell survives the program", g.cmd(f"echo {tok}"), [tok])
        count = g.cmd("exec /bin/count.bin")
        log.check("a second program runs", "one" in count and "three" in count, repr(count))
        check_lines(log, "a program runs from $PATH by bare name", g.cmd("hello"),
                    ["hello from a real mort program!",
                     "i was compiled from hello.mx and loaded off the MortFS disk.",
                     "goodbye."])
        asked = g.send_until("exec /bin/ask.bin", "what is your name?")
        log.check("an interactive program asks over serial", "what is your name?" in asked, repr(asked))
        name = TOKEN()
        reply = g.answer(name)
        log.check("it reads the answer and greets it", f"hello, {name}" in reply, repr(reply))
        check_lines(log, "a missing program is reported", g.cmd("exec /bin/nope.bin"),
                    ["not found: /bin/nope.bin"])
        check_lines(log, "an empty program is refused", g.cmd("exec /bin/empty.bin"), ["empty program"])
        lost_nothing(log, g)


def session_errors(run, log):
    disk = run.image("errors", adds=[("seeded.txt", SEEDED)])
    with Guest(log, run.kernel, disk=disk) as g:
        boot_ok(log, g)
        g.cmd("mkdir d")
        g.cmd("write d/f.txt x")
        for line, want in (
            ("no-such-command", "unknown command"),
            ("cat nope.txt", "cat: not found: nope.txt"),
            ("cat d", "cat: is a directory: d"),
            ("ls nowhere", "ls: not found: nowhere"),
            ("ls d/f.txt", "ls: not a directory: d/f.txt"),
            ("cd nowhere", "cd: no such directory"),
            ("cd d/f.txt", "cd: not a directory"),
            ("rm nope.txt", "not found: nope.txt"),
            ("rm d", "rm: is a directory (use rmdir)"),
            ("rm /seeded.txt", "permission denied"),
            ("write /seeded.txt x", "permission denied"),
            ("write onlyname", "usage: write <name> <text>"),
            ("write nowhere/f.txt x", "write: parent directory does not exist"),
            ("mkdir d", "mkdir: already exists"),
            ("mkdir nowhere/d", "mkdir: parent directory does not exist"),
            ("rmdir nowhere", "rmdir: no such directory"),
            ("rmdir d/f.txt", "rmdir: not a directory"),
            ("rmdir d", "rmdir: directory not empty"),
            ("run nope.txt", "not found: nope.txt"),
            ("exec nope.bin", "not found: nope.bin"),
            ("export =bad", "usage: export NAME=value"),
            ("export NOEQUALS", "usage: export NAME=value"),
            ("chmod 777", "usage: chmod <octal> <path>"),
            ("chmod 777 nope.txt", "chmod: not found"),
            ("chown 0 /seeded.txt", "chown: not permitted (root only)"),
        ):
            check_lines(log, f"{line!r} reports {want!r}", g.cmd(line), [want])
        check_lines(log, "the refused rm left the file alone", g.cmd("cat /seeded.txt"),
                    ["first line from mkfs", "second line from mkfs"])

        # A usage error must not act on what a longer command left past the NUL.
        g.cmd("write mode.txt x")
        g.cmd("chmod 640 mode.txt")
        log.check("chmod sets the mode", ls_field(g, "mode.txt", "mode") == "640", repr(g.cmd("ls")))
        check_lines(log, "chmod with no path after a longer chmod is a usage error", g.cmd("chmod 777"),
                    ["usage: chmod <octal> <path>"])
        log.check("that usage error left the mode alone", ls_field(g, "mode.txt", "mode") == "640",
                  repr(g.cmd("ls")))
        g.cmd("export STALEVALUE=stale")
        check_lines(log, "export with no '=' after a longer export is a usage error",
                    g.cmd("export NOEQUALS"), ["usage: export NAME=value"])
        check_lines(log, "that usage error set no variable", g.cmd("echo x$NOEQUALS"), ["x"])
        # A trailing space is still no path: it must not mean "the current directory".
        home_mode = ls_field(g, USER, "mode", "/home")
        check_lines(log, "chmod with only a trailing space is a usage error", g.cmd("chmod 777 "),
                    ["usage: chmod <octal> <path>"])
        log.check("that usage error left the current directory alone",
                  home_mode is not None and ls_field(g, USER, "mode", "/home") == home_mode,
                  repr(g.cmd("ls /home")))
        home_owner = ls_field(g, USER, "uid", "/home")
        g.send_until("sudo chown 5 ", "password for")
        reply = g.answer(PASSWORD)
        log.check("chown with only a trailing space is a usage error",
                  "usage: chown <uid> <path>" in reply, repr(reply))
        log.check("that usage error left the owner of the current directory alone",
                  home_owner is not None and ls_field(g, USER, "uid", "/home") == home_owner,
                  repr(g.cmd("ls /home")))
        owner = ls_field(g, "mode.txt", "uid")
        g.send_until("sudo chown 5", "password for")
        reply = g.answer(PASSWORD)
        log.check("chown with no path is a usage error", "usage: chown <uid> <path>" in reply, repr(reply))
        log.check("that usage error left the owner alone", ls_field(g, "mode.txt", "uid") == owner,
                  repr(g.cmd("ls")))

        g.cmd("write meta.txt run meta.txt")
        tok = TOKEN()
        g.cmd(f"write meta.txt echo {tok}")
        check_lines(log, "a nested run is refused and the script carries on", g.cmd("run meta.txt"),
                    ["~ $ run meta.txt", "run: nested run not allowed", f"~ $ echo {tok}", tok])

        asked = g.send_until("sudo whoami", "password for")
        log.check("sudo asks for a password", f"password for {USER}" in asked, repr(asked))
        denied = g.answer("wrong")
        log.check("sudo refuses a wrong password", "sudo: authentication failure" in denied, repr(denied))
        log.check("sudo masks the password", denied.startswith("*****\r\n"), repr(denied))
        log.check("sudo ran nothing", "uid 0" not in denied, repr(denied))
        g.send_until("sudo whoami", "password for")
        allowed = g.answer(PASSWORD)
        log.check("sudo accepts the right password", "(uid 0)" in allowed, repr(allowed))
        log.check("sudo is one command only", "(uid 0)" not in " ".join(g.cmd("whoami")))
        g.send_until("su", "assword")
        denied = g.answer("wrong")
        log.check("su refuses a wrong password", "su: authentication failure" in denied, repr(denied))
        check_lines(log, "su stayed the same user", g.cmd("pwd"), [f"/home/{USER}"])

        check_lines(log, "the shell still works after every error", g.cmd(f"echo {tok}"), [tok])
        lost_nothing(log, g)


def session_nodisk(run, log):
    with Guest(log, run.kernel, tag="no disk") as g:
        boot_ok(log, g, "no disk", prompt="/ $ ")
        for line in ("ls", "cat a.txt", "write a.txt x", "exec a.bin"):
            check_lines(log, f"{line!r} says there is no disk", g.cmd(line),
                        ["no disk (boot with -hda disk.img)"])
        tok = TOKEN()
        check_lines(log, "the shell works without a disk", g.cmd(f"echo {tok}"), [tok])
    bad = os.path.join(run.tmp, "zeroed.img")
    with open(bad, "wb") as fh:
        fh.write(b"\x00" * (16 * 1024 * 1024))
    with Guest(log, run.kernel, disk=bad, tag="bad filesystem") as g:
        boot_ok(log, g, "bad filesystem", prompt="/ $ ")
        got = " ".join(g.cmd("ls"))
        log.check("a non-MortFS disk is reported", "bad filesystem" in got, repr(got))


def session_fault(run, log):
    """A CPU exception is reported on COM1 and really stops the machine."""
    with Guest(log, run.kernel, tag="crash") as g:
        boot_ok(log, g, "crash", prompt="/ $ ")
        g.fault_ok = True
        mark = g.mark()
        g.send("crash")
        out = g.wait_text("-- HALTED ***", mark)
        log.add(f"<<< {out!r}")
        log.check("crash reports #UD on COM1", "*** CPU EXCEPTION #6 -- HALTED ***" in out, repr(out))
        mark = g.mark()
        g.send("echo after-crash")
        time.sleep(3)
        log.check("a halted machine runs no more commands", g.text(mark) == "", repr(g.text(mark)))


def session_power(run, log):
    """`shutdown` powers QEMU off by itself, with a clean exit status."""
    with Guest(log, run.kernel, disk=run.image("power"), tag="shutdown") as g:
        boot_ok(log, g, "shutdown")
        mark = g.mark()
        g.send("shutdown")
        out = g.wait_text("It is now safe to turn off your computer.", mark)
        log.add(f"<<< {out!r}")
        code = g.wait_exit()
        log.check("shutdown makes QEMU exit", code is not None, repr(g.text(mark)))
        log.check("QEMU's exit status is 0", code == 0, repr(code))


def session_slowdisk(run, log):
    """A disk that takes its time over a write must not cost the data.

    QEMU holds each sector write for 500 ms, as a busy host disk can. The first
    boot is unthrottled, so only the write under test is slow.
    """
    disk = run.image("slowdisk")
    with Guest(log, run.kernel, disk=disk, tag="first boot") as g:
        boot_ok(log, g, "first boot")
    tok = TOKEN()
    with Guest(log, run.kernel, disk=disk, tag="slow disk", drive_opts=",throttling.iops-write=2") as g:
        boot_ok(log, g, "slow disk")
        check_lines(log, "write reports no error on a slow disk",
                    g.cmd(f"write slow.txt {tok}", timeout_s=SLOW_WRITE_TIMEOUT_S), [])
        check_lines(log, "cat reads back what the slow write stored", g.cmd("cat slow.txt"), [tok])
    with Guest(log, run.kernel, disk=disk, tag="after slow disk") as g:
        boot_ok(log, g, "after slow disk")
        check_lines(log, "the slow write survives a power cycle", g.cmd("cat slow.txt"), [tok])


def data_sector(disk, name):
    """The first data sector of the MortFS file called name, read from the image."""
    with open(disk, "rb") as fh:
        table = fh.read(9 * 512)
    for i in range(64):
        entry = table[512 + i * 64:512 + (i + 1) * 64]
        used, _size, start = struct.unpack("<III", entry[24:36])
        if used == 1 and entry[:24].rstrip(b"\x00") == name.encode("ascii"):
            return start
    raise AssertionError(f"{name} is not on {disk}")


def ed_send(guest, line, prompt=True):
    """Send one line to ed; return its output up to the next ": " prompt.

    In text entry ed prints no prompt, so with prompt=False wait for the echo.
    """
    mark = guest.mark()
    guest.send(line)
    done = (lambda s: s.endswith(": ")) if prompt else (lambda s: s.endswith(line + "\r\n"))
    out = guest._wait(done, mark, CMD_TIMEOUT_S, f"ed's response to {line!r}")
    guest.log.add(f"<<< {out!r}")
    return out


def failed_writes(log, g, label, old, tok):
    """Every way of changing the disk must say it failed and change nothing."""
    check_lines(log, f"{label}: write to a new file reports the error",
                g.cmd(f"write fresh.txt {tok}"), [WRITE_ERROR])
    check_lines(log, f"{label}: the failed new file does not exist", g.cmd("cat fresh.txt"),
                ["cat: not found: fresh.txt"])
    check_lines(log, f"{label}: an append reports the error", g.cmd(f"write old.txt {tok}"), [WRITE_ERROR])
    check_lines(log, f"{label}: the failed append is not visible", g.cmd("cat old.txt"), [old])
    check_lines(log, f"{label}: rm reports the error", g.cmd("rm old.txt"), [WRITE_ERROR])
    check_lines(log, f"{label}: the failed rm kept the file", g.cmd("cat old.txt"), [old])
    check_lines(log, f"{label}: mkdir reports only the error", g.cmd("mkdir newdir"), [WRITE_ERROR])
    check_lines(log, f"{label}: the failed mkdir made nothing", g.cmd("ls newdir"),
                ["ls: not found: newdir"])
    check_lines(log, f"{label}: rmdir reports the error", g.cmd("rmdir empty"), [WRITE_ERROR])
    log.check(f"{label}: the failed rmdir kept the directory", ls_field(g, "empty", "mode") == "755",
              repr(g.cmd("ls")))
    mode, owner = ls_field(g, "old.txt", "mode"), ls_field(g, "old.txt", "uid")
    check_lines(log, f"{label}: chmod reports the error", g.cmd("chmod 600 old.txt"), [WRITE_ERROR])
    log.check(f"{label}: the failed chmod kept the mode", ls_field(g, "old.txt", "mode") == mode,
              repr(g.cmd("ls")))
    g.send_until("sudo chown 5 old.txt", "password for")
    reply = g.answer(PASSWORD)
    log.check(f"{label}: chown reports the error", WRITE_ERROR in reply, repr(reply))
    log.check(f"{label}: the failed chown kept the owner", ls_field(g, "old.txt", "uid") == owner,
              repr(g.cmd("ls")))

    # A program's file syscalls: ed reports the kernel's EIO and never says "wrote".
    for path, entry, final in (("edited.txt", ("a", "text"), "."), ("old.txt", (), "c 1 changed")):
        ed_send(g, f"ed {path}")
        for key in entry:
            ed_send(g, key, prompt=False)
        ed_send(g, final)
        out = ed_send(g, "w")
        log.check(f"{label}: ed reports the failed save of {path}",
                  f"ed: i/o error: {path}" in out, repr(out))
        log.check(f"{label}: ed does not claim it wrote {path}", "wrote" not in out, repr(out))
        g.answer("q!")
    check_lines(log, f"{label}: the failed new program file does not exist", g.cmd("cat edited.txt"),
                ["cat: not found: edited.txt"])
    check_lines(log, f"{label}: the failed rewrite left the file whole", g.cmd("cat old.txt"), [old])


def session_ioerror(run, log):
    """An error the disk reports reaches the user, and nothing pretends it worked."""
    disk = run.image("ioerror")
    old, tok, script = TOKEN(), TOKEN(), TOKEN()
    with Guest(log, run.kernel, disk=disk, tag="prepare") as g:
        boot_ok(log, g, "prepare")
        g.cmd(f"write old.txt {old}")
        g.cmd(f"write job.txt echo {script}")
        g.cmd("mkdir empty")
        check_lines(log, "prepare: the disk is healthy before any fault", g.cmd("cat old.txt"), [old])

    for label, event in (("write error", "write_aio"), ("flush error", "flush_to_disk")):
        with Guest(log, run.kernel, disk=disk, tag=label, faults=run.faults(label[:5], (event, None))) as g:
            boot_ok(log, g, label)
            failed_writes(log, g, label, old, tok)
        with Guest(log, run.kernel, disk=disk, tag=f"after {label}") as g:
            boot_ok(log, g, f"after {label}")
            check_lines(log, f"after {label}: the old file is intact", g.cmd("cat old.txt"), [old])
            check_lines(log, f"after {label}: the failed file never appeared", g.cmd("cat fresh.txt"),
                        ["cat: not found: fresh.txt"])

    bad = run.faults("reads", *[("read_aio", data_sector(disk, n)) for n in ("old.txt", "job.txt", "hello.bin")])
    with Guest(log, run.kernel, disk=disk, tag="read error", faults=bad) as g:
        boot_ok(log, g, "read error")
        check_lines(log, "read error: the cat program reports it", g.cmd("cat old.txt"),
                    ["cat: i/o error: old.txt"])
        check_lines(log, "read error: run reports it", g.cmd("run job.txt"), [READ_ERROR])
        check_lines(log, "read error: exec reports it", g.cmd("exec /bin/hello.bin"),
                    ["exec: disk read error"])
        g.send_until("sudo rm /bin/cat.bin", "password for")
        g.answer(PASSWORD)           # with no program, the shell's own cat answers
        check_lines(log, "read error: the built-in cat reports it", g.cmd("cat old.txt"), [READ_ERROR])

    table = run.faults("table", ("read_aio", 0))
    with Guest(log, run.kernel, disk=disk, tag="table read error", faults=table) as g:
        boot_ok(log, g, "table read error", prompt="/ $ ")
        check_lines(log, "table read error: ls says the disk failed, not that it is bad",
                    g.cmd("ls"), [READ_ERROR])


def session_slowio(run, log):
    """Slow reads still work; a write that never finishes is an error, not a success."""
    disk = run.image("slowio")
    old = TOKEN()
    with Guest(log, run.kernel, disk=disk, tag="prepare") as g:
        boot_ok(log, g, "prepare")
        g.cmd(f"write old.txt {old}")
    with Guest(log, run.kernel, disk=disk, tag="slow reads", drive_opts=",throttling.iops-read=1") as g:
        boot_ok(log, g, "slow reads")
        check_lines(log, "slow reads: the file reads back", g.cmd("cat old.txt", timeout_s=SLOW_READ_TIMEOUT_S), [old])
    # 2 bytes a second: the second sector written would take over four minutes.
    with Guest(log, run.kernel, disk=disk, tag="stuck write", drive_opts=",throttling.bps-write=2") as g:
        boot_ok(log, g, "stuck write")
        check_lines(log, "stuck write: the kernel gives up and says so",
                    g.cmd("write stuck.txt never", timeout_s=STUCK_WRITE_TIMEOUT_S), [WRITE_ERROR])
    with Guest(log, run.kernel, disk=disk, tag="after stuck write") as g:
        boot_ok(log, g, "after stuck write")
        check_lines(log, "after stuck write: no file was promised", g.cmd("cat stuck.txt"),
                    ["cat: not found: stuck.txt"])
        check_lines(log, "after stuck write: the old file is intact", g.cmd("cat old.txt"), [old])


SESSIONS = {f.__name__.replace("session_", ""): f for f in (
    session_boot, session_shell, session_files, session_persistence, session_exec,
    session_errors, session_nodisk, session_fault, session_power, session_slowdisk,
    session_ioerror, session_slowio)}


def run_sessions(run, names):
    for name in names:
        log = Transcript(name)
        print(f"--- session {name} ---", flush=True)
        try:
            SESSIONS[name](run, log)
        except GuestFailure as exc:
            log.check("session ran to the end", False, str(exc))
        log.write()
        if log.failures:
            print(f"--- transcript of {name} ({log.path}) ---")
            print("\n".join(log.lines))
            print("--- end of transcript ---", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("sessions", nargs="*", help=f"any of: {' '.join(SESSIONS)}")
    parser.add_argument("--no-build", action="store_true", help="reuse build/")
    parser.add_argument("--kernel", default=build.ELF, help="kernel ELF to boot")
    args = parser.parse_args()
    names = args.sessions or list(SESSIONS)
    unknown = [n for n in names if n not in SESSIONS]
    if unknown:
        sys.exit(f"unknown session(s) {unknown}; choose from {list(SESSIONS)}")
    if not build._find_qemu():
        sys.exit("qemu-system-i386 not found")

    run = Run(os.path.abspath(args.kernel))
    for mx in build._program_sources():
        out = os.path.join(build.BUILD, os.path.splitext(os.path.basename(mx))[0] + ".bin")
        if not args.no_build:
            build.build_program(mx, out)
        run.bins.append((out, os.path.basename(out)))
    if not args.no_build and args.kernel == build.ELF:
        build.build()
    if os.path.isdir(LOG_DIR):
        shutil.rmtree(LOG_DIR)
    os.makedirs(LOG_DIR)
    try:
        run_sessions(run, names)
    finally:
        shutil.rmtree(run.tmp, ignore_errors=True)
    print(f"\n{passed} passed, {failed} failed")
    if passed == 0:
        print("FAIL: no checks ran")
        return 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
