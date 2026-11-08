#!/usr/bin/env python3
"""Serial console acceptance test. Boots the real kernel in QEMU with COM1 on
QEMU's stdio pipe, asserts the boot banner arrives on serial, and drives the
shell purely over serial, in lock-step (send a line, wait for the prompt).

    python test_serial.py

Covers the text (-kernel) and graphical (Limine ISO) paths, the polled input
paths (sudo password, a program's read-line syscall), PS/2 used alongside
serial, and a machine with no UART. Prints the COM1 transcript of the first
boot. Needs QEMU + the ISO toolchain. Exit code 0 = all passed.

Host-side bytes are paced, one per kernel tick: the kernel drains the UART at
100 Hz, and QEMU's Windows stdio backend drops a byte instead of waiting when
the FIFO is at its trigger level. That backend also strips CR, so stdio lines
end in LF and the CR handling is tested over a raw TCP serial port.
"""
import os
import re
import socket
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
    bins = []
    for mx in build._program_sources():
        out = os.path.join(build.BUILD, os.path.splitext(os.path.basename(mx))[0] + ".bin")
        build.build_program(mx, out)
        bins.append((out, os.path.basename(out)))
    mkfs.make(IMG, bins=bins)

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


def session_line_endings():
    """CR and CRLF, over a raw TCP serial port (see the module docstring)."""
    port = free_port()
    h = spawn(["-serial", f"tcp:127.0.0.1:{port},server=on,wait=off",
               "-monitor", "none", "-kernel", build.ELF])
    got = bytearray()

    def pump(sock):
        while True:
            try:
                chunk = sock.recv(4096)
            except OSError:
                return
            if not chunk:
                return
            got.extend(chunk)

    def seen():
        return bytes(got).decode("ascii", "replace")

    def until(needle, start):
        deadline = time.monotonic() + 30
        while needle not in seen()[start:] and time.monotonic() < deadline:
            time.sleep(0.05)
        return needle in seen()[start:]

    def typed(sock, data):
        for byte in data.encode("ascii"):
            sock.sendall(bytes((byte,)))
            time.sleep(BYTE_GAP_S)

    try:
        time.sleep(5)                # let the kernel reach its prompt first
        with socket.create_connection(("127.0.0.1", port), timeout=10) as sock:
            sock.settimeout(None)
            threading.Thread(target=pump, args=(sock,), daemon=True).start()
            typed(sock, "echo ready\r")   # output before we connected is gone
            if not check("endings: CR ends a line", until("\r\nready\r\n", 0), repr(seen())):
                return
            until("$ ", seen().index("ready\r\n"))
            start = len(seen())
            typed(sock, "echo crlf-ok\r\n")
            until("\r\ncrlf-ok\r\n", start)
            time.sleep(1)            # room for a wrong second prompt to show up
            out = seen()[start:]
            check("endings: CRLF is one Enter, not two", out.count("$ ") == 1, repr(out))
    finally:
        stop(h)


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


def session_iso():
    """Limine boots to the graphical launcher; serial must still reach the shell."""
    h = boot_serial("-cdrom", build.ISO)
    try:
        if not boot_to_prompt(h, "iso"):
            return
        mark = h.out_len()
        send(h, "echo iso-$USER\n")
        check("iso: serial command runs from the launcher screen",
              wait_text(h, "\r\niso-mortuex\r\n", mark), repr(text(h, mark)))
        wait_until(h, at_prompt, mark)
        out = run(h, "uptime")
        check("iso: shell keeps answering", re.search(r"uptime: \d+ s", out) is not None, repr(out))
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


def main():
    if not build._find_qemu():
        sys.exit("qemu-system-i386 not found")
    build.iso()                  # builds kernel.elf too
    for session in (session_text, session_line_endings, session_polled_input,
                    session_ps2_alongside, session_iso, session_no_uart):
        session()
    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
