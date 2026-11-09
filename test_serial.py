#!/usr/bin/env python3
"""Serial console acceptance test. Boots the real kernel in QEMU with COM1 on
QEMU's stdio pipe, asserts the boot banner arrives on serial, and drives the
shell purely over serial, in lock-step (send a line, wait for the prompt).

    python test_serial.py                  # build, then every session
    python test_serial.py --no-build text  # reuse the build, chosen sessions

Covers the text (-kernel) and graphical (Limine ISO) paths, the polled input
paths (sudo password, a program's read-line syscall), PS/2 used alongside
serial, and a machine with no UART. Prints the COM1 transcript of the first
boot. Needs QEMU + the ISO toolchain. Exit code 0 = all passed.

Stdio bytes are paced, one per kernel tick: QEMU's Windows stdio backend drops
a byte instead of waiting when the FIFO is at its trigger level, faster than a
halted guest can be woken. It also strips CR, so stdio lines end in LF and CR
is tested over TCP. TCP takes short unpaced bursts, but the kernel drains the UART
even with its 512-byte ring full, so a burst over about 512 bytes can lose bytes
unless the sender paces or waits for prompts. `serial` counts the drops.
"""
import os
import re
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

import build  # noqa: E402  (kernel, ISO and program builds)
import mkfs  # noqa: E402
import test as T  # noqa: E402  (QEMU harness)

TMP = tempfile.mkdtemp(prefix="mortserial-test-")
IMG = os.path.join(TMP, "serial.img")
BIGIMG = os.path.join(TMP, "big.img")
ESC = chr(27)

BANNER = "MORT OS -- interrupt-driven"
SESSION_LIMIT_S = 180            # watchdog: no QEMU outlives this
BYTE_GAP_S = 0.02                # longer than one 10 ms kernel tick
# 256 MB guest and a capped translation cache: uncapped QEMU reached 1.4 GB.
QEMU_BASE = ["-display", "none", "-m", "256", "-accel", "tcg,tb-size=32"]

passed = 0
failed = 0


def check(label, ok, detail=None):
    global passed, failed
    if ok:
        passed += 1
        print(f"PASS: {label}")
    else:
        failed += 1
        print(f"FAIL: {label}")
        if detail is not None:
            print(f"--- detail ---\n{detail}\n--------------")
    return ok


# ----- QEMU with COM1 on stdin/stdout -----

