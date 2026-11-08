#!/usr/bin/env python3
"""Graphics acceptance test for the Borehole interface (docs/borehole-concept.md).

Builds the ISO, boots it headless in QEMU with a MortFS disk attached (the Limine
path provides a linear framebuffer), drives it with real key presses over the
QEMU monitor, and asserts on real framebuffer screendumps. Text is verified by
decoding pixels against the kernel's own font table, so a check passes only if
the exact glyphs are on screen.

    python test_gfx.py

Stdlib only: parses PPM screendumps directly.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)
import build  # noqa: E402
import test as T  # noqa: E402  (QEMU monitor helpers and limits)

# Design constants, from docs/borehole-concept.md and ui/borehole.mx.
BONE = 0xE8DCC4
BRIGHT = 0xF5EBD7
VERM = 0xFF4B1F
SHAFT = 0x0C0908
GALLERY = 0x14100C
INK = 0x2B1D12
WARN = 0xFF6B4A

SAND = {0x7A5228, 0x5E3D1B, 0x936A3A}
LIME = {0x6A5B4A, 0x4F4336, 0x7B6C5A}
SHALE = {0x4A2B20, 0x34201A, 0x5B3A2C}
GRANITE = {0x262020, 0x3D3535, 0x191515}

EDGES = [180, 327, 474, 621, 768]       # surface strata, top edges
CAPTIONS = [
    "the machine -- what it is made of",
    "objects on MortFS -- dig through the files",
    "run -- the shell, talk to the machine",
    "terminate -- lock, sleep, restart, halt",
]
LETTERS = "mort"

CON_X, CON_Y, CON_CW, CON_CH = 120, 136, 10, 20   # shell console cell grid
SETTLE = 1.6                                      # seconds for a reveal to finish

# Colours the shell may use for text (vga_rgb), to decode any cell.
CONSOLE_FG = [0xD8CBB2, 0xF5EBD7, 0xE0A14A, 0xC99B6B, 0xFF6B4A, 0xA88F6C, 0xB7773A, 0x8F6F4F]


def load_font():
    """Parse g_font out of kmain.mx: the real table the kernel draws with."""
    with open(os.path.join(HERE, "kmain.mx"), encoding="utf-8") as fh:
        src = fh.read()
    m = re.search(r"let g_font: \[u8; 4096\] = \[(.*?)\];", src, re.S)
    if not m:
        raise RuntimeError("g_font not found in kmain.mx")
    data = [int(x) for x in re.findall(r"\d+", m.group(1))]
    if len(data) != 4096:
        raise RuntimeError(f"g_font has {len(data)} bytes, expected 4096")
    return data


FONT = load_font()


def glyph_bits(ch):
    """The (x, y) positions of set pixels in glyph `ch`."""
    out = []
    for row in range(16):
        bits = FONT[ch * 16 + row]
        for col in range(8):
            if (bits >> (7 - col)) & 1:
                out.append((col, row))
    return out


GLYPHS = {c: glyph_bits(c) for c in range(32, 127)}


class Shot:
    """One framebuffer dump."""

    def __init__(self, path):
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
        self.w, self.h = fields[0], fields[1]
        self.px = data[idx + 1:]
        self.path = path

    def rgb(self, x, y):
        if not (0 <= x < self.w and 0 <= y < self.h):
            return -1                 # off-screen never matches a colour
        o = (y * self.w + x) * 3
        return (self.px[o] << 16) | (self.px[o + 1] << 8) | self.px[o + 2]

    def glyph_at(self, x, y, fgs):
        """Best glyph at pixel (x, y) whose set bits are all an accepted colour."""
        best, best_n = 32, 0
        for ch, bits in GLYPHS.items():
            if len(bits) <= best_n:
                continue
            if all(self.rgb(x + bx, y + by) in fgs for bx, by in bits):
                best, best_n = ch, len(bits)
        return chr(best)

    def text(self, x, y, n, fgs, step=8):
        """Decode `n` glyphs on a line, set bits must match a colour in fgs."""
        return "".join(self.glyph_at(x + i * step, y, fgs) for i in range(n))

    def find_text(self, x, y0, y1, needle, fgs, step=8):
        """Scan rows y0..y1 for `needle` at column x. Returns y or None."""
        for y in range(y0, y1):
            if self.text(x, y, len(needle), fgs, step) == needle:
                return y
        return None

    def cell(self, row, col):
        """Decode console cell strictly: every glyph pixel fg, the rest GALLERY."""
        px, py = CON_X + col * CON_CW + 1, CON_Y + row * CON_CH + 2
        for fg in CONSOLE_FG:
            for ch, bits in GLYPHS.items():
                on = set(bits)
                ok = True
                for yy in range(16):
                    for xx in range(8):
                        want = fg if (xx, yy) in on else GALLERY
                        if self.rgb(px + xx, py + yy) != want:
                            ok = False
                            break
                    if not ok:
                        break
                if ok:
                    return chr(ch)
        return "?"

    def console(self):
        """The whole console, 25 lines, strict pixel decode."""
        return ["".join(self.cell(r, c) for c in range(80)).rstrip() for r in range(25)]


class Vm:
    """The ISO booted in QEMU with a scratch copy of the MortFS disk."""

    def __init__(self):
        build.iso()
        build.ensure_disk()
        self.tmp = tempfile.mkdtemp(prefix="mortgfx-")
        self.disk = os.path.join(self.tmp, "disk.img")
        shutil.copy(build.DISK, self.disk)
        qemu = build._find_qemu()
        if not qemu:
            raise RuntimeError("qemu-system-i386 not found")
        self.proc = subprocess.Popen(
            [qemu, "-cdrom", build.ISO, "-hda", self.disk, "-boot", "d",
             "-display", "none", "-monitor", "stdio", *T.QEMU_LIMITS],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
        self.h = T.QemuHandle(self.proc)
        T._wait_first_prompt(self.h)
        self.n = 0

    def key(self, name, wait=0.12):
        T._monitor(self.h, f"sendkey {name} {T.KEY_HOLD_MS}")
        time.sleep(wait)

    def type(self, text):
        for ch in text:
            self.key(T.key_name(ch))

    def line(self, text):
        self.type(text)
        self.key("ret")

    def dump(self, path):
        T._monitor(self.h, f"screendump {path.replace(chr(92), '/')}", timeout_s=20)
        for _ in range(100):
            if os.path.exists(path) and os.path.getsize(path) > 1024 * 768 * 3:
                return
            time.sleep(0.05)
        raise RuntimeError(f"screendump never appeared: {path}")

    def shot(self, settle=SETTLE):
        time.sleep(settle)
        self.n += 1
        ppm = os.path.join(self.tmp, f"s{self.n}.ppm")
        self.dump(ppm)
        return Shot(ppm)

    def close(self):
        T.shutdown(self.h)


passed = 0
failed = 0


def check(label, ok):
    global passed, failed
    if ok:
        passed += 1
        print(f"PASS: {label}")
    else:
        failed += 1
        print(f"FAIL: {label}")


def area_in(s, x0, y0, w, h, allowed):
    """Every pixel of the rectangle is one of the allowed colours."""
    return all(s.rgb(x, y) in allowed for y in range(y0, y0 + h) for x in range(x0, x0 + w))


def colours(s, x0, y0, w, h):
    return {s.rgb(x, y) for y in range(y0, y0 + h) for x in range(x0, x0 + w)}


def phase_surface(vm):
    s = vm.shot(6.0)
    check("framebuffer is 1024x768", (s.w, s.h) == (1024, 768))
    for name, top, pal in (("sandstone M", EDGES[0], SAND), ("limestone O", EDGES[1], LIME),
                           ("shale R", EDGES[2], SHALE), ("granite T", EDGES[3], GRANITE)):
        check(f"surface: {name} stratum shows its lithology",
              area_in(s, 700, top + 112, 120, 16, pal)
              and len(colours(s, 700, top + 112, 120, 16)) >= 2)
    check("surface: drill shaft runs through all strata",
          all(s.rgb(54, y) == SHAFT for y in range(EDGES[0] + 16, 740)
              if not 515 <= y <= 580))     # the drill bit sits in the shaft on R
    for i, cap in enumerate(CAPTIONS):
        check(f"surface: caption {i} is legible",
              s.text(152, EDGES[i] + 100, len(cap), {BONE}) == cap)
    check("surface: R stratum selected at boot",
          all(s.rgb(x, EDGES[2] + 3) == VERM for x in range(300, 340))
          and s.rgb(92, EDGES[2] + 32) == VERM)
    check("surface: other strata not selected", s.rgb(300, EDGES[1] + 3) != VERM)
    vm.key("up")
    s = vm.shot()
    check("surface: Up moves selection to O",
          s.rgb(300, EDGES[1] + 3) == VERM and s.rgb(300, EDGES[2] + 3) != VERM)
    vm.key("down")
    vm.shot()


def phase_shell(vm):
    vm.key("ret")
    s = vm.shot()
    check("shell: gallery opened",
          all(s.rgb(x, y) == GALLERY for x, y in ((930, 300), (110, 300), (500, 680))))
    con = s.console()
    check("shell: boot messages and prompt rendered",
          any("MORT OS" in ln for ln in con) and any("$" in ln for ln in con))
    vm.line("echo borehole-ok")
    s = vm.shot()
    con = s.console()
    check("shell: echo prints exactly what was typed",
          any(ln == "borehole-ok" for ln in con))
    vm.line("ls /bin")
    s = vm.shot()
    con = s.console()
    check("shell: ls lists /bin programs from MortFS",
          any("hello.bin" in ln for ln in con))
    check("shell: text output survives in the console", any(ln == "borehole-ok" for ln in con))
    vm.key("esc")
    s = vm.shot()
    check("shell: Esc returns to the surface",
          s.rgb(930, 300) != GALLERY and s.rgb(300, EDGES[2] + 3) == VERM)
    vm.key("r")
    s = vm.shot()
    con = s.console()
    check("shell: R returns with scrollback intact", any(ln == "borehole-ok" for ln in con))
    vm.key("esc")
    vm.shot()


def phase_objects(vm):
    vm.key("o")
    s = vm.shot()
    names = (BONE, BRIGHT)
    check("objects: root stratum labelled", s.find_text(100, 56, 90, "/", set(names)) is not None)
    y = None
    for name in ("hello.txt", "bin", "home"):
        y = s.find_text(150, 90, 760, name, set(names))
        check(f"objects: root lists {name}", y is not None)
    check("objects: shell gallery is gone", s.rgb(930, 300) != GALLERY)
    # Move to the hello.txt bed: dirs come first, then files; press Down until selected.
    sel = None
    for _ in range(24):
        y = s.find_text(150, 90, 760, "hello.txt", {BRIGHT})
        if y is not None:
            sel = y
            break
        vm.key("down")
        s = vm.shot(0.8)
    check("objects: Down selects a file bed", sel is not None)
    vm.key("ret")
    s = vm.shot()
    want = "this file lives on the MortFS disk"
    y = s.find_text(190, 100, 200, want, {INK}, step=10)
    check("core: Enter shows the exact file contents", y is not None)
    check("core: slab is bone coloured", s.rgb(500, 700) != GALLERY)
    vm.key("esc")
    s = vm.shot()
    check("core: Esc returns to the objects list",
          s.find_text(150, 90, 760, "hello.txt", {BONE, BRIGHT}) is not None)
    # Descend into /bin and come back.
    for _ in range(24):
        if s.find_text(150, 90, 760, "bin", {BRIGHT}) is not None:
            break
        vm.key("up")
        s = vm.shot(0.8)
    vm.key("ret")
    s = vm.shot()
    check("objects: Enter descends into /bin",
          s.find_text(100, 56, 120, "bin", {BONE, BRIGHT}) is not None
          and s.find_text(150, 110, 760, "hello.bin", {BONE, BRIGHT}) is not None)
    vm.key("esc")
    s = vm.shot()
    check("objects: Esc climbs back to the root",
          s.find_text(150, 90, 760, "hello.txt", {BONE, BRIGHT}) is not None)
    vm.key("esc")
    s = vm.shot()
    check("objects: Esc at the root returns to the surface",
          s.rgb(300, EDGES[1] + 3) == VERM)


def phase_machine(vm):
    vm.key("m")
    s = vm.shot()
    want = "machine"
    check("machine: stratum open", s.find_text(100, 56, 90, want, {BONE, BRIGHT}) is not None)
    ram = None
    for y in range(90, 400):
        t = s.text(150, y, 30, {BONE, BRIGHT})
        if t.startswith("RAM"):
            ram = t
            break
    check("machine: RAM reading is the real guest size",
          ram is not None and re.search(r"RAM\D+25\d MiB", ram) is not None)
    check("machine: DHCP action listed",
          s.find_text(150, 300, 760, "Connect with DHCP", {BONE, BRIGHT}) is not None)
    vm.key("esc")
    vm.shot()


def phase_terminate(vm):
    vm.key("t")
    s = vm.shot()
    for item in ("Lock", "Sleep", "Restart", "Shut down"):
        check(f"terminate: {item} listed",
              s.find_text(150, 56, 760, item, {BONE, BRIGHT}) is not None)
    check("terminate: Lock selected first", s.find_text(150, 56, 760, "Lock", {BRIGHT}) is not None)
    vm.key("ret")
    s = vm.shot()
    check("lock: password prompt shown",
          s.find_text(300, 300, 500, "password", {BONE, BRIGHT}) is not None)
    vm.line("wrongpw")
    s = vm.shot()
    check("lock: wrong password refused",
          s.find_text(300, 300, 500, "wrong password", {WARN}) is not None)
    vm.line("mort")
    s = vm.shot()
    check("lock: correct password unlocks", s.find_text(300, 300, 500, "password", {BONE}) is None)
    vm.key("down")
    s = vm.shot(0.8)
    check("terminate: Down selects Sleep", s.find_text(150, 56, 760, "Sleep", {BRIGHT}) is not None)
    vm.key("ret")
    s = vm.shot()
    sleeping = all(s.rgb(x, 700) not in SAND | LIME | SHALE | GRANITE for x in range(100, 900, 37))
    check("sleep: screen goes dark", sleeping)
    vm.key("spc")
    s = vm.shot()
    check("sleep: any key wakes", s.find_text(150, 56, 760, "Sleep", {BONE, BRIGHT}) is not None)
    vm.key("esc")
    s = vm.shot()
    check("terminate: Esc returns to the surface", s.rgb(300, EDGES[3] + 3) == VERM)


def main():
    vm = Vm()
    try:
        for phase in (phase_surface, phase_shell, phase_objects, phase_machine, phase_terminate):
            try:
                phase(vm)
            except Exception as e:  # report and continue: each phase is independent
                check(f"{phase.__name__} crashed: {e!r}", False)
    finally:
        vm.close()
    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
