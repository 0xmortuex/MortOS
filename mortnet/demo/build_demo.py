#!/usr/bin/env python3
"""Build and run the mortnet M1 demo: MORT OS transmits an Ethernet frame.

    python demo/build_demo.py build    # -> build/net_demo.elf
    python demo/build_demo.py run      # build + boot in QEMU (windowed)
    python demo/build_demo.py capture  # build + boot headless, dump the frame
                                       #    the NIC sends to build/capture.pcap,
                                       #    then verify "MORTNET" is in it

The demo kernel is net/endian.mx + net/eth.mx + glue/rtl8139.mx + demo/net_demo.mx
compiled to freestanding C by mortc, cross-compiled to 32-bit x86 with Zig, and
linked with demo/boot.s + demo/linker.ld — the same recipe as MORT OS, minus the
GDT/IDT (the RTL8139 TX path is pure polling, so the demo needs no interrupts).

`capture` boots QEMU with an emulated RTL8139 whose traffic is written to a pcap
via `-object filter-dump`, then parses the pcap and asserts our broadcast frame
(dst ff:ff:ff:ff:ff:ff, EtherType 0x88B5, payload "MORTNET") is present. That
pcap is the M1 artifact — open it in Wireshark for the screenshot.

Requirements: Python 3.8+, Mort (sibling ../Mort or $MORT_HOME), `pip install
ziglang`, and QEMU (qemu-system-i386).
"""
import glob
import os
import shutil
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BUILD = os.path.join(ROOT, "build")
ELF = os.path.join(BUILD, "net_demo.elf")
PCAP = os.path.join(BUILD, "capture.pcap")
TARGET = "x86-freestanding-none"

# Every net/*.mx plus the driver, then one demo main appended last. Mort emits
# prototypes first so declaration order among these doesn't matter for calls.
NET_SOURCES = [
    os.path.join(ROOT, "net", "endian.mx"),
    os.path.join(ROOT, "net", "checksum.mx"),
    os.path.join(ROOT, "net", "eth.mx"),
    os.path.join(ROOT, "net", "ip.mx"),
    os.path.join(ROOT, "net", "udp.mx"),
    os.path.join(ROOT, "net", "icmp.mx"),
    os.path.join(ROOT, "net", "arp.mx"),
    os.path.join(ROOT, "net", "dhcp.mx"),
    os.path.join(ROOT, "net", "dns.mx"),
    os.path.join(ROOT, "net", "tcp.mx"),
    os.path.join(ROOT, "net", "http.mx"),
    os.path.join(ROOT, "net", "netcfg.mx"),
    os.path.join(ROOT, "glue", "rtl8139.mx"),
]
# Each demo is a separate kernel sharing the same stack.
DEMOS = {
    "capture": os.path.join(HERE, "net_demo.mx"),    # M1: transmit one frame
    "ping": os.path.join(HERE, "ping_demo.mx"),      # M2: ARP + ICMP round trip
    "dhcp": os.path.join(HERE, "dhcp_demo.mx"),      # M3: DHCP DORA handshake
    "dns": os.path.join(HERE, "dns_demo.mx"),        # M4: DNS A-record resolve
    "tcp": os.path.join(HERE, "tcp_demo.mx"),        # M5: TCP connection lifecycle
    "http": os.path.join(HERE, "http_demo.mx"),      # M6: HTTP server (serves a page)
}
SOURCES = NET_SOURCES + [DEMOS["capture"]]


def _find_mort():
    for c in (os.environ.get("MORT_HOME"),
              os.path.join(os.path.dirname(ROOT), "Mort"),
              os.path.join(ROOT, ".mort")):
        if c and os.path.isfile(os.path.join(c, "mortc.py")):
            return c
    dest = os.path.join(ROOT, ".mort")
    subprocess.run(["git", "clone", "--depth", "1",
                    "https://github.com/0xmortuex/Mort", dest], check=True)
    return dest


sys.path.insert(0, _find_mort())
import mortc  # noqa: E402


def _zig():
    cc = mortc.find_zig()
    if not cc:
        sys.exit("demo needs the Zig backend — run: pip install ziglang")
    return cc


def _find_qemu():
    found = shutil.which("qemu-system-i386")
    if found:
        return found
    for pattern in (r"C:\Program Files\qemu\qemu-system-i386.exe",
                    r"C:\Program Files*\qemu*\qemu-system-i386.exe"):
        hits = glob.glob(pattern)
        if hits:
            return hits[0]
    return None


