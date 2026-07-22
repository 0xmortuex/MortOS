#!/usr/bin/env python3
"""Automated test harness for MORT OS.

Boots the kernel headless in QEMU, types commands over the QEMU human
monitor (`sendkey`), reads the VGA text screen back out of guest memory
(`memsave 0xb8000`), and asserts on what the shell drew.

    python kernel/test.py smoke                 # build + boot + run the smoke tests
    python kernel/test.py smoke --disk foo.img  # same, with a disk attached as -hda

Python stdlib only. Works on Windows (pipes to `-monitor stdio` are drained
by a background thread; nothing here assumes a tty or select()).

API for other tests:

    handle = boot(disk_img=None)         # launch QEMU, wait for the monitor
    type_line(handle, "echo hi")         # sendkey each char, then Enter
    text = screen_text(handle)           # the 80x25 VGA screen as 25 lines
    ok = wait_for(handle, "hi", 10)      # poll the screen for a substring
    shutdown(handle)                     # monitor `quit` + kill, always safe
"""
import argparse
import os
import shutil
import subprocess
import struct
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "build")
ELF = os.path.join(HERE, "build", "kernel.elf")

MONITOR_PROMPT = b"(qemu)"

# How long QEMU holds each injected key down (ms), and how long we pause after
# each key. The pause MUST exceed the hold time: `sendkey shift-a` releases
# shift only after the hold time, so a faster next key would land shifted.
KEY_HOLD_MS = 40
KEY_GAP_S = 0.07

# ----- char -> QEMU sendkey name -----

_SYMS = {
    " ": "spc", "-": "minus", "=": "equal", ".": "dot", ",": "comma",
    "/": "slash", ";": "semicolon", "'": "apostrophe", "[": "bracket_left",
    "]": "bracket_right", "\\": "backslash", "`": "grave_accent",
}
_SHIFT_SYMS = {
    "!": "1", "@": "2", "#": "3", "$": "4", "%": "5", "^": "6", "&": "7",
    "*": "8", "(": "9", ")": "0", "_": "minus", "+": "equal", "<": "comma",
    ">": "dot", "?": "slash", ":": "semicolon", '"': "apostrophe",
    "{": "bracket_left", "}": "bracket_right", "|": "backslash",
    "~": "grave_accent",
}


def key_name(ch):
    """QEMU sendkey name for a single character (raises on unmappable)."""
    if "a" <= ch <= "z" or "0" <= ch <= "9":
        return ch
    if "A" <= ch <= "Z":
        return "shift-" + ch.lower()
    if ch in _SYMS:
        return _SYMS[ch]
    if ch in _SHIFT_SYMS:
        return "shift-" + _SHIFT_SYMS[ch]
    raise ValueError(f"no sendkey mapping for character {ch!r}")


# ----- QEMU process handle -----

class QemuHandle:
    def __init__(self, proc):
        self.proc = proc
        self.out = bytearray()          # everything QEMU wrote to stdout
        self.err = bytearray()          # everything QEMU wrote to stderr
        self.lock = threading.Lock()
        self._dump = os.path.join(
            tempfile.gettempdir(), f"mort_vga_{proc.pid}.bin")
        self._readers = [
            threading.Thread(target=self._drain, args=(proc.stdout, self.out),
                             daemon=True),
            threading.Thread(target=self._drain, args=(proc.stderr, self.err),
                             daemon=True),
        ]
        for t in self._readers:
            t.start()

    def _drain(self, pipe, buf):
        # Raw (bufsize=0) pipe: read() returns as soon as any bytes arrive.
        # A dedicated thread per pipe is the only portable way to avoid
        # blocking on Windows, where select() doesn't work on pipes.
        while True:
            try:
                chunk = pipe.read(4096)
            except (OSError, ValueError):
                break
            if not chunk:
                break
            with self.lock:
                buf.extend(chunk)

    def alive(self):
        return self.proc.poll() is None

    def out_len(self):
        with self.lock:
            return len(self.out)

    def out_since(self, mark):
        with self.lock:
            return bytes(self.out[mark:])

    def tail(self, n=800):
        with self.lock:
            return (bytes(self.out[-n:]).decode("ascii", "replace")
                    + " | stderr: "
                    + bytes(self.err[-n:]).decode("ascii", "replace"))


def _monitor(handle, cmd, timeout_s=10):
    """Send one human-monitor command; return its output (text between the
    echoed command and the next '(qemu)' prompt)."""
    if not handle.alive():
        raise RuntimeError(f"QEMU exited (rc={handle.proc.returncode}); "
                           f"last output: {handle.tail()}")
    mark = handle.out_len()
    handle.proc.stdin.write(cmd.encode("ascii") + b"\n")
    handle.proc.stdin.flush()
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        data = handle.out_since(mark)
        if MONITOR_PROMPT in data:
            text = data.split(MONITOR_PROMPT, 1)[0]
            return text.decode("ascii", "replace")
        if not handle.alive():
            raise RuntimeError(
                f"QEMU died during {cmd!r} (rc={handle.proc.returncode}); "
                f"output: {handle.tail()}")
        time.sleep(0.01)
    raise TimeoutError(
        f"no monitor prompt within {timeout_s}s after {cmd!r}; "
        f"output tail: {handle.tail()}")


