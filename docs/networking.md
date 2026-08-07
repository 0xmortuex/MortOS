# Networking (mortnet)

MORT OS vendors [mortnet](https://github.com/0xmortuex/mortnet) — a TCP/IP
stack written from scratch in Mort — into `net/`, and compiles it into the
kernel as part of the same translation unit as `kmain.mx`. This is a map of
which file implements which layer, and how the two shell commands (`net`,
`httpd`) actually drive it at runtime.

Not every file under `net/` is part of the protocol stack: `net/hardware.mx`
(generic PCI capability scan + PC-speaker audio), `net/audio.mx`,
`net/hci_usb.mx` (USB host-controller enumeration), and `net/settings.mx`
(the Settings app) live here too but are unrelated to mortnet. This document
only covers the networking layers.

## Layers, bottom to top

| Layer | File | What it does |
|---|---|---|
| Byte order | `net/endian.mx` | `hton16`/`ntoh16`/`hton32`/`ntoh32` (`net/endian.mx:19`-`22`) and big/little-endian load/store helpers on raw memory addresses — `be16_load`/`be16_store`/`be32_load`/`be32_store` and `le16_load` (the last for reading NIC-DMA'd fields, which land in native little-endian order per the comment at `net/endian.mx:44`-`46`). |
| Checksum | `net/checksum.mx` | The RFC 1071 Internet checksum shared by IPv4/ICMP/UDP/TCP: `inet_sum` accumulates one's-complement 16-bit words without folding, so a UDP/TCP pseudo-header can be summed separately from the segment (`net/checksum.mx:16`-`28`); `inet_fold`/`inet_checksum` finish it (`net/checksum.mx:31`-`41`). |
| NIC driver | `net/rtl8139.mx` | An RTL8139 driver: `rtl_init` (`net/rtl8139.mx:63`) finds the card by scanning PCI bus 0 for vendor `0x10EC`/device `0x8139`, enables bus mastering, and programs a receive ring; `rtl_transmit` (`net/rtl8139.mx:174`) fires a TX descriptor; `rtl_poll_rx` (`net/rtl8139.mx:128`) copies one waiting frame (CRC stripped) out of the ring, non-blocking. |
| Ethernet | `net/eth.mx` | 14-byte Ethernet II framing: `eth_build_header`/`eth_type`/`eth_payload` (`net/eth.mx:44`-`69`), plus MAC helpers `mac_copy`/`mac_eq`/`mac_broadcast`. |
| ARP | `net/arp.mx` | RFC 826 address resolution — `arp_build_request`/`arp_build_reply` (`net/arp.mx:25`-`58`), used to answer "who has our IP?". |
| IPv4 | `net/ip.mx` | RFC 791 header, no fragmentation or options — `ip_verify`/`ip_build_header` (`net/ip.mx:50`-`76`). |
| ICMP | `net/icmp.mx` | Echo request/reply only (ping) — `icmp_build_echo_reply` flips type 8→0 and recomputes the checksum over the whole message (`net/icmp.mx:46`-`58`). |
| UDP | `net/udp.mx` | RFC 768 — `udp_build`/`udp_verify` (`net/udp.mx:31`-`53`), the transport DHCP and DNS ride on. |
| DHCP | `net/dhcp.mx` | RFC 2131 client (DORA exchange): `dhcp_build_discover`/`dhcp_build_request` (`net/dhcp.mx:50`-`73`) and `dhcp_find_option`/`dhcp_msg_type` (`net/dhcp.mx:76`-`104`) to parse OFFER/ACK. |
| DNS | `net/dns.mx` | RFC 1035 resolver client for A records — `dns_build_query` (`net/dns.mx:58`) and `dns_first_a` (`net/dns.mx:98`), including compression-pointer-aware name skipping (`dns_skip_name`, `net/dns.mx:73`). **Implemented and host-testable but not currently called from anywhere in the kernel** — no shell command or `net/netapp.mx` code path invokes it (verified by grep for `dns_` outside this file). It resolves no hostnames at runtime today. |
| TCP | `net/tcp.mx` | RFC 793 segment format and checksum only — `tcp_build`/`tcp_verify` (`net/tcp.mx:55`-`78`). Per the file's own header comment (`net/tcp.mx:4`-`6`), the connection state machine (handshake, sequence tracking, teardown) is deliberately kept out of this file so the wire format stays host-testable; that state machine lives inline in `net_httpd` (see below). |
| HTTP | `net/http.mx` | A minimal HTTP/1.1 response builder — `http_build_response` (`net/http.mx:63`) writes a `200 OK` with a correct `Content-Length`, and `http_is_get` (`net/http.mx:82`) checks for a `GET ` request line. |
| Dispatch | `net/netcfg.mx` | `net_handle_frame` (`net/netcfg.mx:29`) is a pure frame-in/frame-out function: given a received Ethernet frame, it decides whether to answer (an ARP reply, or an ICMP echo reply) and builds the whole response. No hardware I/O, which is what makes it testable on the host against captured packets. |
| Kernel bridge | `net/netapp.mx` | Wires the stack above to the kernel's shell and NIC driver — see below. |

## What `net` and `httpd` actually do

Both are shell commands dispatched in `run_command_impl`
(`kmain.mx:2131`-`2137`), which call straight into `net/netapp.mx`:

- **`net`** runs `net_dhcp` (`net/netapp.mx:46`). It calls `rtl_init` to bring
  up the NIC, reads the card's burned-in MAC via `rtl_mac`, then builds and
  broadcasts a DHCP DISCOVER (`net_dhcp_send`, `net/netapp.mx:124`, which
  wraps a `dhcp_build_discover` body in UDP/IP/Ethernet by hand — it does not
  go through `net_handle_frame`). It polls `rtl_poll_rx` in a spin loop
  (`net/netapp.mx:77`-`115`), watching for a DHCP OFFER, sending a REQUEST in
  reply, and finishing when an ACK lands — at which point `net_set_ip` records
  the leased address and prints it. There is no fallback: if no OFFER arrives
  before the spin count runs out, `net` prints `DHCP: no response (timeout)`
  and returns false.
- **`httpd`** runs `net_httpd` (`net/netapp.mx:176`), an infinite loop (until
  reboot) that polls `rtl_poll_rx` and, per received frame: hands it to
  `net_handle_frame` for automatic ARP/ICMP replies, and separately runs its
  own inline single-connection TCP server state machine
  (`net/netapp.mx:193`-`259`) — SYN → SYN/ACK, then on the first `GET`
  payload it serves the fixed page from `net_page` (`net/netapp.mx:141`)
  via `http_build_response`, then FIN. It only tracks one connection's state
  (`g_h_mac`/`g_h_ip`/`g_h_port`/`g_h_snd`/`g_h_rcv`, `net/netapp.mx:146`-`151`)
  at a time, and requires `net` to have already leased an address
  (`g_net_up`, checked at `net/netapp.mx:177`).

Note that `net/netcfg.mx` initializes `g_our_ip` to a hardcoded
`10.0.2.15` (`net/netcfg.mx:13`) — QEMU's default SLIRP guest address — but
`net_dhcp` immediately zeroes it (`net/netapp.mx:58`) and then overwrites it
with whatever address DHCP actually leases, so the hardcoded value is never
the address the kernel answers on once `net` has run.

## Not covered by automated tests

None of the repo's test scripts (`test.py`, `test_fs.py`, `test_exec.py`,
`test_gfx.py`) exercise `net` or `httpd` — a grep for `net`, `httpd`, `rtl`,
and `dhcp` across them turns up nothing. `net/rtl8139.mx`'s own header
comment says as much: it is "proven by booting QEMU with `-device rtl8139`
and watching the frame it sends land in a packet capture," i.e. verified
manually, not by CI.