def build(demo="capture"):
    os.makedirs(BUILD, exist_ok=True)
    cc = _zig()

    sources = NET_SOURCES + [DEMOS[demo]]
    combined = "".join(open(s, encoding="utf-8").read() + "\n" for s in sources)
    demo_c = os.path.join(BUILD, f"{demo}.c")
    with open(demo_c, "w", encoding="utf-8") as fh:
        fh.write(mortc.compile_to_c(combined, freestanding=True))

    # -mno-sse/-mmx: the kernel runs with SSE disabled (CR4.OSFXSR=0) and no
    # IDT, so a single compiler-emitted xorps/movsd would #UD -> triple fault.
    # Forbid vector codegen; the checksum/copy loops stay scalar.
    c_flags = ["-target", TARGET, "-ffreestanding", "-fno-stack-protector",
               "-fno-pie", "-fno-asynchronous-unwind-tables",
               "-fno-unwind-tables", "-mno-sse", "-mno-sse2", "-mno-mmx", "-O2"]
    demo_o = os.path.join(BUILD, f"{demo}.o")
    boot_o = os.path.join(BUILD, "boot.o")
    elf = os.path.join(BUILD, f"{demo}.elf")
    subprocess.run([*cc, *c_flags, "-c", demo_c, "-o", demo_o], check=True)
    subprocess.run([*cc, "-target", TARGET, "-fno-pie", "-c",
                    os.path.join(HERE, "boot.s"), "-o", boot_o], check=True)
    subprocess.run([
        *cc, "-target", TARGET, "-nostdlib", "-static", "-no-pie",
        "-Wl,-T," + os.path.join(HERE, "linker.ld"),
        "-Wl,--build-id=none", "-o", elf, boot_o, demo_o,
    ], check=True)
    print(f"built {os.path.relpath(elf, ROOT)}")
    return elf


def _qemu_net_args():
    # An emulated RTL8139 on a user-mode network, with every frame it sends or
    # receives mirrored into a pcap file. romfile= disables the card's iPXE boot
    # ROM, so SeaBIOS boots our kernel immediately (no PXE-boot delay) and the
    # capture holds only our stack's traffic, not iPXE's.
    return [
        "-device", "rtl8139,netdev=n0,romfile=",
        "-netdev", "user,id=n0",
        "-object", f"filter-dump,id=d0,netdev=n0,file={PCAP}",
    ]


def run():
    elf = build("ping")
    qemu = _find_qemu()
    if not qemu:
        sys.exit("qemu-system-i386 not found — install QEMU to run the demo.")
    subprocess.run([qemu, "-kernel", elf, *_qemu_net_args()])


def _boot_and_capture(elf, min_frames):
    """Boot the kernel headless with the NIC + pcap dump; return once the
    capture holds at least min_frames records and has settled, or after 20s."""
    qemu = _find_qemu()
    if not qemu:
        sys.exit("qemu-system-i386 not found — install QEMU to run the demo.")
    if os.path.exists(PCAP):
        os.remove(PCAP)

    print("Booting MORT OS headless with an RTL8139 + packet dump...")
    proc = subprocess.Popen([qemu, "-display", "none", "-kernel", elf,
                             *_qemu_net_args()])
    # A cold QEMU (first launch, Defender scan) can take seconds to start, and
    # the ARP/ICMP round trips trickle in over time — so poll, and once frames
    # start arriving give them a moment to settle rather than cutting off early.
    import time
    deadline = time.monotonic() + 20
    last_size, stable_since = -1, None
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            break
        size = os.path.getsize(PCAP) if os.path.exists(PCAP) else 0
        if size != last_size:
            last_size, stable_since = size, time.monotonic()
        n = len(_frames(PCAP))
        if n >= min_frames and stable_since and time.monotonic() - stable_since > 1.5:
            break
        time.sleep(0.25)
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def _frames(path):
    """Parse a pcap into a list of raw frame bytes (empty if unreadable)."""
    if not os.path.exists(path):
        return []
    with open(path, "rb") as fh:
        data = fh.read()
    if len(data) < 24:
        return []
    endian = "<" if struct.unpack("<I", data[:4])[0] in (0xA1B2C3D4, 0xA1B23C4D) else ">"
    off, out = 24, []
    while off + 16 <= len(data):
        _ts, _us, caplen, _orig = struct.unpack(endian + "IIII", data[off:off + 16])
        off += 16
        out.append(data[off:off + caplen])
        off += caplen
    return out


def has_mortnet_frame(path):
    """True iff the pcap holds our broadcast MORTNET frame. Shared by the M1
    demo and test/test_pcap_oracle.py so the verifier is checked without QEMU."""
    return any(len(f) >= 14 and f[0:6] == b"\xff" * 6
               and struct.unpack(">H", f[12:14])[0] == 0x88B5 and b"MORTNET" in f
               for f in _frames(path))