def _wait_first_prompt(handle, timeout_s=15):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if MONITOR_PROMPT in handle.out_since(0):
            return
        if not handle.alive():
            raise RuntimeError(
                f"QEMU exited at startup (rc={handle.proc.returncode}); "
                f"output: {handle.tail()}")
        time.sleep(0.02)
    raise TimeoutError(f"QEMU monitor never prompted; output: {handle.tail()}")


# ----- public API -----

def boot(disk_img=None, kernel_elf=ELF, extra_args=None):
    """Boot the kernel headless; return a handle once the monitor is ready."""
    qemu = _find_qemu()
    if not qemu:
        raise RuntimeError("qemu-system-i386 not found — install QEMU "
                           "(winget install SoftwareFreedomConservancy.QEMU)")
    if not os.path.exists(kernel_elf):
        raise RuntimeError(f"kernel not built: {kernel_elf}")
    cmd = [qemu, "-display", "none", "-monitor", "stdio",
           "-kernel", kernel_elf]
    if disk_img:
        cmd += ["-hda", disk_img]
    if extra_args:
        cmd += list(extra_args)
    proc = subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, bufsize=0)          # raw, unbuffered pipes
    handle = QemuHandle(proc)
    try:
        _wait_first_prompt(handle)
    except Exception:
        shutdown(handle)
        raise
    return handle


def boot_iso(iso_path, disk_img=None, extra_args=None):
    """Boot a graphical ISO image headlessly with a QEMU monitor."""
    qemu = _find_qemu()
    if not qemu:
        raise RuntimeError("qemu-system-i386 not found")
    cmd = [qemu, "-display", "none", "-monitor", "stdio",
           "-cdrom", iso_path, "-boot", "d"]
    if disk_img:
        cmd += ["-hda", disk_img]
    if extra_args:
        cmd += list(extra_args)
    proc = subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, bufsize=0)
    handle = QemuHandle(proc)
    try:
        _wait_first_prompt(handle)
    except Exception:
        shutdown(handle)
        raise
    return handle


def send_key(handle, name, hold_ms=KEY_HOLD_MS):
    _monitor(handle, f"sendkey {name} {hold_ms}")
    time.sleep(KEY_GAP_S)


def type_line(handle, text):
    """Type `text` on the guest's PS/2 keyboard, then press Enter."""
    for ch in text:
        _monitor(handle, f"sendkey {key_name(ch)} {KEY_HOLD_MS}")
        time.sleep(KEY_GAP_S)
    _monitor(handle, f"sendkey ret {KEY_HOLD_MS}")
    time.sleep(KEY_GAP_S)


def screen_text(handle):
    """The current 80x25 VGA text screen, as 25 newline-joined lines."""
    raw = _dump_vga_memsave(handle)
    if raw is None:
        raw = _dump_vga_xp(handle)
    chars = raw[0::2]                     # cells are (char, attr) byte pairs
    rows = []
    for r in range(25):
        row = chars[r * 80:(r + 1) * 80]
        rows.append("".join(chr(b) if 32 <= b < 127 else " " for b in row))
    return "\n".join(rows)


def wait_for(handle, substring, timeout_s=10):
    """Poll the screen until `substring` appears. Returns True/False."""
    deadline = time.monotonic() + timeout_s
    while True:
        if substring in screen_text(handle):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.25)


def shutdown(handle):
    """Quit QEMU via the monitor; kill it if it lingers. Never raises."""
    try:
        if handle.alive():
            try:  # `quit` never prompts again, so don't wait for one
                handle.proc.stdin.write(b"quit\n")
                handle.proc.stdin.flush()
            except OSError:
                pass
            try:
                handle.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                handle.proc.kill()
                handle.proc.wait(timeout=5)
    except Exception:
        try:
            handle.proc.kill()
        except Exception:
            pass
    finally:
        for pipe in (handle.proc.stdin, handle.proc.stdout, handle.proc.stderr):
            try:
                pipe.close()
            except Exception:
                pass
        try:
            os.remove(handle._dump)
        except OSError:
            pass


# ----- VGA dumping (memsave primary, xp fallback) -----

