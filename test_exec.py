#!/usr/bin/env python3
"""Program-execution acceptance test. Builds the sample Mort programs, seeds
them onto a fresh MortFS image, boots the kernel in QEMU, and `exec`s them —
proving a Mort program compiled to a flat binary loads off disk, runs at
0x00A00000, makes int 0x80 syscalls, and returns to the shell.

    python test_exec.py

Needs QEMU + `pip install ziglang`. Scratch image goes to the temp dir.
"""
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import build  # noqa: E402  (compile programs + reuse the mkfs seeder)
import mkfs  # noqa: E402
import test as T  # noqa: E402  (QEMU harness)

TMP = tempfile.mkdtemp(prefix="mortexec-test-")
IMG = os.path.join(TMP, "exec.img")

passed = 0
failed = 0


def check(label, ok, h=None):
    global passed, failed
    if ok:
        passed += 1
        print(f"PASS: {label}")
    else:
        failed += 1
        print(f"FAIL: {label}")
        if h is not None:
            print(T.screen_text(h))


def main():
    # build every sample program to a flat binary, then seed them raw
    bins = []
    for mx in build._program_sources():
        out = os.path.join(build.BUILD, os.path.splitext(os.path.basename(mx))[0] + ".bin")
        build.build_program(mx, out)
        bins.append((out, os.path.basename(out)))
    mkfs.make(IMG, bins=bins)
    print(f"seeded {len(bins)} program(s) into {IMG}")

    h = T.boot(disk_img=IMG)
    try:
        check("boot banner", T.wait_for(h, "MORT OS"), h)
        # the kernel moves seeded *.bin files from / into /bin on first boot
        T.type_line(h, "ls /bin")
        check("ls shows hello.bin", T.wait_for(h, "hello.bin", timeout_s=15), h)
        check("ls shows count.bin", T.wait_for(h, "count.bin", timeout_s=15), h)

        T.type_line(h, "exec /bin/hello.bin")
        check("exec hello: syscall output",
              T.wait_for(h, "hello from a real mort program!", timeout_s=15), h)
        T.type_line(h, "echo back-in-shell")
        check("shell alive after program returns",
              T.wait_for(h, "back-in-shell", timeout_s=15), h)

        T.type_line(h, "exec /bin/count.bin")
        check("exec count: prints 'one'", T.wait_for(h, "one", timeout_s=15), h)
        check("exec count: prints 'three'", T.wait_for(h, "three", timeout_s=15), h)

        # interactive program: it prompts, reads a line via syscall, greets
        T.type_line(h, "exec /bin/ask.bin")
        check("interactive program prompts",
              T.wait_for(h, "what is your name?", timeout_s=15), h)
        T.type_line(h, "fadi")
        check("interactive program reads input + greets",
              T.wait_for(h, "hello, fadi", timeout_s=15), h)

        T.type_line(h, "exec nope.bin")
        check("exec missing program errors",
              T.wait_for(h, "not found: nope.bin", timeout_s=15), h)
        # the shell must survive an interactive program cleanly
        T.type_line(h, "echo shell-still-ok")
        check("shell alive after interactive program",
              T.wait_for(h, "shell-still-ok", timeout_s=15), h)
    finally:
        T.shutdown(h)

    userland()
    print(f"\nexec: {passed} passed, {failed} failed; userland: {ulpassed} passed, {ulfailed} failed")
    return 1 if failed or ulfailed else 0


# ----- userland programs, driven over COM1 (each output is the program's own) -----

BIG_END = "big-file-last-line"
ulpassed = 0
ulfailed = 0


def ul_check(label, ok, detail=None):
    global ulpassed, ulfailed
    if ok:
        ulpassed += 1
        print(f"PASS: {label}")
    else:
        ulfailed += 1
        print(f"FAIL: {label}\n--- detail ---\n{detail!r}\n--------------")
    return ok


def exit_status(S, h):
    """The shell's $? as an int (a line holding nothing but digits)."""
    out = S.run(h, "echo $?")
    found = re.search(r"\r\n(\d+)\r\n", out)
    return int(found.group(1)) if found else None