def capture():
    """M1: assert our broadcast 'MORTNET' frame is in the capture."""
    elf = build("capture")
    _boot_and_capture(elf, min_frames=1)
    frames = _frames(PCAP)
    hit = has_mortnet_frame(PCAP)
    if hit:
        print(f"PASS: {len(frames)} frame(s) captured; found the broadcast "
              f"MORTNET frame (EtherType 0x88B5).")
        print(f"      Open it in Wireshark:  {os.path.relpath(PCAP, ROOT)}")
        return 0
    print(f"FAIL: {len(frames)} frame(s) captured, none matched the MORTNET frame.")
    return 1


def ping():
    """M2: assert MORT OS emitted a valid ARP request and ICMP echo request to
    the gateway, and — if SLIRP answered — that the echo reply came back."""
    elf = build("ping")
    _boot_and_capture(elf, min_frames=2)
    frames = _frames(PCAP)

    OUR_IP, GW_IP = b"\x0a\x00\x02\x0f", b"\x0a\x00\x02\x02"
    arp_req = icmp_req = icmp_reply = False
    for f in frames:
        if len(f) < 14:
            continue
        etype = struct.unpack(">H", f[12:14])[0]
        if etype == 0x0806:                                   # ARP
            a = f[14:]
            if len(a) >= 28 and struct.unpack(">H", a[6:8])[0] == 1 and a[24:28] == GW_IP:
                arp_req = True                                # who-has 10.0.2.2, from us
        elif etype == 0x0800:                                 # IPv4
            ip = f[14:]
            if len(ip) >= 20 and ip[9] == 1:                  # ICMP
                ihl = (ip[0] & 0x0F) * 4
                icmp_type = ip[ihl] if len(ip) > ihl else None
                if icmp_type == 8 and ip[12:16] == OUR_IP and ip[16:20] == GW_IP:
                    icmp_req = True                           # our echo request out
                if icmp_type == 0 and ip[12:16] == GW_IP and ip[16:20] == OUR_IP:
                    icmp_reply = True                         # gateway's echo reply in

    print(f"      captured {len(frames)} frame(s): "
          f"ARP request={arp_req}  ICMP echo request={icmp_req}  echo reply={icmp_reply}")
    if arp_req and icmp_req:
        note = "full round trip — SLIRP answered." if icmp_reply else \
               "TX + RX verified (no gateway echo reply seen, host-test proves the answer path)."
        print(f"PASS: MORT OS spoke ARP and ICMP over the RTL8139. {note}")
        print(f"      Open it in Wireshark:  {os.path.relpath(PCAP, ROOT)}")
        return 0
    print("FAIL: expected at least a broadcast ARP request and an ICMP echo "
          "request to 10.0.2.2.")
    return 1


def _dhcp_msg_type(frame):
    """The DHCP message-type option (53) in a frame, or None if it isn't a
    DHCP packet (UDP 67<->68 with a magic cookie)."""
    if len(frame) < 14 or struct.unpack(">H", frame[12:14])[0] != 0x0800:
        return None
    ip = frame[14:]
    if len(ip) < 20 or ip[9] != 17:                       # not UDP
        return None
    ihl = (ip[0] & 0x0F) * 4
    udp = ip[ihl:]
    if len(udp) < 8:
        return None
    sport, dport = struct.unpack(">H", udp[0:2])[0], struct.unpack(">H", udp[2:4])[0]
    if 67 not in (sport, dport) or 68 not in (sport, dport):
        return None
    dhcp = udp[8:]
    if len(dhcp) < 240 or dhcp[236:240] != b"\x63\x82\x53\x63":   # magic cookie
        return None
    i = 240
    while i < len(dhcp):
        code = dhcp[i]
        if code == 255:
            break
        if code == 0:
            i += 1
            continue
        length = dhcp[i + 1]
        if code == 53:
            return dhcp[i + 2]
        i += 2 + length
    return None


def dhcp():
    """M3: assert MORT OS ran the DHCP handshake — DISCOVER, OFFER, REQUEST, ACK."""
    elf = build("dhcp")
    _boot_and_capture(elf, min_frames=4)
    types = [_dhcp_msg_type(f) for f in _frames(PCAP)]
    seen = set(t for t in types if t is not None)
    names = {1: "DISCOVER", 2: "OFFER", 3: "REQUEST", 5: "ACK"}
    got = ", ".join(names[t] for t in sorted(seen) if t in names) or "(none)"
    print(f"      DHCP messages captured: {got}")
    # We proved TX + parsing if we sent DISCOVER/REQUEST and the server answered
    # OFFER/ACK (which MORT OS had to parse to proceed from one to the next).
    if {1, 2, 3, 5} <= seen:
        print("PASS: MORT OS earned its IP via DHCP — full DISCOVER/OFFER/"
              "REQUEST/ACK handshake.")
        print(f"      Open it in Wireshark:  {os.path.relpath(PCAP, ROOT)}")
        return 0
    print("FAIL: expected all four of DISCOVER, OFFER, REQUEST, ACK.")
    return 1


