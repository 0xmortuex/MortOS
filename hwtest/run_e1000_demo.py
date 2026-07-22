#!/usr/bin/env python3
"""Boot the E1000 demo kernel in QEMU and verify it transmits on the wire.

Attaches `-device e1000` with user networking and a `filter-dump`, runs the demo
(which inits the card and sends three broadcast probe frames), then parses the
captured pcap. Prints the serial log and the decoded frames; exits non-zero if no
valid probe frame was captured.

    python hwtest/build_e1000_demo.py && python hwtest/run_e1000_demo.py
"""
import os
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "out")
ELF = os.path.join(OUT, "e1000_demo.elf")
PCAP = os.path.join(OUT, "e1000.pcap")

sys.path.insert(0, ROOT)
import build as b  # noqa: E402  (reuse _find_qemu)


def run_qemu():
    qemu = b._find_qemu()
    if not qemu:
        sys.exit("qemu-system-i386 not found")
    if not os.path.exists(ELF):
        sys.exit(f"demo not built: {ELF} (run build_e1000_demo.py first)")
    if os.path.exists(PCAP):
        os.remove(PCAP)
    cmd = [
        qemu, "-display", "none", "-serial", "stdio", "-no-reboot",
        "-kernel", ELF,
        "-netdev", "user,id=n0",
        "-device", "e1000,netdev=n0",
        "-object", f"filter-dump,id=f0,netdev=n0,file={PCAP}",
        "-device", "isa-debug-exit,iobase=0xf4,iosize=0x04",
    ]
    # The demo self-exits via isa-debug-exit; timeout is a safety net.
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        serial = res.stdout
    except subprocess.TimeoutExpired as e:
        serial = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
    print("----- serial log -----")
    print(serial.strip())
    print("----------------------")


def parse_pcap():
    if not os.path.exists(PCAP):
        sys.exit("FAIL: no pcap produced — the card did not transmit")
    data = open(PCAP, "rb").read()
    off, frames = 24, []
    while off + 16 <= len(data):
        _, _, incl, _ = struct.unpack("<IIII", data[off:off + 16])
        off += 16
        frames.append(data[off:off + incl])
        off += incl
    ok = 0
    for i, f in enumerate(frames, 1):
        dst = ":".join(f"{x:02x}" for x in f[0:6])
        src = ":".join(f"{x:02x}" for x in f[6:12])
        etype = (f[12] << 8) | f[13]
        payload = bytes(f[14:22])
        print(f"frame {i}: len={len(f)} dst={dst} src={src} "
              f"ethertype=0x{etype:04x} payload={payload!r}")
        if dst == "ff:ff:ff:ff:ff:ff" and etype == 0x88B5 and payload == b"E1000-OK":
            ok += 1
    if ok == 0:
        sys.exit("FAIL: no valid E1000 probe frame captured")
    print(f"PASS: {ok} valid E1000 broadcast probe frame(s) captured on the wire")


if __name__ == "__main__":
    run_qemu()
    parse_pcap()