def spawn(args):
    """Start QEMU with a watchdog; stdout/stderr are drained by QemuHandle."""
    proc = subprocess.Popen(
        [build._find_qemu(), *QEMU_BASE, *args], stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
    handle = T.QemuHandle(proc)
    timer = threading.Timer(SESSION_LIMIT_S, proc.kill)
    timer.daemon = True
    timer.start()
    handle.watchdog = timer
    return handle


def stop(handle):
    """Kill QEMU and release its pipes (the monitor is not on stdin here)."""
    handle.watchdog.cancel()
    handle.proc.kill()
    handle.proc.wait(timeout=10)
    for pipe in (handle.proc.stdin, handle.proc.stdout, handle.proc.stderr):
        pipe.close()


def boot_serial(*args):
    return spawn(["-serial", "stdio", "-monitor", "none", *args])


def text(handle, mark=0):
    return handle.out_since(mark).decode("ascii", "replace")


def wait_until(handle, pred, mark=0, timeout_s=30):
    """Poll the COM1 stream from `mark` until pred(text); True/False."""
    deadline = time.monotonic() + timeout_s
    while True:
        if pred(text(handle, mark)):
            return True
        if time.monotonic() >= deadline or not handle.alive():
            return False
        time.sleep(0.05)


def wait_text(handle, needle, mark=0, timeout_s=30):
    return wait_until(handle, lambda s: needle in s, mark, timeout_s)


def at_prompt(s):
    return s.endswith("$ ")


def send(handle, data):
    for byte in data.encode("ascii"):
        handle.proc.stdin.write(bytes((byte,)))
        handle.proc.stdin.flush()
        time.sleep(BYTE_GAP_S)


def run(handle, line, timeout_s=30):
    """Send one command and wait for the next prompt; return what came back."""
    mark = handle.out_len()
    send(handle, line + "\n")
    wait_until(handle, at_prompt, mark, timeout_s)
    return text(handle, mark)


def boot_to_prompt(handle, label):
    """Assert banner + prompt on COM1. False means skip the rest of a session."""
    ok = check(f"{label}: banner on COM1", wait_text(handle, BANNER, timeout_s=45),
               repr(text(handle)[-300:]) + " | " + handle.tail(200))
    if ok:
        ok = check(f"{label}: prompt on COM1",
                   wait_until(handle, at_prompt, timeout_s=45), repr(text(handle)[-300:]))
    return ok


# ----- sessions -----

def session_text():
    h = boot_serial("-kernel", build.ELF)
    try:
        if not boot_to_prompt(h, "text"):
            return
        out = run(h, "echo via-serial-$USER")
        check("text: $USER expands, so the shell really ran it",
              "via-serial-mortuex" in out, repr(out))
        check("text: command is echoed back as typed",
              "echo via-serial-$USER" in out, repr(out))
        out = run(h, "uptime")
        check("text: uptime answers", re.search(r"uptime: \d+ s", out) is not None, repr(out))
        out = run(h, "help")
        check("text: help lists the serial command", "serial" in out, repr(out))
        out = run(h, "no-such-command")
        check("text: errors reach serial", "unknown command" in out, repr(out))
        out = run(h, "echo Up_Case:?")
        check("text: shifted characters survive", "\r\nUp_Case:?\r\n" in out, repr(out))
        out = run(h, "ex\x7fcho rubout-ok")
        check("text: DEL edits the line",
              "\r\nrubout-ok\r\n" in out and "unknown" not in out, repr(out))
        out = run(h, "ex\x08cho backspace-ok")
        check("text: BS edits the line",
              "\r\nbackspace-ok\r\n" in out and "unknown" not in out, repr(out))
        print("--- COM1 transcript (text path) ---")
        print(text(h))
        print("-----------------------------------")
    finally:
        stop(h)


def session_polled_input():
    """sudo and a program's read-line poll the hardware from inside a command."""
    h = boot_serial("-kernel", build.ELF, "-hda", IMG)
    try:
        if not boot_to_prompt(h, "polled"):
            return
        mark = h.out_len()
        send(h, "sudo whoami\n")
        check("polled: sudo prompts on serial", wait_text(h, "password for", mark), repr(text(h, mark)))
        mark = h.out_len()
        send(h, "mort\n")
        wait_until(h, at_prompt, mark)
        out = text(h, mark)
        check("polled: sudo password accepted from serial", "(uid 0)" in out, repr(out))
        check("polled: password is masked on serial", out.startswith("****\r\n"), repr(out))

        mark = h.out_len()
        send(h, "exec /bin/ask.bin\n")
        check("polled: program prompts on serial",
              wait_text(h, "what is your name?", mark), repr(text(h, mark)))
        mark = h.out_len()
        send(h, "fadi\n")
        wait_until(h, at_prompt, mark)
        out = text(h, mark)
        check("polled: program reads its line from serial", "hello, fadi" in out, repr(out))
    finally:
        stop(h)


def sendkeys(sock, line):
    for ch in line:
        sock.sendall(f"sendkey {T.key_name(ch)} {T.KEY_HOLD_MS}\n".encode("ascii"))
        time.sleep(T.KEY_GAP_S)
    sock.sendall(f"sendkey ret {T.KEY_HOLD_MS}\n".encode("ascii"))


def free_port():
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    return port


class TcpSerial:
    """COM1 on a TCP socket, with the monitor on stdio for VGA and screendumps."""

    def __init__(self, *args, rcvbuf=None, sndbuf=None):
        port = free_port()
        self.h = spawn(["-serial", f"tcp:127.0.0.1:{port},server=on,wait=off",
                        "-monitor", "stdio", *args])
        T._wait_first_prompt(self.h)
        self.sock = socket.socket()
        if rcvbuf is not None:       # a small window makes an idle reader stall QEMU
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, rcvbuf)
        if sndbuf is not None:       # keeps a flood's backlog small once it stops
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, sndbuf)
        self.sock.settimeout(10)
        self.sock.connect(("127.0.0.1", port))
        self.sock.settimeout(None)
        self.got = bytearray()
        self.read_gap_s = 0          # > 0 throttles the reader, which backs up transmit

    def start_reading(self):
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        while True:
            try:
                chunk = self.sock.recv(256 if self.read_gap_s else 65536)
            except OSError:
                return
            if not chunk:
                return
            self.got.extend(chunk)
            if self.read_gap_s:
                time.sleep(self.read_gap_s)

    def seen(self, start=0):
        return bytes(self.got).decode("ascii", "replace")[start:]

    def until(self, needle, start=0, timeout_s=30):
        deadline = time.monotonic() + timeout_s
        while needle not in self.seen(start) and time.monotonic() < deadline:
            time.sleep(0.05)
        return needle in self.seen(start)

    def typed(self, data):
        for byte in data.encode("ascii"):
            self.sock.sendall(bytes((byte,)))
            time.sleep(BYTE_GAP_S)

    def close(self):
        self.h.watchdog.cancel()
        self.sock.close()
        T.shutdown(self.h)