def _udp_payload(frame, want_dport=None, want_sport=None):
    """Return (src_port, dst_port, payload) for a UDP frame, or None."""
    if len(frame) < 14 or struct.unpack(">H", frame[12:14])[0] != 0x0800:
        return None
    ip = frame[14:]
    if len(ip) < 20 or ip[9] != 17:
        return None
    ihl = (ip[0] & 0x0F) * 4
    udp = ip[ihl:]
    if len(udp) < 8:
        return None
    sport, dport = struct.unpack(">H", udp[0:2])[0], struct.unpack(">H", udp[2:4])[0]
    if want_dport is not None and dport != want_dport:
        return None
    if want_sport is not None and sport != want_sport:
        return None
    return sport, dport, udp[8:]


def dns():
    """M4: assert MORT OS sent a DNS query and parsed an A record from the reply."""
    elf = build("dns")
    _boot_and_capture(elf, min_frames=2)
    frames = _frames(PCAP)

    sent_query = False
    answer_ip = None
    for f in frames:
        to53 = _udp_payload(f, want_dport=53)
        if to53:
            sent_query = True
        from53 = _udp_payload(f, want_sport=53)
        if from53:
            dnsmsg = from53[2]
            if len(dnsmsg) >= 12:
                ancount = struct.unpack(">H", dnsmsg[6:8])[0]
                # walk to the first A record (skip question, skip names)
                ip = _first_a_record(dnsmsg, ancount)
                if ip:
                    answer_ip = ip
    verdict = f"query sent={sent_query}  answer A record={'.'.join(map(str, answer_ip)) if answer_ip else None}"
    print(f"      {verdict}")
    if sent_query and answer_ip:
        print(f"PASS: MORT OS resolved a hostname over DNS to {'.'.join(map(str, answer_ip))}.")
        print(f"      Open it in Wireshark:  {os.path.relpath(PCAP, ROOT)}")
        return 0
    print("FAIL: expected a DNS query to :53 and an A record in the reply "
          "(needs outbound DNS via SLIRP).")
    return 1


def _skip_name(msg, off):
    while off < len(msg):
        b = msg[off]
        if b == 0:
            return off + 1
        if (b & 0xC0) == 0xC0:
            return off + 2
        off += 1 + b
    return off


def _first_a_record(msg, ancount):
    """Mirror of net/dns.mx dns_first_a, for verifying the capture."""
    if ancount == 0 or len(msg) < 12:
        return None
    off = _skip_name(msg, 12) + 4          # past question name + QTYPE/QCLASS
    for _ in range(ancount):
        off = _skip_name(msg, off)
        if off + 10 > len(msg):
            return None
        atype = struct.unpack(">H", msg[off:off + 2])[0]
        rdlength = struct.unpack(">H", msg[off + 8:off + 10])[0]
        rdata = off + 10
        if atype == 1 and rdlength == 4 and rdata + 4 <= len(msg):
            return tuple(msg[rdata:rdata + 4])
        off = rdata + rdlength
    return None


def _tcp_flag_names(f):
    names = []
    for bit, name in ((0x02, "SYN"), (0x10, "ACK"), (0x08, "PSH"),
                      (0x01, "FIN"), (0x04, "RST")):
        if f & bit:
            names.append(name)
    return "|".join(names) or "-"


