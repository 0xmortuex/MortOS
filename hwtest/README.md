# hwtest — hardware driver verification (claude-hardware)

Standalone QEMU proofs for the new-file hardware drivers on the `claude-hardware`
branch. Each driver lives in `net/<driver>.mx` and exposes a small, documented
API; the OS integration (calling `<driver>_init()` from `kmain.mx` and surfacing
status in `net/settings.mx`) is done by Codex, so these harnesses prove the
driver in isolation without touching either file.

## E1000 (Intel 82540EM gigabit Ethernet) — `net/e1000.mx`

Verified working: PCI discovery → MMIO map → reset → TX/RX ring setup → DMA
transmit, captured on the wire.

```
python hwtest/build_e1000_demo.py      # build hwtest/out/e1000_demo.elf
python hwtest/run_e1000_demo.py        # boot with -device e1000, capture TX
```

`run_e1000_demo.py` boots the demo kernel with an E1000 attached and a
`filter-dump`, then parses the pcap. Expected result:

```
present=y ready=y link=y
devid=100e error=00
mmio=febc0000
mac=52:54:00:12:34:56
tx frame bytes=3c            (x3)
-> pcap: 3 x 60-byte broadcast frames, ethertype 0x88B5, payload "E1000-OK",
   src = the card's own MAC. Proof the device transmits, not just PCI-detects.
```

### Integration hooks for Codex (kmain.mx / net/settings.mx)

Driver is pure and side-effect-free until called. To wire it into the OS:

**Boot hook (one line, after PCI/heap are up, near the rtl8139 bring-up):**

```
e1000_init();            // returns bool; also sets the status globals below
```

**Status globals to surface in Settings** (all in `net/e1000.mx`):

| global            | type      | meaning                                             |
|-------------------|-----------|-----------------------------------------------------|
| `g_e1000_present` | `bool`    | matching PCI device found on bus 0                  |
| `g_e1000_ready`   | `bool`    | init succeeded: rings up, TX/RX enabled             |
| `g_e1000_link`    | `bool`    | STATUS.LU — the link is actually up                 |
| `g_e1000_devid`   | `u16`     | matched PCI device id (0x100E / 0x100F / 0x10D3)    |
| `g_e1000_error`   | `u32`     | 0 = ok; 1 = no PCI device; 2 = BAR0 not memory-mapped |
| `g_e1000_mac`     | `[u8; 6]` | the card's MAC (also via `e1000_mac(out: u64)`)     |

Keep the three states distinct in the UI — "detected" (`present`), "driver
ready" (`ready`), and "link up" (`link`) are not the same thing; never label the
card Ready from `present` alone.

**Vendor/device IDs:** vendor `0x8086`; devices `0x100E` (82540EM, QEMU default
`-device e1000`), `0x100F` (82545EM), `0x10D3` (82574L / e1000e).

**Data path (available once ready):** `e1000_transmit(len: u32) -> bool` sends
`len` bytes staged in `g_e1000_tx_buf`; `e1000_send_test() -> u32` builds and
sends a broadcast probe frame. RX rings are configured (broadcast-accept, CRC
strip) but a poll/receive entry point is a follow-up milestone.

**Note:** `net/e1000.mx` reuses `pci_read32` / `pci_write32` (from
`net/rtl8139.mx`) and `eth_build_header` / `mac_broadcast` (from `net/eth.mx`) —
all present in the one-translation-unit kernel build, so no new dependencies.
