#!/usr/bin/env python3
"""Graphics-mode acceptance test. Builds the bootable ISO, boots it headless in
QEMU (the Limine path provides a linear framebuffer), and screendumps the
framebuffer to assert the desktop, the console, and app-switching all render.

    python kernel/test_gfx.py

Needs QEMU + the ISO toolchain (Limine/xorriso, downloaded+cached by build.py).
Stdlib only — parses the PPM screendump directly, no Pillow.
"""
import os
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)
import build  # noqa: E402

passed = 0
failed = 0
TMP = tempfile.mkdtemp(prefix="mortgfx-")


def check(label, ok):
    global passed, failed
    if ok:
        passed += 1
        print(f"PASS: {label}")
    else:
        failed += 1
        print(f"FAIL: {label}")


def parse_ppm(path):
    with open(path, "rb") as fh:
        data = fh.read()
    if data[:2] != b"P6":
        raise ValueError("not a P6 ppm")
    idx, fields = 2, []
    while len(fields) < 3:
        while data[idx] in b" \t\n\r":
            idx += 1
        start = idx
        while data[idx] not in b" \t\n\r":
            idx += 1
        fields.append(int(data[start:idx]))
    idx += 1
    w, h, _ = fields
    if len(data) - idx != w * h * 3:
        raise ValueError("incomplete P6 pixel payload")
    return w, h, data[idx:]


def main():
    build.iso()  # -> build/mort.iso (uses cached Limine/xorriso)
    build.ensure_disk()
    iso = os.path.join(build.BUILD, "mort.iso")
    qemu = build._find_qemu()
    if not qemu:
        sys.exit("qemu-system-i386 not found")

    p = subprocess.Popen([qemu, "-cdrom", iso, "-boot", "d",
                          "-hda", build.DISK,
                          "-display", "none", "-monitor", "stdio"],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, bufsize=0)

    def drain(s):
        while s.read(1):
            pass

    for s in (p.stdout, p.stderr):
        threading.Thread(target=drain, args=(s,), daemon=True).start()

    def key(k):
        p.stdin.write(f"sendkey {k}\n".encode())
        p.stdin.flush()
        time.sleep(0.1)

    n = [0]

    def capture():
        n[0] += 1
        ppm = os.path.join(TMP, f"s{n[0]}.ppm")
        p.stdin.write(f"screendump {ppm.replace(chr(92), '/')}\n".encode())
        p.stdin.flush()
        deadline = time.monotonic() + 8
        while True:
            try:
                if os.path.getsize(ppm) > 32:
                    return parse_ppm(ppm)
            except (OSError, ValueError, IndexError):
                pass
            if time.monotonic() >= deadline:
                raise RuntimeError("QEMU screendump did not become a complete P6 image")
            time.sleep(0.2)

    try:
        # Limine's countdown follows guest virtual time, which can advance
        # slowly on busy CI hosts. Poll the actual framebuffer signature rather
        # than typing into the boot menu after a fixed host-side sleep.
        deadline = time.monotonic() + 40
        w, h, px = 0, 0, b""
        while time.monotonic() < deadline:
            w, h, px = capture()
            if (w, h) == (1024, 768):
                offset = (3 * w + 150) * 3
                if tuple(px[offset:offset + 3]) == (11, 13, 20):
                    break
            time.sleep(1)

        def rgb(x, y, buf=None):
            b = buf if buf is not None else px
            o = (y * w + x) * 3
            return b[o], b[o + 1], b[o + 2]

        ACCENT = (135, 123, 255)   # MortuexOS iris accent (0x877bff)
        TOPBAR = (11, 13, 20)      # current top bar (0x0b0d14)
        DOCK = (25, 28, 40)        # dock/title surface (0x191c28)

        check("framebuffer is 1024x768", (w, h) == (1024, 768))
        check("MortuexOS desktop top bar rendered", rgb(150, 3) == TOPBAR)
        check("Home launcher is visible at boot",
              rgb(500, 90) == (18, 20, 29)
              and rgb(170, 320) == ACCENT)

        # F1 is global even while Home owns the overlay.
        key("f1")
        time.sleep(0.4)
        for ch in "help":
            key(ch)
        key("ret")
        _, _, px1 = capture()
        check("F1 opens the terminal from Home",
              rgb(500, 172, px1) == DOCK
              and rgb(530, 748, px1) == ACCENT)
        # console has non-background pixels => glyphs rendered
        bg = (11, 15, 20)
        text_pixels = 0
        y = 196
        while y < 340 and text_pixels < 50:
            x = 192
            while x < 640:
                if rgb(x, y, px1) != bg:
                    text_pixels += 1
                x += 1
            y += 1
        check("console shows rendered glyph pixels", text_pixels >= 50)

        # switch to Files (F2)
        key("f2")
        time.sleep(0.4)
        _, _, px2 = capture()
        check("Files dock icon is active after F2",
              rgb(580, 748, px2) == ACCENT)
        check("Terminal dock icon is inactive after F2",
              rgb(530, 748, px2) == DOCK)

        # switch to Vex (F3)
        key("f3")
        time.sleep(0.4)
        _, _, px3 = capture()
        check("canonical Vex shell and dock state render after F3",
              rgb(630, 748, px3) == ACCENT
              and rgb(64, 64, px3) == (18, 16, 13))

        # back to terminal (F1)
        key("f1")
        time.sleep(0.4)
        _, _, px4 = capture()
        check("Terminal dock icon is active again after F1",
              rgb(530, 748, px4) == ACCENT)
    finally:
        try:
            p.stdin.write(b"quit\n")
            p.stdin.flush()
            time.sleep(0.5)
        except Exception:
            pass
        p.kill()

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
