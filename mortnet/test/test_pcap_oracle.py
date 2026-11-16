#!/usr/bin/env python3
"""Validate the M1 capture oracle without QEMU.

demo/build_demo.py's verify_pcap() is what turns "we booted QEMU" into
PASS/FAIL. If it's wrong, the whole demo is meaningless. So here we hand it
synthetic pcaps — one holding exactly the frame glue/rtl8139.mx emits, and
several holding near-misses — and assert it accepts only the real thing.

    python test/test_pcap_oracle.py
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "demo"))
import build_demo  # noqa: E402


def pcap(frames):
    """A minimal little-endian pcap (Ethernet linktype) wrapping `frames`."""
    out = struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)
    for f in frames:
        out += struct.pack("<IIII", 0, 0, len(f), len(f)) + f
    return out


def mortnet_frame():
    """The exact bytes glue/rtl8139.mx builds: broadcast dst, a QEMU-style
    src MAC, EtherType 0x88B5, payload 'MORTNET'."""
    dst = b"\xff" * 6
    src = bytes([0x52, 0x54, 0x00, 0x12, 0x34, 0x56])
    etype = struct.pack(">H", 0x88B5)
    return dst + src + etype + b"MORTNET"


def main():
    tmp = os.path.join(ROOT, "build")
    os.makedirs(tmp, exist_ok=True)
    cases = []

    def case(name, data, want):
        path = os.path.join(tmp, f"oracle_{name}.pcap")
        with open(path, "wb") as fh:
            fh.write(data)
        got = build_demo.has_mortnet_frame(path)
        ok = (got == want)
        cases.append(ok)
        print(f"{'PASS' if ok else 'FAIL'}: {name} (oracle returned {got}, want {want})")
        os.remove(path)

    # The real frame must be accepted.
    case("real_frame", pcap([mortnet_frame()]), True)
    # Real frame among unrelated DHCP/ARP-ish noise: still accepted.
    case("frame_with_noise", pcap([b"\x00" * 60, mortnet_frame(), b"\x11" * 42]),
         True)
    # Right payload but unicast dst (not broadcast): rejected.
    bad_dst = bytes(range(6)) + mortnet_frame()[6:]
    case("not_broadcast", pcap([bad_dst]), False)
    # Broadcast + payload but wrong EtherType: rejected.
    wrong_type = mortnet_frame()[:12] + struct.pack(">H", 0x0800) + b"MORTNET"
    case("wrong_ethertype", pcap([wrong_type]), False)
    # Empty capture (nothing transmitted): rejected.
    case("empty_capture", pcap([]), False)

    passed = sum(cases)
    print(f"\n{passed}/{len(cases)} oracle checks passed.")
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    sys.exit(main())