def session_line_endings():
    """CR and CRLF over TCP (see the module docstring), and both console outputs."""
    t = TcpSerial("-kernel", build.ELF)
    try:
        check("endings: VGA reaches the prompt", T.wait_for(t.h, "$ ", timeout_s=30),
              T.screen_text(t.h))
        t.start_reading()
        t.typed("echo ready-both\r")
        if not check("endings: CR ends a line on serial", t.until("\r\nready-both\r\n"), repr(t.seen())):
            return
        check("endings: the same output is on VGA", T.wait_for(t.h, "ready-both", timeout_s=10),
              T.screen_text(t.h))
        t.until("$ ", t.seen().index("ready-both\r\n"))
        start = len(t.seen())
        t.typed("echo crlf-ok\r\n")
        t.until("\r\ncrlf-ok\r\n", start)
        time.sleep(1)                # room for a wrong second prompt to show up
        out = t.seen(start)
        check("endings: CRLF is one Enter, not two", out.count("$ ") == 1, repr(out))
    finally:
        t.close()


def session_escape():
    h = boot_serial("-kernel", build.ELF)
    try:
        if not boot_to_prompt(h, "escape"):
            return
        out = run(h, ESC + "[A" + ESC + "OB" + ESC + "[1;5Cecho esc-ok")
        check("escape: CSI and SS3 sequences are ignored",
              "\r\nesc-ok\r\n" in out and "[A" not in out and "OB" not in out and "unknown" not in out,
              repr(out))
    finally:
        stop(h)


def session_burst():
    """One unpaced write of several lines, kept well under the 512-byte ring."""
    t = TcpSerial("-kernel", build.ELF)
    try:
        T.wait_for(t.h, "$ ", timeout_s=30)
        t.start_reading()
        lines = [f"echo burst-{n}-0123456789abcdef" for n in range(10)]
        t.sock.sendall("".join(line + "\r" for line in lines).encode("ascii"))
        for n in range(10):
            check(f"burst: unpaced line {n} ran in full",
                  t.until(f"\r\nburst-{n}-0123456789abcdef\r\n", timeout_s=20), t.seen()[-300:])
    finally:
        t.close()


def session_cat_burst():
    """56 stdio bytes while cat keeps the kernel busy with interrupts off.

    Only the ring keeps these: cat is transmitting, and every transmit drains
    the FIFO into it. Polling receive leaves them in the 16-byte FIFO, and
    the stdio backend's drop at the trigger level truncates the line at 14.
    """
    h = boot_serial("-kernel", build.ELF, "-hda", BIGIMG)
    try:
        if not boot_to_prompt(h, "cat-burst"):
            return
        mark = h.out_len()
        send(h, "cat /big.txt\n")
        if not check("cat-burst: cat started", wait_text(h, "0123456789", mark), repr(text(h, mark))):
            return
        payload = "y" * 50
        next_at = time.perf_counter()
        for byte in ("echo " + payload + "\n").encode("ascii"):
            while time.perf_counter() < next_at:     # time.sleep is too coarse for 4 ms
                pass
            h.proc.stdin.write(bytes((byte,)))
            h.proc.stdin.flush()
            next_at += 0.004
        check("cat-burst: every byte was sent while cat ran",
              "BIGEND" not in text(h, mark), text(h, mark)[-200:])
        check("cat-burst: all 56 bytes arrive",
              wait_text(h, "\r\n" + payload + "\r\n", mark, timeout_s=30), repr(text(h, mark)[-300:]))
    finally:
        stop(h)


def wait_serial_prompt(t, timeout_s=60):
    """COM1 may connect after the boot banner, so prod the shell for a prompt."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        start = len(t.seen())
        t.typed("\r")
        if t.until("$ ", start, timeout_s=1):
            return True
    return False


def wait_quiet(t, idle_s=1.0, timeout_s=60):
    """Wait for COM1 output to stop: a flood's backlog has been worked off."""
    deadline = time.monotonic() + timeout_s
    seen = len(t.got)
    quiet_at = time.monotonic()
    while time.monotonic() < deadline:
        time.sleep(0.1)
        if len(t.got) != seen:
            seen, quiet_at = len(t.got), time.monotonic()
        elif time.monotonic() - quiet_at >= idle_s:
            return True
    return False