def _dump_vga_memsave(handle):
    """Dump 0xB8000..0xB8FA0 to a host file via `memsave`; None on failure."""
    path = handle._dump
    if " " in path:
        return None       # monitor filename args don't survive spaces
    try:
        os.remove(path)
    except OSError:
        pass
    # Forward slashes: fine for Windows, and nothing for the monitor to eat.
    out = _monitor(handle, f"memsave 0xb8000 4000 {path.replace(os.sep, '/')}")
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        return None
    if len(data) != 4000:
        return None
    if "could not" in out.lower() or "error" in out.lower():
        return None
    return data


def _dump_vga_xp(handle):
    """Fallback: parse `xp /2000wx 0xb8000` (hex words) into 4000 raw bytes."""
    out = _monitor(handle, "xp /2000wx 0xb8000", timeout_s=20)
    raw = bytearray()
    for line in out.splitlines():
        if ":" not in line:
            continue
        _, _, rest = line.partition(":")
        for tok in rest.split():
            if not tok.startswith("0x"):
                continue
            word = int(tok, 16)
            raw += bytes((word & 0xFF, (word >> 8) & 0xFF,
                          (word >> 16) & 0xFF, (word >> 24) & 0xFF))
    if len(raw) < 4000:
        raise RuntimeError(
            f"xp fallback parsed only {len(raw)} bytes of VGA memory")
    return bytes(raw[:4000])


def _find_qemu():
    sys.path.insert(0, HERE)
    import build as kernel_build
    return kernel_build._find_qemu()


def _elf32_symbol(path, wanted):
    """Return the address of a local/global symbol in a little-endian ELF32."""
    with open(path, "rb") as fh:
        data = fh.read()
    if data[:5] != b"\x7fELF\x01" or data[5] != 1:
        raise RuntimeError(f"expected little-endian ELF32: {path}")
    shoff = struct.unpack_from("<I", data, 32)[0]
    shentsize, shnum = struct.unpack_from("<HH", data, 46)
    sections = []
    for index in range(shnum):
        fields = struct.unpack_from("<IIIIIIIIII", data,
                                    shoff + index * shentsize)
        sections.append(fields)
    for section in sections:
        _name, kind, _flags, _addr, offset, size, link, _info, _align, entsize = section
        if kind != 2 or entsize == 0:  # SHT_SYMTAB
            continue
        strings = sections[link]
        strtab = data[strings[4]:strings[4] + strings[5]]
        for pos in range(offset, offset + size, entsize):
            name_off, value = struct.unpack_from("<II", data, pos)
            end = strtab.find(b"\0", name_off)
            name = strtab[name_off:end].decode("ascii", "replace")
            if name == wanted:
                return value
    raise RuntimeError(f"symbol not found in {path}: {wanted}")


def _guest_u32(handle, address):
    text = _monitor(handle, f"xp /1wx 0x{address:x}")
    values = []
    for token in text.replace(":", " ").split():
        if token.startswith("0x"):
            try:
                values.append(int(token, 16))
            except ValueError:
                pass
    if not values:
        raise RuntimeError(f"could not parse monitor memory output: {text!r}")
    return values[-1]


def _wait_guest_u32(handle, address, predicate, timeout_s=10):
    deadline = time.monotonic() + timeout_s
    value = _guest_u32(handle, address)
    while not predicate(value) and time.monotonic() < deadline:
        time.sleep(0.25)
        value = _guest_u32(handle, address)
    return value


def _guest_bytes(handle, address, length):
    text = _monitor(handle, f"xp /{length}bx 0x{address:x}", timeout_s=20)
    values = []
    for token in text.replace(":", " ").split():
        if token.startswith("0x"):
            try:
                value = int(token.rstrip(","), 16)
                if value <= 0xff:
                    values.append(value)
            except ValueError:
                pass
    if len(values) < length:
        raise RuntimeError(f"expected {length} guest bytes, got {len(values)}: {text!r}")
    return bytes(values[:length])


# ----- smoke test -----