def tcp():
    """M5: run a host TCP server (reached from the guest via SLIRP at 10.0.2.2),
    have MORT OS connect, and verify the handshake + data + close, plus that the
    server actually received MORT OS's request bytes."""
    import socket
    import threading

    result = {"got": None, "connected": False}

    def server():
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 8888))
        srv.listen(1)
        srv.settimeout(20)
        try:
            conn, _addr = srv.accept()
        except OSError:
            srv.close()
            return
        result["connected"] = True
        conn.settimeout(8)
        try:
            result["got"] = conn.recv(1024)
            conn.sendall(b"HELLO-MORTNET\n")
        except OSError:
            pass
        try:
            conn.close()
        except OSError:
            pass
        srv.close()

    th = threading.Thread(target=server, daemon=True)
    th.start()

    elf = build("tcp")
    _boot_and_capture(elf, min_frames=6)      # SYN, SYN-ACK, ACK, data x2, FINs
    th.join(timeout=3)

    # Classify the captured TCP segments between our port (40001) and 8888.
    frames = _frames(PCAP)
    seen = {"syn": False, "synack": False, "our_data": False,
            "server_data": False, "fin_from_us": False}
    for f in frames:
        if len(f) < 34 or struct.unpack(">H", f[12:14])[0] != 0x0800:
            continue
        ip = f[14:]
        if len(ip) < 20 or ip[9] != 6:                        # not TCP
            continue
        ihl = (ip[0] & 0x0F) * 4
        tcp_seg = ip[ihl:]
        if len(tcp_seg) < 20:
            continue
        sport, dport = struct.unpack(">H", tcp_seg[0:2])[0], struct.unpack(">H", tcp_seg[2:4])[0]
        flags = tcp_seg[13]
        doff = (tcp_seg[12] >> 4) * 4
        payload = tcp_seg[doff:]
        outbound = sport == 40001
        if flags & 0x02 and not (flags & 0x10) and outbound:
            seen["syn"] = True
        if (flags & 0x02) and (flags & 0x10) and not outbound:
            seen["synack"] = True
        if outbound and payload:
            seen["our_data"] = True
        if (not outbound) and payload:
            seen["server_data"] = True
        if (flags & 0x01) and outbound:
            seen["fin_from_us"] = True

    got = result["got"]
    print(f"      handshake: SYN={seen['syn']} SYN-ACK={seen['synack']}  "
          f"data out={seen['our_data']} in={seen['server_data']}  "
          f"our FIN={seen['fin_from_us']}")
    print(f"      host server received from MORT OS: {got!r}")

    handshake_ok = seen["syn"] and seen["synack"]
    data_ok = got == b"mortnet\n" and seen["server_data"]
    if handshake_ok and data_ok and seen["fin_from_us"]:
        print("PASS: MORT OS opened a TCP connection, exchanged data, and closed "
              "cleanly. The host server received exactly what MORT OS sent.")
        print(f"      Open it in Wireshark:  {os.path.relpath(PCAP, ROOT)}")
        return 0
    print("FAIL: expected full handshake, bidirectional data ('mortnet\\n' at the "
          "server), and a FIN from MORT OS.")
    return 1


def http():
    """M6 (finale): MORT OS listens on TCP 80 and serves a page. Boot it with a
    host->guest port forward (8080 -> 80), then GET http://127.0.0.1:8080/ from
    the host and verify MORT OS generated the response."""
    import time
    import urllib.request

    elf = build("http")
    qemu = _find_qemu()
    if not qemu:
        sys.exit("qemu-system-i386 not found — install QEMU to run the demo.")
    if os.path.exists(PCAP):
        os.remove(PCAP)

    net_args = [
        "-device", "rtl8139,netdev=n0,romfile=",
        "-netdev", "user,id=n0,hostfwd=tcp:127.0.0.1:8080-10.0.2.15:80",
        "-object", f"filter-dump,id=d0,netdev=n0,file={PCAP}",
    ]
    print("Booting MORT OS as an HTTP server (headless), forwarding :8080 -> :80 ...")
    proc = subprocess.Popen([qemu, "-display", "none", "-kernel", elf, *net_args])

    body = None
    deadline = time.monotonic() + 30
    try:
        while time.monotonic() < deadline and body is None:
            if proc.poll() is not None:
                break
            try:
                with urllib.request.urlopen("http://127.0.0.1:8080/", timeout=2) as r:
                    body = r.read().decode("utf-8", "replace")
            except Exception:
                time.sleep(0.5)          # server not up yet (cold boot) — retry
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    if body and "Served by MORT OS" in body:
        first = body.splitlines()[0] if body.splitlines() else body[:40]
        print(f"      GET / returned {len(body)} bytes; title line: {first[:60]!r}")
        print("PASS: MORT OS served an HTTP page over its own TCP/IP stack.")
        print(f"      Open it in a browser:  http://127.0.0.1:8080/  (while the server runs)")
        return 0
    print(f"FAIL: no valid page returned (got {body[:80]!r} )." if body
          else "FAIL: the server never answered on :8080.")
    return 1


COMMANDS = {"build": build, "run": run, "capture": capture, "ping": ping,
            "dhcp": dhcp, "dns": dns, "tcp": tcp, "http": http}

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd not in COMMANDS:
        sys.exit(f"unknown command {cmd!r}; use one of: {', '.join(COMMANDS)}")
    rc = COMMANDS[cmd]()
    sys.exit(rc or 0)