def elf_symbol(name):
    """The address of a symbol in the built kernel, from its ELF symbol table."""
    with open(build.ELF, "rb") as fh:
        data = fh.read()
    shoff = struct.unpack_from("<I", data, 32)[0]
    shentsize, shnum = struct.unpack_from("<HH", data, 46)
    sections = [struct.unpack_from("<10I", data, shoff + n * shentsize) for n in range(shnum)]
    symtab = next(sec for sec in sections if sec[1] == 2)        # SHT_SYMTAB
    strtab = sections[symtab[6]]
    wanted = name.encode("ascii") + b"\0"
    for n in range(symtab[5] // 16):
        offset, value = struct.unpack_from("<II", data, symtab[4] + n * 16)
        start = strtab[4] + offset
        if data[start:start + len(wanted)] == wanted:
            return value
    raise RuntimeError(f"{name} is not in {build.ELF}")


def guest_ticks(t, address):
    """g_ticks, read from guest memory: this cannot be lost to a saturated COM1."""
    reply = T._monitor(t.h, f"xp /1wx {address:#x}", timeout_s=30)
    found = re.search(r": (0x[0-9a-f]+)", reply)
    if found is None:
        raise RuntimeError(f"unexpected xp reply: {reply!r}")
    return int(found.group(1), 16)


def answered(t, command, pattern, tries=6, timeout_s=10):
    """Send a command until its reply is seen; the regex match, or None.

    Bytes still arriving from a flood can garble one attempt, so a reply is
    all that is required. A dead shell answers none of them.
    """
    for _ in range(tries):
        start = len(t.seen())
        t.typed("\r" + command + "\r")
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            found = re.search(pattern, t.seen(start))
            if found:
                return found
            time.sleep(0.05)
    return None


class Flood:
    """Send one chunk over and over until the block ends. A small send buffer
    keeps the input ahead of the guest without a long backlog afterwards."""

    def __init__(self, t, chunk):
        self.t, self.chunk = t, chunk
        self.stopping = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        while not self.stopping.is_set():
            self.t.sock.sendall(self.chunk)

    def __enter__(self):
        self.started = time.monotonic()
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.stopping.set()
        self.thread.join(timeout=30)


# Flood progress is measured against work done, never the host's clock: a loaded
# host slows the guest and the sender together. Each command the guest finishes
# prints one prompt. Between batches of input the idle loop opens an interrupt
# window, so ticks keep pace with commands. Measured over 1 s windows, the
# bounded serial_service takes about 1 tick per 9 prompts (worst 1 per 47), idle
# or under load, while an unbounded one takes none (best 1 per 110).
FLOOD_PROMPTS = 1500             # work to observe in each flood
PROMPTS_PER_TICK_MAX = 50        # more than this means the timer is being starved
PS2_PROMPTS_MAX = 300            # commands a queued PS/2 key may wait behind
FLOOD_HANG_S = 45                # only a hang guard; a slow host stays far inside it


def prompts_seen(t, start):
    return t.seen(start).count("$ ")


def ticks_keep_pace(t, label, name, ticks_at):
    """Keep the flood running for FLOOD_PROMPTS commands; ticks must keep pace."""
    start = len(t.seen())
    first = guest_ticks(t, ticks_at)
    deadline = time.monotonic() + FLOOD_HANG_S
    while prompts_seen(t, start) < FLOOD_PROMPTS and time.monotonic() < deadline:
        time.sleep(0.05)
    ticks = guest_ticks(t, ticks_at) - first
    prompts = prompts_seen(t, start)
    check(f"{label}: guest kept working through a {name} flood", prompts >= FLOOD_PROMPTS,
          repr((prompts, ticks)))
    check(f"{label}: ticks advance during a {name} flood",
          ticks > 0 and ticks >= prompts // PROMPTS_PER_TICK_MAX, repr((prompts, ticks)))


def ps2_key_reaches_shell(t, flood):
    """A key must echo within PS2_PROMPTS_MAX commands of QEMU injecting it.

    Commands run while the monitor is still answering sendkey are not counted:
    on a loaded host that call can stall for seconds, which says nothing about
    the kernel. Returns (ok, prompts during the call, prompts after it).
    """
    start = len(t.seen())
    T._monitor(t.h, f"sendkey z {T.KEY_HOLD_MS}", timeout_s=30)
    injected = len(t.seen())
    during = t.seen(start)[:injected - start].count("$ ")
    deadline = time.monotonic() + FLOOD_HANG_S
    while time.monotonic() < deadline and flood.thread.is_alive():
        seen = t.seen(start)
        key_at = seen.find("z")
        after_text = seen[injected - start:] if key_at < 0 else seen[injected - start:key_at]
        after = after_text.count("$ ")
        if key_at >= 0 or after > PS2_PROMPTS_MAX:
            return key_at >= 0 and after <= PS2_PROMPTS_MAX, during, after
        time.sleep(0.02)
    return False, during, None


def flood_checks(label, *boot):
    """A sustained flood must leave the timer and the keyboard running."""
    t = TcpSerial(*boot, sndbuf=4096)
    try:
        t.start_reading()
        if not check(f"{label}: shell is up", wait_serial_prompt(t), t.seen()[-200:]):
            return
        ticks_at = elf_symbol("m_g_ticks")
        with Flood(t, b"\r" * 64) as flood:
            time.sleep(1)
            ok, during, after = ps2_key_reaches_shell(t, flood)
            check(f"{label}: PS/2 key handled during a CR flood", ok,
                  repr((during, after)) + t.seen()[-200:])
            ticks_keep_pace(t, label, "CR", ticks_at)
        wait_quiet(t)

        with Flood(t, b"uptime\r" * 8):
            time.sleep(1)
            ticks_keep_pace(t, label, "line", ticks_at)
        wait_quiet(t)

        low = guest_ticks(t, ticks_at)
        found = answered(t, "uptime", r"uptime: (\d+) s")
        high = guest_ticks(t, ticks_at)
        check(f"{label}: uptime after the flood matches g_ticks",
              found is not None and low // 100 <= int(found.group(1)) <= high // 100,
              repr((low, found and found.group(1), high)))
        check(f"{label}: shell answers after the flood",
              answered(t, "echo flood-alive", r"\r\nflood-alive\r\n") is not None,
              t.seen()[-200:])
    finally:
        t.close()


def session_flood():
    flood_checks("flood", "-kernel", build.ELF)


def session_iso_flood():
    flood_checks("iso-flood", "-cdrom", build.ISO)


def session_lsr_overrun():
    """Overruns reach the counter, and no LSR read can eat one uncounted.

    Reading the LSR clears its overrun bit, so a read that ignores the bit loses
    the report. A guest paused by the monitor rarely sits between the receive
    read and the transmit wait's read, and while the backend refuses output a
    loopback write makes no overrun at all, so the boot below catches a lost
    report only sometimes. The dependable guard is the source check: only these
    two functions may read the LSR.
    """
    with open(os.path.join(HERE, "kmain.mx"), encoding="utf-8") as fh:
        source = fh.read()
    readers = set()
    for chunk in re.split(r"(?m)^(?=fn )", source)[1:]:
        if "inb(0x3FD)" in chunk:
            readers.add(re.match(r"fn (\w+)", chunk).group(1))
    check("lsr: every LSR read after init goes through serial_lsr",
          readers == {"serial_init", "serial_lsr"}, repr(sorted(readers)))

    rounds = 10
    t = TcpSerial("-kernel", build.ELF, "-hda", BIGIMG)
    try:
        t.start_reading()
        if not check("lsr: shell is up", wait_serial_prompt(t), t.seen()[-200:]):
            return
        start = len(t.seen())
        t.typed("cat /big.txt\r")
        check("lsr: cat started", t.until("0123456789", start), t.seen(start)[-200:])
        for _ in range(rounds):
            T._monitor(t.h, "stop")
            T._monitor(t.h, "o /b 0x3fc 0x1e")       # MCR: loopback
            for _ in range(20):
                T._monitor(t.h, "o /b 0x3f8 0x2e")   # more than the FIFO holds
            T._monitor(t.h, "o /b 0x3fc 0x0b")       # MCR: normal operation
            T._monitor(t.h, "cont")
            time.sleep(0.1)
        wait_quiet(t, idle_s=2)
        t.typed("\r")
        wait_quiet(t)
        counters = serial_counters(t)
        check(f"lsr: all {rounds} overruns counted",
              counters is not None and counters[0] >= rounds, repr(counters))
    finally:
        t.close()


def session_exec_paced():
    """Input paced over stdio while exec loads, then reaches the program."""
    h = boot_serial("-kernel", build.ELF, "-hda", IMG)
    try:
        if not boot_to_prompt(h, "exec-paced"):
            return
        name = "x" * 37
        mark = h.out_len()
        send(h, "exec /bin/ask.bin\n" + name + "\n")     # no wait for its prompt
        check("exec-paced: 37 bytes during exec all arrive",
              wait_text(h, "hello, " + name, mark, timeout_s=15), repr(text(h, mark)))
    finally:
        stop(h)


def serial_counters(t):
    """Run `serial` and return its three counters."""
    start = len(t.seen())
    t.typed("serial\r")
    if not t.until("tx-dropped", start, timeout_s=15):
        return None
    t.until("$ ", start)
    found = re.search(r"overrun (\d+) ring-lost (\d+) tx-dropped (\d+)", t.seen(start))
    return tuple(int(n) for n in found.groups()) if found else None


def session_overflow():
    """More input than the ring holds, while a long command keeps the shell busy."""
    t = TcpSerial("-kernel", build.ELF, "-hda", BIGIMG)
    try:
        T.wait_for(t.h, "$ ", timeout_s=30)
        t.start_reading()
        t.typed("cat /big.txt\r")
        t.sock.sendall(b"x" * 4000 + b"\r")
        check("overflow: output reached serial", t.until("BIGEND", timeout_s=60), t.seen()[-200:])
        time.sleep(3)                # the leftover input runs as one bad command
        t.typed("\r")
        counters = serial_counters(t)
        check("overflow: lost input is counted", counters is not None and counters[1] > 0, repr(counters))
        start = len(t.seen())
        t.typed("echo overflow-alive\r")
        check("overflow: shell still answers", t.until("\r\noverflow-alive\r\n", start), t.seen(start))
    finally:
        t.close()


def session_stall():
    """A reader that stops reading must not cost us the serial console."""
    t = TcpSerial("-kernel", build.ELF, "-hda", BIGIMG, rcvbuf=2048)
    try:
        T.wait_for(t.h, "$ ", timeout_s=30)
        for n in range(4):           # nothing reads the socket: 240 KB backs up
            t.typed("cat /big.txt\r")
            t.typed(f"echo stalled-{n}\r")
            check(f"stall: shell runs with the reader stalled ({n})",
                  T.wait_for(t.h, f"stalled-{n}", timeout_s=40), T.screen_text(t.h))
        t.start_reading()
        time.sleep(3)
        start = len(t.seen())
        t.typed("echo stall-recovered\r")
        check("stall: serial input and output recover",
              t.until("\r\nstall-recovered\r\n", start, timeout_s=20), t.seen(start)[-200:])
        counters = serial_counters(t)
        check("stall: dropped output is counted", counters is not None and counters[2] > 0, repr(counters))
    finally:
        t.close()


def session_ps2_alongside():
    """One boot, both inputs: PS/2 (monitor on a socket) and serial (stdio)."""
    port = free_port()
    h = spawn(["-serial", "stdio", "-monitor",
               f"tcp:127.0.0.1:{port},server=on,wait=off", "-kernel", build.ELF])
    try:
        if not boot_to_prompt(h, "ps2"):
            return
        with socket.create_connection(("127.0.0.1", port), timeout=10) as sock:
            mark = h.out_len()
            sendkeys(sock, "echo from-ps2")
            check("ps2: keyboard command output is mirrored to serial",
                  wait_text(h, "\r\nfrom-ps2\r\n", mark), repr(text(h, mark)))
            wait_until(h, at_prompt, mark)
            out = run(h, "echo from-serial")
            check("ps2: serial still works after keyboard use",
                  "\r\nfrom-serial\r\n" in out, repr(out))
            mark = h.out_len()
            sendkeys(sock, "echo ps2-again")
            check("ps2: keyboard still works after serial use",
                  wait_text(h, "\r\nps2-again\r\n", mark), repr(text(h, mark)))
    finally:
        stop(h)


def screendump(sendcmd, name):
    """A real QEMU screendump; returns (width, height, RGB bytes)."""
    path = os.path.join(TMP, name).replace(os.sep, "/")
    sendcmd(f"screendump {path}")
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        time.sleep(0.5)
        if os.path.exists(path) and os.path.getsize(path) > 100000:
            break
    time.sleep(0.5)              # the header is written before the pixels
    return parse_ppm(path)


def parse_ppm(path):
    with open(path, "rb") as fh:
        data = fh.read()
    idx, fields = 2, []
    while len(fields) < 3:
        while data[idx] in b" \t\n\r":
            idx += 1
        start = idx
        while data[idx] not in b" \t\n\r":
            idx += 1
        fields.append(int(data[start:idx]))
    return fields[0], fields[1], data[idx + 1:]


def region_diff(a, b, x0, y0, x1, y1):
    """How many pixels differ between two dumps inside a rectangle."""
    w = a[0]
    return sum(1 for y in range(y0, y1) for x in range(x0, x1)
               if a[2][(y * w + x) * 3:(y * w + x) * 3 + 3] != b[2][(y * w + x) * 3:(y * w + x) * 3 + 3])


def is_surface(dump):
    """Limine is dark; the Borehole sky at this point is light."""
    w, _, px = dump
    o = (40 * w + 500) * 3
    return px[o] + px[o + 1] + px[o + 2] > 300


def iso_monitor_boot(*args):
    """ISO on a monitor-on-stdio QEMU, up to a settled Surface screen."""
    h = spawn(["-monitor", "stdio", "-cdrom", build.ISO, *args])
    T._wait_first_prompt(h)
    mon = lambda cmd: T._monitor(h, cmd)
    deadline = time.monotonic() + 60
    n = 0
    while time.monotonic() < deadline:
        n += 1
        time.sleep(1)
        if is_surface(screendump(mon, f"probe{h.proc.pid}-{n}.ppm")):
            break
    time.sleep(4)                # let the reveal finish
    return h, mon


def session_iso():
    """Limine boots to the Surface screen; serial must still reach the shell."""
    port = free_port()
    h = spawn(["-serial", "stdio", "-monitor", f"tcp:127.0.0.1:{port},server=on,wait=off",
               "-cdrom", build.ISO])
    try:
        if not boot_to_prompt(h, "iso"):
            return
        with socket.create_connection(("127.0.0.1", port), timeout=10) as sock:
            mon = lambda cmd: sock.sendall(cmd.encode("ascii") + b"\n")
            mark = h.out_len()
            send(h, "echo iso-$USER\n")
            check("iso: serial command runs from the Surface screen",
                  wait_text(h, "\r\niso-mortuex\r\n", mark), repr(text(h, mark)))
            wait_until(h, at_prompt, mark)
            time.sleep(1)
            before = screendump(mon, f"iso-before-{h.proc.pid}.ppm")
            out = run(h, "echo " + "z" * 40)
            check("iso: shell keeps answering", ("z" * 40 + "\r\n") in out, repr(out))
            time.sleep(1)
            after = screendump(mon, f"iso-after-{h.proc.pid}.ppm")
            check("iso: the framebuffer console drew it too",
                  region_diff(before, after, 0, 60, 1024, 700) > 200,
                  region_diff(before, after, 0, 60, 1024, 700))
    finally:
        stop(h)


def session_iso_no_uart():
    """-serial none must be visible on the Surface screen, not only in a log."""
    h, mon = iso_monitor_boot("-serial", "none")
    try:
        absent = screendump(mon, f"nouart-{h.proc.pid}.ppm")
    finally:
        h.watchdog.cancel()
        T.shutdown(h)
    log = os.path.join(TMP, "present.log").replace(os.sep, "/")
    h, mon = iso_monitor_boot("-serial", f"file:{log}")
    try:
        present = screendump(mon, f"uart-{h.proc.pid}.ppm")
    finally:
        h.watchdog.cancel()
        T.shutdown(h)
    changed = region_diff(absent, present, 720, 8, 920, 30)
    check("iso-no-uart: Surface shows the report only without a UART", changed > 100, changed)


def session_iso_junk():
    """NUL and 0xFF type nothing, so they must not leave the Surface screen."""
    port = free_port()
    h = spawn(["-serial", "stdio", "-monitor", f"tcp:127.0.0.1:{port},server=on,wait=off",
               "-cdrom", build.ISO])
    try:
        if not boot_to_prompt(h, "junk"):
            return
        time.sleep(6)            # the reveal must have finished
        with socket.create_connection(("127.0.0.1", port), timeout=10) as sock:
            mon = lambda cmd: sock.sendall(cmd.encode("ascii") + b"\n")
            before = screendump(mon, f"junk-a-{h.proc.pid}.ppm")
            mark = h.out_len()
            for byte in (0, 255, 0, 255):
                h.proc.stdin.write(bytes((byte,)))
                h.proc.stdin.flush()
                time.sleep(0.05)
            time.sleep(2)
            after = screendump(mon, f"junk-b-{h.proc.pid}.ppm")
            changed = region_diff(before, after, 60, 180, 1000, 760)
            check("iso-junk: Surface screen untouched", changed < 50, changed)
            check("iso-junk: nothing echoed", text(h, mark) == "", repr(text(h, mark)))
            mark = h.out_len()
            send(h, "echo junk-then-ok\n")
            check("iso-junk: real input still reaches the shell",
                  wait_text(h, "\r\njunk-then-ok\r\n", mark), repr(text(h, mark)))
    finally:
        stop(h)


def session_iso_lock():
    """Input typed at the lock screen is discarded, never run after unlock."""
    port = free_port()
    h = spawn(["-serial", "stdio", "-monitor", f"tcp:127.0.0.1:{port},server=on,wait=off",
               "-cdrom", build.ISO])
    try:
        if not boot_to_prompt(h, "lock"):
            return
        with socket.create_connection(("127.0.0.1", port), timeout=10) as sock:
            mark = h.out_len()
            send(h, "lock\n")
            time.sleep(3)
            mark = h.out_len()
            send(h, "mort\n")
            time.sleep(1)
            sendkeys(sock, "mort")   # the real unlock, on the keyboard
            time.sleep(4)
            typed_after = text(h, mark)
            check("lock: serial bytes are discarded, not echoed or run",
                  "mort" not in typed_after and "unknown" not in typed_after, repr(typed_after))
            out = run(h, "echo after-unlock")
            check("lock: shell works after a keyboard unlock",
                  "\r\nafter-unlock\r\n" in out and "mort" not in out, repr(out))
    finally:
        stop(h)


def session_iso_fault():
    """Exception and shutdown screens bypass put_cell_at; serial must see them."""
    h = boot_serial("-cdrom", build.ISO)
    try:
        if not boot_to_prompt(h, "fault"):
            return
        send(h, "crash\n")
        check("fault: exception report on serial",
              wait_text(h, "*** CPU EXCEPTION #6 -- HALTED ***", timeout_s=15), repr(text(h)[-200:]))
    finally:
        stop(h)
    h = boot_serial("-cdrom", build.ISO)
    try:
        if not boot_to_prompt(h, "capped"):
            return
        send(h, "shutdown\n")
        check("capped: shutdown notice on serial",
              wait_text(h, "It is now safe to turn off your computer.", timeout_s=15), repr(text(h)[-200:]))
    finally:
        stop(h)


def session_no_uart():
    """-serial none removes the 16550; the kernel must say so and carry on."""
    h = spawn(["-serial", "none", "-monitor", "stdio", "-kernel", build.ELF])
    try:
        T._wait_first_prompt(h)
        check("no-uart: banner still on VGA", T.wait_for(h, "MORT OS", timeout_s=30),
              T.screen_text(h))
        check("no-uart: VGA reports serial unavailable",
              T.wait_for(h, "serial: COM1 unavailable", timeout_s=10), T.screen_text(h))
        T.type_line(h, "echo no-uart-ok")
        check("no-uart: shell works from PS/2", T.wait_for(h, "no-uart-ok", timeout_s=15),
              T.screen_text(h))
    finally:
        h.watchdog.cancel()
        T.shutdown(h)


SESSIONS = {f.__name__.replace("session_", ""): f for f in (
    session_text, session_line_endings, session_escape, session_burst, session_cat_burst,
    session_exec_paced, session_polled_input, session_ps2_alongside, session_overflow,
    session_stall, session_lsr_overrun, session_flood, session_no_uart, session_iso,
    session_iso_no_uart, session_iso_junk, session_iso_lock, session_iso_fault,
    session_iso_flood)}


def prepare_images(compile_programs):
    bins = []
    for mx in build._program_sources():
        out = os.path.join(build.BUILD, os.path.splitext(os.path.basename(mx))[0] + ".bin")
        if compile_programs:
            build.build_program(mx, out)
        bins.append((out, os.path.basename(out)))
    mkfs.make(IMG, bins=bins)
    big = os.path.join(TMP, "big.txt")
    with open(big, "w", newline="\n") as fh:
        fh.write(("0123456789" * 6 + "\n") * 980 + "BIGEND\n")
    mkfs.make(BIGIMG, adds=[(big, "big.txt")])


def main():
    if not build._find_qemu():
        sys.exit("qemu-system-i386 not found")
    args = sys.argv[1:]
    no_build = "--no-build" in args
    names = [a for a in args if a != "--no-build"] or list(SESSIONS)
    unknown = [n for n in names if n not in SESSIONS]
    if unknown:
        sys.exit(f"unknown session(s) {unknown}; choose from {list(SESSIONS)}")
    if not no_build:
        build.iso()              # builds kernel.elf too
    prepare_images(compile_programs=not no_build)
    for name in names:
        SESSIONS[name]()
    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