def smoke(disk_img=None):
    # Build first (build.py locates the Mort compiler via its parent dir).
    sys.path.insert(0, HERE)
    import build as kernel_build
    kernel_build.build()
    sha256_ok_addr = _elf32_symbol(ELF, "m_g_tls_crypto_sha256_ok")
    hmac_ok_addr = _elf32_symbol(ELF, "m_g_tls_crypto_hmac_ok")
    hkdf_ok_addr = _elf32_symbol(ELF, "m_g_tls_crypto_hkdf_ok")
    chacha_ok_addr = _elf32_symbol(ELF, "m_g_tls_crypto_chacha_ok")
    poly1305_ok_addr = _elf32_symbol(ELF, "m_g_tls_crypto_poly1305_ok")
    aead_ok_addr = _elf32_symbol(ELF, "m_g_tls_crypto_aead_ok")
    ticks_addr = _elf32_symbol(ELF, "m_g_ticks")

    results = []

    def check(name, ok, handle=None):
        results.append((name, ok))
        print(f"{'PASS' if ok else 'FAIL'}: {name}")
        if not ok and handle is not None:
            print("--- screen at failure ---")
            print(screen_text(handle))
            print("-------------------------")

    handle = boot(disk_img=disk_img)
    try:
        check("boot banner shows 'MORT OS'",
              wait_for(handle, "MORT OS", timeout_s=15), handle)
        _wait_guest_u32(handle, ticks_addr, lambda value: value >= 1, timeout_s=20)

        check("Mort SHA-256 passes empty and abc standard vectors",
              (_guest_u32(handle, sha256_ok_addr) & 0xff) != 0, handle)
        check("Mort HMAC-SHA256 passes RFC 4231 case 1",
              (_guest_u32(handle, hmac_ok_addr) & 0xff) != 0, handle)
        check("Mort HKDF-SHA256 passes RFC 5869 case 1",
              (_guest_u32(handle, hkdf_ok_addr) & 0xff) != 0, handle)
        check("Mort ChaCha20 passes the RFC 8439 block vector",
              (_guest_u32(handle, chacha_ok_addr) & 0xff) != 0, handle)
        check("Mort Poly1305 passes the RFC 8439 authenticator vector",
              (_guest_u32(handle, poly1305_ok_addr) & 0xff) != 0, handle)
        check("Mort ChaCha20-Poly1305 passes the RFC 8439 AEAD vector",
              (_guest_u32(handle, aead_ok_addr) & 0xff) != 0, handle)

        type_line(handle, "help")
        check("'help' lists the commands",
              wait_for(handle, "clear about echo", timeout_s=10), handle)

        type_line(handle, "echo hi-there")
        check("'echo hi-there' echoes back",
              wait_for(handle, "hi-there", timeout_s=10), handle)

        type_line(handle, "uptime")
        check("'uptime' reports uptime",
              wait_for(handle, "uptime:", timeout_s=10), handle)
    finally:
        shutdown(handle)

    failed = [name for name, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    return 0 if not failed else 1


def usb_hotplug():
    """Exercise automatic UHCI detach and reattach recovery in QEMU."""
    sys.path.insert(0, HERE)
    import build as kernel_build
    kernel_build.build()
    devices_addr = _elf32_symbol(ELF, "m_g_usb_devices")
    events_addr = _elf32_symbol(ELF, "m_g_usb_hotplug_events")
    rescanning_addr = _elf32_symbol(ELF, "m_g_usb_rescanning")
    keyboard_addr = _elf32_symbol(ELF, "m_g_usb_keyboard_ready")
    mouse_addr = _elf32_symbol(ELF, "m_g_usb_mouse_ready")
    handle = boot(extra_args=["-usb", "-device", "usb-kbd,id=mortkbd"])
    results = []

    def check(name, ok):
        results.append((name, ok))
        print(f"{'PASS' if ok else 'FAIL'}: {name}")

    try:
        devices = _wait_guest_u32(handle, devices_addr, lambda value: value >= 1)
        check("USB keyboard enumerates at boot", devices >= 1)
        check("USB keyboard HID binding is ready",
              (_guest_u32(handle, keyboard_addr) & 0xff) != 0)

        _monitor(handle, "device_del mortkbd")
        devices = _wait_guest_u32(handle, devices_addr, lambda value: value == 0,
                                  timeout_s=12)
        events = _guest_u32(handle, events_addr)
        check("USB detach automatically rebuilds the device table", devices == 0)
        check("USB detach increments the hot-plug event counter", events >= 1)
        _wait_guest_u32(handle, rescanning_addr,
                        lambda value: (value & 0xff) == 0, timeout_s=12)

        _monitor(handle, "device_add usb-kbd,id=mortkbd")
        devices = _wait_guest_u32(handle, devices_addr, lambda value: value >= 1,
                                  timeout_s=12)
        events = _guest_u32(handle, events_addr)
        keyboard = _guest_u32(handle, keyboard_addr) & 0xff
        check("USB reattach automatically enumerates the device", devices >= 1)
        check("USB reattach restores the HID keyboard binding", keyboard != 0)
        check("USB reattach records a second hot-plug event", events >= 2)
    finally:
        shutdown(handle)

    handle = boot(extra_args=["-usb", "-device", "usb-kbd,id=hubkbd",
                              "-device", "usb-mouse,id=hubmouse"])
    try:
        devices = _wait_guest_u32(handle, devices_addr, lambda value: value >= 3)
        check("hub topology enumerates keyboard, hub, and mouse", devices >= 3)
        check("downstream mouse HID binding is ready",
              (_guest_u32(handle, mouse_addr) & 0xff) != 0)

        _monitor(handle, "device_del hubmouse")
        devices = _wait_guest_u32(handle, devices_addr, lambda value: value == 2,
                                  timeout_s=12)
        check("hub-port detach removes the downstream mouse", devices == 2)
        _wait_guest_u32(handle, rescanning_addr,
                        lambda value: (value & 0xff) == 0, timeout_s=12)

        _monitor(handle, "device_add usb-mouse,id=hubmouse")
        devices = _wait_guest_u32(handle, devices_addr, lambda value: value >= 3,
                                  timeout_s=12)
        mouse = _guest_u32(handle, mouse_addr) & 0xff
        events = _guest_u32(handle, events_addr)
        check("hub-port reattach re-enumerates the mouse", devices >= 3)
        check("hub-port reattach restores the mouse binding", mouse != 0)
        check(f"hub detach and reattach record two events (observed {events})",
              events >= 2)
    finally:
        shutdown(handle)

    failed = [name for name, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    return 0 if not failed else 1


def settings_ui():
    """Verify graphical Settings navigation and MortFS preference persistence."""
    sys.path.insert(0, HERE)
    import build as kernel_build
    kernel_build.iso()
    kernel_build.ensure_disk()
    ticks_addr = _elf32_symbol(ELF, "m_g_ticks")
    app_addr = _elf32_symbol(ELF, "m_g_app")
    view_addr = _elf32_symbol(ELF, "m_g_settings_view")
    accent_addr = _elf32_symbol(ELF, "m_g_settings_accent")
    persisted_addr = _elf32_symbol(ELF, "m_g_settings_persisted")
    temp_disk = os.path.join(tempfile.gettempdir(),
                             f"mort_settings_{os.getpid()}.img")
    shutil.copyfile(kernel_build.DISK, temp_disk)
    results = []

    def check(name, ok):
        results.append((name, ok))
        print(f"{'PASS' if ok else 'FAIL'}: {name}")

    changed_accent = 0
    handle = boot_iso(kernel_build.ISO, temp_disk)
    try:
        _wait_guest_u32(handle, ticks_addr, lambda value: value >= 100,
                        timeout_s=20)
        send_key(handle, "esc")       # close the boot launcher
        send_key(handle, "f4")
        app = _wait_guest_u32(handle, app_addr, lambda value: value == 3)
        check("F4 opens Settings from the graphical desktop", app == 3)
        persisted = _wait_guest_u32(
            handle, persisted_addr, lambda value: (value & 0xff) != 0)
        check("Settings creates a per-user MortFS preference record",
              (persisted & 0xff) != 0)

        send_key(handle, "down")      # Overview -> Personalization
        send_key(handle, "ret")
        view = _wait_guest_u32(handle, view_addr, lambda value: value == 1)
        check("Enter opens the Personalization control page", view == 1)
        before = _guest_u32(handle, accent_addr)
        send_key(handle, "ret")       # cycle accent
        changed_accent = _wait_guest_u32(
            handle, accent_addr, lambda value: value != before)
        check("Accent control changes live kernel state", changed_accent != before)

        send_key(handle, "esc")
        send_key(handle, "slash")
        for key in ("c", "l", "o", "c", "k"):
            send_key(handle, key)
        send_key(handle, "ret")
        view = _wait_guest_u32(handle, view_addr, lambda value: value == 2)
        check("Settings search opens the matching Clock control page", view == 2)
        shot = os.path.join(BUILD, "settings-complete.ppm").replace(os.sep, "/")
        _monitor(handle, f"screendump {shot}")
        check("Settings UI screenshot was captured",
              os.path.exists(os.path.join(BUILD, "settings-complete.ppm")))
    finally:
        shutdown(handle)

    handle = boot_iso(kernel_build.ISO, temp_disk)
    try:
        _wait_guest_u32(handle, ticks_addr, lambda value: value >= 100,
                        timeout_s=20)
        send_key(handle, "esc")
        send_key(handle, "f4")
        loaded_accent = _wait_guest_u32(
            handle, accent_addr, lambda value: value == changed_accent,
            timeout_s=10)
        check("Accent preference survives a full reboot", loaded_accent == changed_accent)
    finally:
        shutdown(handle)
        try:
            os.remove(temp_disk)
        except OSError:
            pass

    failed = [name for name, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    return 0 if not failed else 1


def browser_ui():
    """Load a host-served HTTP page and verify browser state and persistence."""
    from functools import partial
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    sys.path.insert(0, HERE)
    import build as kernel_build
    kernel_build.iso()
    kernel_build.ensure_disk()
    ticks_addr = _elf32_symbol(ELF, "m_g_ticks")
    app_addr = _elf32_symbol(ELF, "m_g_app")
    remote_addr = _elf32_symbol(ELF, "m_g_browser_remote")
    gateway_addr = _elf32_symbol(ELF, "m_g_gateway_ip")
    dns_addr = _elf32_symbol(ELF, "m_g_dns_ip")
    content_addr = _elf32_symbol(ELF, "m_g_browser_content")
    content_len_addr = _elf32_symbol(ELF, "m_g_browser_content_len")
    status_addr = _elf32_symbol(ELF, "m_g_browser_status")
    downloaded_addr = _elf32_symbol(ELF, "m_g_browser_downloaded")
    links_addr = _elf32_symbol(ELF, "m_g_browser_link_count")
    tabs_addr = _elf32_symbol(ELF, "m_g_browser_tab_count")
    mouse_ready_addr = _elf32_symbol(ELF, "m_g_usb_mouse_ready")
    mouse_x_addr = _elf32_symbol(ELF, "m_g_mouse_x")
    mouse_y_addr = _elf32_symbol(ELF, "m_g_mouse_y")
    private_addr = _elf32_symbol(ELF, "m_g_browser_private")
    suggestions_addr = _elf32_symbol(ELF, "m_g_browser_suggestion_count")
    state_addr = _elf32_symbol(ELF, "m_g_browser_state")
    temp_disk = os.path.join(tempfile.gettempdir(),
                             f"mort_browser_{os.getpid()}.img")
    shutil.copyfile(kernel_build.DISK, temp_disk)
    results = []

    def check(name, ok):
        results.append((name, ok))
        print(f"{'PASS' if ok else 'FAIL'}: {name}")

    with tempfile.TemporaryDirectory(prefix="mort_web_") as webroot:
        marker = "MORT-VEX-HTTP-OK"
        second_marker = "MORT-VEX-LINK-OK"
        redirect_marker = "MORT-VEX-REDIRECT-OK"
        chunked_marker = "MORT-VEX-CHUNKED-OK"
        plain_marker = "MORT-VEX-PLAIN-OK"
        with open(os.path.join(webroot, "index.html"), "w", encoding="ascii") as fh:
            fh.write("<!doctype html><html><head><title>Vex Network Test</title>"
                     "<style>hidden-style{color:red}</style></head><body>"
                     f"<h1>{marker}</h1><p>Rendered safely from HTTP.</p>"
                     "<a href=\"/second.html\">Open second page</a>"
                     "<script>hidden-script()</script></body></html>")
        with open(os.path.join(webroot, "second.html"), "w", encoding="ascii") as fh:
            fh.write(f"<!doctype html><title>Second Vex Page</title><h1>{second_marker}</h1>")
        os.mkdir(os.path.join(webroot, "redirected"))
        with open(os.path.join(webroot, "redirected", "index.html"), "w", encoding="ascii") as fh:
            fh.write(f"<!doctype html><title>Redirected</title><h1>{redirect_marker}</h1>")

        class VexHandler(SimpleHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self):
                if self.path == "/chunked":
                    chunks = [b"<!doctype html><title>Chunked</title><h1>",
                              chunked_marker.encode("ascii"), b"</h1>"]
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                    self.send_header("Transfer-Encoding", "chunked")
                    self.end_headers()
                    for chunk in chunks:
                        self.wfile.write(f"{len(chunk):x}\r\n".encode("ascii"))
                        self.wfile.write(chunk + b"\r\n")
                    self.wfile.write(b"0\r\n\r\n")
                    self.wfile.flush()
                    return
                if self.path == "/plain":
                    body = f"{plain_marker} <literal-text>\nsecond line\n".encode("ascii")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain; charset=ascii")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                if self.path == "/binary":
                    body = b"\x00\x01\x02MORT-BINARY"
                    self.send_response(200)
                    self.send_header("Content-Type", "application/octet-stream")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                super().do_GET()

            def log_message(self, _format, *args):
                pass

        port = 18080
        server = ThreadingHTTPServer(
            ("127.0.0.1", port), partial(VexHandler, directory=webroot))
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        handle = boot_iso(
            kernel_build.ISO, temp_disk,
            ["-netdev", "user,id=vexnet", "-device", "rtl8139,netdev=vexnet",
             "-usb", "-device", "usb-mouse,id=vexmouse"])
        try:
            _wait_guest_u32(handle, ticks_addr, lambda value: value >= 100,
                            timeout_s=20)
            send_key(handle, "esc")
            send_key(handle, "f3")
            app = _wait_guest_u32(handle, app_addr, lambda value: value == 2)
            check("F3 opens the native Vex browser", app == 2)

            _wait_guest_u32(handle, mouse_ready_addr,
                            lambda value: (value & 0xff) != 0)
            for dx, dy in ((127, -127), (127, -57), (30, 0)):
                _monitor(handle, f"mouse_move {dx} {dy}")
                time.sleep(0.15)
            _wait_guest_u32(handle, mouse_x_addr, lambda value: value >= 780)
            _wait_guest_u32(handle, mouse_y_addr, lambda value: 188 <= value < 214)
            _monitor(handle, "mouse_button 1")
            time.sleep(0.2)
            _monitor(handle, "mouse_button 0")
            tabs = _wait_guest_u32(handle, tabs_addr, lambda value: value == 2)
            check("Mouse click opens a Vex tab from the toolbar", tabs == 2)
            send_key(handle, "x")
            _wait_guest_u32(handle, tabs_addr, lambda value: value == 1)

            send_key(handle, "slash")
            address = f"http://10.0.2.2:{port}/"
            for char in address:
                send_key(handle, key_name(char))
            send_key(handle, "ret")
            remote = _wait_guest_u32(
                handle, remote_addr, lambda value: (value & 0xff) != 0,
                timeout_s=25)
            check("Vex completes DHCP, ARP, TCP, and HTTP loading",
                  (remote & 0xff) != 0)
            check("DHCP lease records the router-provided default gateway",
                  _guest_bytes(handle, gateway_addr, 4) == bytes((10, 0, 2, 2)))
            check("DHCP lease records the router-provided DNS server",
                  _guest_bytes(handle, dns_addr, 4) == bytes((10, 0, 2, 3)))
            content_len = _guest_u32(handle, content_len_addr)
            content = _guest_bytes(handle, content_addr, min(content_len, 512))
            text_content = content.decode("ascii", "replace")
            check("HTTP HTML is converted into rendered text", marker in text_content)
            check("script and style bodies are removed",
                  "hidden-script" not in text_content and "hidden-style" not in text_content)
            links = _wait_guest_u32(handle, links_addr, lambda value: value >= 1)
            check("HTTP anchor is extracted as a navigable link", links >= 1)

            remembered = _guest_bytes(handle, state_addr + 816, 80).split(b"\0", 1)[0].decode("ascii", "replace")
            check("Last non-private HTTP page is stored for explicit recovery",
                  remembered == address)
            send_key(handle, "1")
            _wait_guest_u32(handle, remote_addr, lambda value: (value & 0xff) == 0)
            send_key(handle, "9")
            restored = _wait_guest_u32(
                handle, remote_addr, lambda value: (value & 0xff) != 0,
                timeout_s=25)
            restored_len = _guest_u32(handle, content_len_addr)
            restored_text = _guest_bytes(
                handle, content_addr, min(restored_len, 512)).decode("ascii", "replace")
            check("Home page restores the last normal session only on request",
                  (restored & 0xff) != 0 and marker in restored_text)

            send_key(handle, "l")
            send_key(handle, "ret")
            deadline = time.monotonic() + 25
            linked_text = ""
            while time.monotonic() < deadline and second_marker not in linked_text:
                length = _guest_u32(handle, content_len_addr)
                linked_text = _guest_bytes(
                    handle, content_addr, min(max(length, 1), 512)).decode("ascii", "replace")
                if second_marker not in linked_text:
                    time.sleep(0.25)
            check("Relative link navigation loads the second HTTP page",
                  second_marker in linked_text)

            send_key(handle, "left")
            deadline = time.monotonic() + 25
            back_text = ""
            while time.monotonic() < deadline and marker not in back_text:
                length = _guest_u32(handle, content_len_addr)
                back_text = _guest_bytes(
                    handle, content_addr, min(max(length, 1), 512)).decode("ascii", "replace")
                if marker not in back_text:
                    time.sleep(0.25)
            check("Back navigation restores the previous HTTP page", marker in back_text)

            send_key(handle, "t")
            tabs = _wait_guest_u32(handle, tabs_addr, lambda value: value == 2)
            check("New-tab command creates a second tab", tabs == 2)
            send_key(handle, "tab")
            send_key(handle, "p")
            private = _wait_guest_u32(
                handle, private_addr, lambda value: (value & 0xff) != 0)
            check("Private browsing mode toggles on", (private & 0xff) != 0)

            send_key(handle, "slash")
            redirect_address = f"http://10.0.2.2:{port}/redirected"
            for char in redirect_address:
                send_key(handle, key_name(char))
            send_key(handle, "ret")
            deadline = time.monotonic() + 25
            redirect_text = ""
            while time.monotonic() < deadline and redirect_marker not in redirect_text:
                length = _guest_u32(handle, content_len_addr)
                redirect_text = _guest_bytes(
                    handle, content_addr, min(max(length, 1), 512)).decode("ascii", "replace")
                if redirect_marker not in redirect_text:
                    time.sleep(0.25)
            check("HTTP redirect is followed to its final page",
                  redirect_marker in redirect_text)

            send_key(handle, "b")
            state_word = _wait_guest_u32(
                handle, state_addr + 4,
                lambda value: ((value >> 16) & 0xff) >= 1)
            check("Bookmark command updates local browser state",
                  ((state_word >> 16) & 0xff) >= 1)

            send_key(handle, "slash")
            for char in "redirected":
                send_key(handle, key_name(char))
            suggestions = _wait_guest_u32(
                handle, suggestions_addr, lambda value: value >= 1)
            check("Address bar suggests matching local bookmarks and history",
                  suggestions >= 1)
            send_key(handle, "down")
            send_key(handle, "ret")
            deadline = time.monotonic() + 25
            suggested_text = ""
            while time.monotonic() < deadline and redirect_marker not in suggested_text:
                length = _guest_u32(handle, content_len_addr)
                suggested_text = _guest_bytes(
                    handle, content_addr, min(max(length, 1), 512)).decode("ascii", "replace")
                if redirect_marker not in suggested_text:
                    time.sleep(0.25)
            check("Selected address suggestion opens its saved URL",
                  redirect_marker in suggested_text)

            send_key(handle, "slash")
            chunked_address = f"http://10.0.2.2:{port}/chunked"
            for char in chunked_address:
                send_key(handle, key_name(char))
            send_key(handle, "ret")
            deadline = time.monotonic() + 25
            chunked_text = ""
            while time.monotonic() < deadline and chunked_marker not in chunked_text:
                length = _guest_u32(handle, content_len_addr)
                chunked_text = _guest_bytes(
                    handle, content_addr, min(max(length, 1), 512)).decode("ascii", "replace")
                if chunked_marker not in chunked_text:
                    time.sleep(0.25)
            check("HTTP/1.1 chunked transfer bodies are decoded",
                  chunked_marker in chunked_text)

            send_key(handle, "slash")
            plain_address = f"http://10.0.2.2:{port}/plain"
            for char in plain_address:
                send_key(handle, key_name(char))
            send_key(handle, "ret")
            deadline = time.monotonic() + 25
            plain_text = ""
            while time.monotonic() < deadline and plain_marker not in plain_text:
                length = _guest_u32(handle, content_len_addr)
                plain_text = _guest_bytes(
                    handle, content_addr, min(max(length, 1), 512)).decode("ascii", "replace")
                if plain_marker not in plain_text:
                    time.sleep(0.25)
            check("text/plain responses render without HTML tag stripping",
                  plain_marker in plain_text and "<literal-text>" in plain_text)
            send_key(handle, "d")
            downloaded = _wait_guest_u32(
                handle, downloaded_addr, lambda value: (value & 0xff) != 0)
            check("Download command saves the rendered page to MortFS",
                  (downloaded & 0xff) != 0)
            shot = os.path.join(BUILD, "browser-http.ppm").replace(os.sep, "/")
            _monitor(handle, f"screendump {shot}")
            check("Browser HTTP screenshot was captured",
                  os.path.exists(os.path.join(BUILD, "browser-http.ppm")))

            send_key(handle, "slash")
            binary_address = f"http://10.0.2.2:{port}/binary"
            for char in binary_address:
                send_key(handle, key_name(char))
            send_key(handle, "ret")
            deadline = time.monotonic() + 25
            binary_status = ""
            while time.monotonic() < deadline and "Unsupported HTTP content type" not in binary_status:
                binary_status = _guest_bytes(handle, status_addr, 64).split(b"\0", 1)[0].decode("ascii", "replace")
                if "Unsupported HTTP content type" not in binary_status:
                    time.sleep(0.25)
            check("Unsupported binary responses are rejected safely",
                  "Unsupported HTTP content type" in binary_status)
        finally:
            shutdown(handle)
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=5)

    handle = boot_iso(kernel_build.ISO, temp_disk)
    try:
        _wait_guest_u32(handle, ticks_addr, lambda value: value >= 100,
                        timeout_s=20)
        send_key(handle, "esc")
        send_key(handle, "f3")
        state = _guest_bytes(handle, state_addr, 8)
        check("Browser bookmarks survive a full reboot", state[6] >= 1)
    finally:
        shutdown(handle)
        try:
            os.remove(temp_disk)
        except OSError:
            pass

    failed = [name for name, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    return 0 if not failed else 1


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_smoke = sub.add_parser("smoke", help="build, boot, and smoke-test the shell")
    p_smoke.add_argument("--disk", default=None,
                         help="optional disk image to attach as -hda")
    sub.add_parser("usb-hotplug", help="test live UHCI detach and reattach")
    sub.add_parser("settings-ui", help="test Settings UI and persistence")
    sub.add_parser("browser-ui", help="test Vex browser HTTP and persistence")
    args = parser.parse_args(argv)
    if args.cmd == "smoke":
        return smoke(disk_img=args.disk)
    if args.cmd == "usb-hotplug":
        return usb_hotplug()
    if args.cmd == "settings-ui":
        return settings_ui()
    if args.cmd == "browser-ui":
        return browser_ui()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