def userland():
    import test_serial as S  # the COM1 lock-step helpers

    big = os.path.join(TMP, "big.txt")
    with open(big, "w", newline="\n") as fh:     # spans several 512-byte sectors
        for n in range(120):
            fh.write(f"line {n:03d} of the big file\n")
        fh.write(BIG_END + "\n")
    bins = [(os.path.join(build.BUILD, os.path.splitext(os.path.basename(mx))[0] + ".bin"),
             os.path.splitext(os.path.basename(mx))[0] + ".bin")
            for mx in build._program_sources()]
    ul_img = os.path.join(TMP, "userland.img")
    mkfs.make(ul_img, adds=[(big, "big.txt")], bins=bins)

    h = S.boot_serial("-kernel", build.ELF, "-hda", ul_img)
    try:
        if not ul_check("userland: boots to a shell on COM1",
                        S.boot_to_prompt(h, "userland")):
            return

        def run(line, t=30):
            return S.run(h, line, timeout_s=t)

        # --- echo: an executable that only sees argv ---
        out = run('echo one   two "three  four"')
        ul_check("echo: separate words joined by one space, quotes grouped",
                 "\r\none two three  four\r\n" in out, out)
        ul_check("echo: exits 0", exit_status(S, h) == 0, out)
        out = run("ps -a")
        ul_check("echo: really ran as a program (exited record in ps -a)",
                 re.search(r"exited\s+0\s+\d+\s+echo\b", out) is not None, out)

        # --- cat: several files, multi-sector read, error paths, exit status ---
        run("write a.txt alpha-text")           # the default user owns only its home
        run("write b.txt bravo-text")
        out = run("cat a.txt b.txt")
        ul_check("cat: concatenates two files in order",
                 "alpha-text" in out and "bravo-text" in out
                 and out.index("alpha-text") < out.index("bravo-text", out.index("alpha-text")),
                 out)
        ul_check("cat: exits 0 when every file is read", exit_status(S, h) == 0, out)
        out = run("cat /big.txt")
        ul_check("cat: reads a file across sector boundaries",
                 "line 000 of the big file" in out and BIG_END in out, out[-300:])
        out = run("cat /nope.txt")
        ul_check("cat: missing file message", "cat: not found: /nope.txt" in out, out)
        ul_check("cat: missing file exits 1", exit_status(S, h) == 1, out)
        out = run("cat /bin")
        ul_check("cat: directory message", "cat: is a directory: /bin" in out, out)
        out = run("cat")
        ul_check("cat: usage message", "usage: cat <file>..." in out, out)
        ul_check("cat: usage exits 2", exit_status(S, h) == 2, out)

        # --- ls: own listing, errors, exit status ---
        out = run("ls /bin")
        for prog in ("cat.bin", "echo.bin", "ed.bin", "hello.bin", "kill.bin", "ls.bin", "ps.bin"):
            ul_check(f"ls: lists {prog}", prog in out, out)
        ul_check("ls: type, mode and size columns",
                 re.search(r"- 755\s+ls\.bin\s+\d+ bytes\s+uid 0", out) is not None, out)
        ul_check("ls: exits 0", exit_status(S, h) == 0, out)
        out = run("ls /big.txt")
        ul_check("ls: non-directory message", "ls: not a directory: /big.txt" in out, out)
        out = run("ls /nope")
        ul_check("ls: missing directory message", "ls: not found: /nope" in out, out)
        ul_check("ls: missing directory exits 1", exit_status(S, h) == 1, out)
        out = run("ls /bin /nope")
        ul_check("ls: reports the failing argument of several",
                 "ls: not found: /nope" in out and "ps.bin" in out, out)

        # --- ps: the genuine process table ---
        out = run("ps")
        ul_check("ps: kernel is pid 1",
                 re.search(r"\b1\s+running\s+-\s+0\s+kernel\b", out) is not None, out)
        me = re.search(r"\b(\d+)\s+running\s+-\s+\d+\s+ps\b", out)
        ul_check("ps: lists itself as running", me is not None, out)
        ul_check("ps: without -a shows only live processes", "exited" not in out, out)
        out2 = run("ps")
        me2 = re.search(r"\b(\d+)\s+running\s+-\s+\d+\s+ps\b", out2)
        ul_check("ps: a new run is a new pid",
                 me is not None and me2 is not None and int(me2.group(1)) > int(me.group(1)),
                 out2)

        # --- kill: the honest outcomes ---
        out = run("kill 1")
        ul_check("kill: refuses the kernel", "kill: 1: operation not permitted" in out, out)
        ul_check("kill: refused exits 1", exit_status(S, h) == 1, out)
        out = run("kill 99999")
        ul_check("kill: unknown pid", "kill: 99999: no such process" in out, out)
        ul_check("kill: unknown pid exits 1", exit_status(S, h) == 1, out)
        out = run("kill nope")
        ul_check("kill: bad pid is a usage error", "usage: kill <pid>" in out, out)
        ul_check("kill: usage exits 2", exit_status(S, h) == 2, out)
        if me2 is not None:                      # the last ps above has exited
            old = me2.group(1)
            out = run(f"kill {old}")
            ul_check("kill: an exited pid is gone",
                     f"kill: {old}: no such process" in out, out)
        # kill aimed at itself: the next pid handed out is the kill program's own.
        out = run("ps")
        pid = re.search(r"\b(\d+)\s+running\s+-\s+\d+\s+ps\b", out)
        if ul_check("kill: can find the next pid", pid is not None, out):
            self_pid = int(pid.group(1)) + 1
            out = run(f"kill {self_pid}")
            ul_check("kill: terminating itself prints no error",
                     "no such process" not in out and "not permitted" not in out, out)
            ul_check("kill: a killed process exits 143", exit_status(S, h) == 143, out)
            out = run("ps -a")
            ul_check("kill: the killed process is recorded with status 143",
                     re.search(r"exited\s+143\s+\d+\s+kill\b", out) is not None, out)

        # --- a program started by a script must not disturb the rest of the script ---
        run("write job.txt echo job-line-one")
        run("write job.txt ls /bin")
        run("write job.txt echo job-line-three")
        out = run("run job.txt")
        ul_check("run: script survives programs (regression: FILEBUF clobber)",
                 "job-line-one" in out and "ps.bin" in out and "job-line-three" in out, out)

        # --- the kernel's path limits reach the program as an error ---
        out = run("cat /" + "a" * 30)
        ul_check("syscall: an over-long name is refused", "cat: name too long:" in out, out)

        # --- ed: edits a file through the file syscalls ---
        def ed_lines(*lines):
            """Send editor input one line at a time, returning all output."""
            mark = h.out_len()
            for line in lines:
                sent = h.out_len()
                S.send(h, line + "\n")
                S.wait_until(h, lambda t: t.endswith(": ") or t.endswith("$ "), sent, 15)
            return S.text(h, mark)

        out = ed_lines("ed note.txt")
        ul_check("ed: reports a new file", "new file" in out, out)
        out = ed_lines("a", "alpha", "gamma", ".", "i 2", "beta", ".", "l")
        ul_check("ed: append and insert, in order",
                 re.search(r"1  alpha\r\n\s+2  beta\r\n\s+3  gamma", out) is not None, out)
        out = ed_lines("q")
        ul_check("ed: refuses to quit with unsaved changes", "unsaved changes" in out, out)
        out = ed_lines("d 3", "c 1 ALPHA", "d 9", "w")
        ul_check("ed: rejects a line that does not exist", "no such line" in out, out)
        ul_check("ed: writes the file", "wrote 2 lines" in out, out)
        out = ed_lines("q")
        ul_check("ed: quits to the shell once saved", out.endswith("$ "), out)
        ul_check("ed: exits 0", exit_status(S, h) == 0, out)
        out = run("cat note.txt")
        ul_check("ed: the saved file holds the edits",
                 "ALPHA\r\nbeta\r\n" in out and "gamma" not in out and "alpha" not in out, out)
        out = ed_lines("ed note.txt", "c 2 BETA", "w", "q")
        ul_check("ed: reopens the saved file", "2 lines" in out, out)
        out = run("cat note.txt")
        ul_check("ed: rewriting replaces rather than appends",
                 "ALPHA\r\nBETA\r\n" in out and out.count("ALPHA") == 1, out)
        out = ed_lines("ed /denied.txt", "a", "x", ".", "w", "q!")
        ul_check("ed: reports a write the kernel refuses",
                 "ed: permission denied: /denied.txt" in out, out)
        out = run("ed")
        ul_check("ed: usage message", "usage: ed <file>" in out, out)
        ul_check("ed: usage exits 2", exit_status(S, h) == 2, out)

        # --- the shell still works around all of that ---
        out = run("no-such-program-here")
        ul_check("status: unknown command exits 127", exit_status(S, h) == 127, out)
        out = run("exec /bin/hello.bin")
        ul_check("exec: arguments stay optional", "goodbye." in out, out)
        out = run("echo still-alive")
        ul_check("shell: alive after the whole session", "still-alive" in out, out)

        print("--- COM1 transcript (userland) ---")
        print(S.text(h))
        print("----------------------------------")
    finally:
        S.stop(h)


def userland_only():
    """The COM1 half alone: python test_exec.py userland"""
    for mx in build._program_sources():
        out = os.path.join(build.BUILD, os.path.splitext(os.path.basename(mx))[0] + ".bin")
        build.build_program(mx, out)
    userland()
    print(f"\nuserland: {ulpassed} passed, {ulfailed} failed")
    return 1 if ulfailed else 0


if __name__ == "__main__":
    sys.exit(userland_only() if sys.argv[1:] == ["userland"] else main())
