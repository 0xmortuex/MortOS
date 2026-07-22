# Wi-Fi driver research — chipset selection for MORT OS

Priority-D deliverable for the `claude-hardware` branch. Per the coordination
brief this is **research, not a driver**: select ONE documented chipset, record
its firmware requirements and IDs, and lay out the state machine — explicitly
*not* a fake "generic Wi-Fi driver." This document is the groundwork a real
driver would start from.

## TL;DR

- **Selected chipset: Atheros AR9002 family (`ath9k`), reference part AR9280.**
- **Firmware requirement: NONE** for the PCI/PCIe AR9002/AR9003 parts — the host
  driver talks to the silicon directly; calibration/regulatory data lives in the
  card's own EEPROM/OTP. This is the deciding factor for a from-scratch OS with
  no firmware-loading facility.
- **Cannot be verified in QEMU** — QEMU emulates no Wi-Fi NIC. A driver is
  testable only on real hardware (PCIe passthrough to a VM, or MORT OS on bare
  metal, which it already boots on).

## Why this is different from the A–E drivers

E1000 / AHCI / HD Audio / ACPI are all emulated by QEMU, so each got a headless
boot + captured-proof harness. **There is no virtual Wi-Fi device in QEMU** (no
`-device wifi` of any kind; the emulated NICs are all wired Ethernet). So a Wi-Fi
driver:

1. can only run against a **real** Atheros card (VFIO/PCIe passthrough, or bare
   metal), and
2. is a *much* larger undertaking than a wired NIC — it needs an 802.11 MAC-layer
   software stack (scanning, authentication, association) and, for real networks,
   a WPA2 supplicant, on top of the hardware bring-up.

That scale and the lack of an emulated target are exactly why the brief scoped
this to research.

## Chipset selection

### Chosen: Atheros AR9002 (`ath9k`), reference AR9280

Atheros `ath9k`-supported PCIe parts are the standard choice for from-scratch and
teaching OSes because **they require no downloadable firmware**. The MAC,
baseband, and radio are all driven directly by host register writes; the only
per-card data (calibration, regulatory limits, MAC address) is read from the
card's on-board EEPROM/OTP.

PCI vendor: **`0x168C`** (Atheros / Qualcomm Atheros). Device IDs (AR9002/AR9003
PCIe, all firmware-free):

| Device id | Part    | Notes                                  |
|-----------|---------|----------------------------------------|
| `0x0029`  | AR9220/AR9223 | 802.11n                          |
| `0x002A`  | **AR9280** | PCIe, dual-band 2x2 — reference part |
| `0x002B`  | AR9285  | PCIe, single-stream 1x1 (netbooks)     |
| `0x002D`  | AR9227  | PCI                                    |
| `0x002E`  | AR9287  | PCIe, 2x2 2.4 GHz                       |
| `0x0030`  | AR9300  | AR9003 family, 802.11n 3x3             |
| `0x0032`  | AR9485  | AR9003 1x1                             |
| `0x0034`  | AR9462  | AR9003 2x2 + Bluetooth coexist         |
| `0x0036`  | AR9565  | AR9003 1x1 + BT                        |

(Match on vendor `0x168C` + one of these device ids; the PCI **class** is
`0x02 / 0x80` — network controller / "other", not Ethernet `0x02/0x00`.)

### Firmware requirements — the key finding

- **AR9002 / AR9003 PCIe: no firmware blob.** Nothing to load; bring-up is pure
  register programming plus EEPROM-driven calibration.
- **Explicitly NOT selected — the USB Atheros parts** (AR9271, AR7010, driver
  `ath9k_htc`) **do** need firmware (`htc_9271.fw`, `htc_7010.fw`). Excluded
  precisely because they reintroduce the firmware-loading barrier.
- **Also excluded — ath10k/ath11k** (QCA988x and newer): large firmware +
  board-data blobs and a firmware command interface. Out of scope.

The card's EEPROM/OTP is **not** a downloaded firmware blob — it is factory data
on the card, read over a register interface during init.

## Hardware interface (what a driver would touch)

PCIe device, single MMIO BAR (BAR0). Same shape as the E1000/AHCI work already on
this branch (memory-mapped registers + DMA descriptor rings), but with far more
register state. Register **regions** (exact offsets: see `ath9k`'s `reg.h` in the
Linux tree, or OpenBSD `athn(4)` `ar5008reg.h`/`ar9280.c`):

- **RTC / reset** (`AR_RTC_*`, ~`0x7000`): warm and cold chip reset, clock/PLL
  bring-up, sleep/wake.
- **MAC DMA** (`AR_CR`, `AR_RXDP`, `AR_Q_TXDP[]`, `AR_CFG`): RX descriptor
  pointer, ten TX queue descriptor pointers (QCU/DCU hardware queues for QoS),
  command/config.
- **Interrupts** (`AR_ISR`, `AR_IMR`, `AR_IER`): status/mask/enable.
- **MAC PCU** (`AR_STA_ID0/1`, `AR_BSS_ID0/1`, `AR_RX_FILTER`, `AR_DIAG_SW`):
  station MAC address, BSSID, receive filter, protocol control.
- **Baseband / PHY** (`AR_PHY_*`, ~`0x9800`): the large chip- and band-specific
  INI register arrays written at init.
- **Analog / RF** (via `AR_PHY_RFBUS_REQ` / `AR_PHY_RFBUS_GRANT`): the radio
  registers are reached through an RF-bus grant handshake.
- **EEPROM** (`AR_EEPROM_*`): calibration, regulatory domain, and MAC address.

DMA: legacy or "EDMA" (AR9003) RX/TX descriptor rings of 802.11 frames, DMA'd to
identity-mapped buffers (MORT OS runs paging-off, as the other drivers rely on).
Hardware crypto (WEP/TKIP/**AES-CCMP**) is offloaded via a key-cache; a driver can
start software-only and add the key cache later.

## Bring-up sequence (hardware)

1. **PCI**: match `0x168C:<id>`, map BAR0, enable memory space + bus master.
2. **Chip reset**: cold reset via `AR_RTC_RC`, bring up PLL/clocks, wait for
   `AR_RTC_STATUS` to report "on".
3. **EEPROM**: read + checksum the EEPROM; extract MAC address, regulatory
   domain, and the per-band calibration data.
4. **Baseband + RF init**: write the chip/band INI register arrays, then run the
   **calibration** loops (ADC/DC-offset, I/Q imbalance, noise-floor). *This is the
   hardest, most chip-specific part* and is why "no firmware" does not mean
   "simple."
5. **DMA rings**: allocate RX/TX descriptor rings + buffers, program `AR_RXDP` /
   `AR_Q_TXDP[]`.
6. **MAC**: program `AR_STA_ID*` (our MAC), `AR_RX_FILTER`, channel/rate.
7. **Enable**: RX (`AR_CR`) and interrupts (`AR_IMR`/`AR_IER`).

At this point the radio can send/receive raw 802.11 frames on a channel — but is
**not** on any network yet.

## 802.11 software stack (above the driver)

`ath9k` is a **softmac** driver: on Linux it leans on `mac80211` for the MAC-layer
management (MLME). A from-scratch OS must provide that itself:

- **Scanning**: hop channels, transmit probe requests, parse beacons / probe
  responses into a BSS list (SSID, channel, security, signal).
- **Authentication + Association**: the 802.11 auth then assoc-request/response
  exchange with the chosen AP.
- **Security (WPA2/WPA3)**: an EAPOL 4-way handshake (a supplicant) to derive
  keys, then install them in the hardware key cache (AES-CCMP). Open networks skip
  this.
- **Then** the existing network stack (`net/*.mx`: DHCP → IP) runs over the Wi-Fi
  link exactly as it does over Ethernet.

## State machine — detected / driver-ready / connected

The brief requires these be **separate** states; conflating them is the classic
Wi-Fi-UI lie. Concretely:

| State            | True when…                                                        | Does NOT mean |
|------------------|-------------------------------------------------------------------|---------------|
| **detected**     | PCI match `0x168C:<id>` found; BAR mapped                          | the driver works, or a radio is usable |
| **driver-ready** | reset done, EEPROM parsed, baseband/RF init + calibrated, DMA + MAC up, RX on | associated with anything, or online |
| **connected**    | associated with an AP (auth+assoc) **and**, for secured nets, 4-way handshake done + keys installed | has an IP address (that's DHCP, a further step: **connected → configured**) |

Mirror the pattern already used by `net/e1000.mx` / `net/ahci.mx`: distinct
booleans (`wifi_detected`, `wifi_ready`, `wifi_connected`) so Settings can never
show "Ready" from PCI detection alone.

## Rejected alternatives

- **Intel `iwlwifi`** (7260/8260/9260/AX200…): excellent hardware, but every part
  needs a versioned firmware ucode blob loaded over DMA plus a host-command /
  notification protocol. The firmware-loading infrastructure alone is a major
  barrier for an OS with no blob-loading facility. Deferred, not chosen.
- **Realtek** (RTL8188/8192, USB-heavy): firmware required, documentation
  scattered and inconsistent.
- **Broadcom** (`brcmfmac`): proprietary, firmware-gated, poorly documented.

## Proposed milestones (real hardware only)

A future driver would proceed like the A–E drivers but tested on a real AR9280
(PCIe passthrough or bare metal), each milestone gating the next state:

- **M0 — detected**: PCI match + BAR map + cold reset + read MAC from EEPROM.
  (First real-hardware checkpoint: print the card's MAC.)
- **M1 — driver-ready**: INI + calibration + DMA rings + RX enabled; prove it by
  capturing raw 802.11 beacon frames from the air on a channel.
- **M2 — scan**: channel hop + probe + build a BSS list (see nearby SSIDs).
- **M3 — connect (open)**: auth + assoc to an open AP; then DHCP over the link.
- **M4 — connect (WPA2)**: EAPOL 4-way handshake + AES-CCMP key cache.

Each is many times the size of a wired-NIC milestone; M1's calibration is the
steepest single step.

## References

- Linux `drivers/net/wireless/ath/ath9k/` — `reg.h` (register map), `eeprom_*.c`,
  `calib.c`, `hw.c` (reset + INI + calibration). The authoritative register-level
  source.
- OpenBSD `athn(4)` (`sys/dev/ic/ar9280.c`, `ar5008.c`, `arn.c`) — a compact,
  BSD-licensed, single-driver implementation; often easier to read end-to-end than
  the Linux mac80211-split driver.
- IEEE 802.11 (management frame formats, auth/assoc, EAPOL) for the software MAC.
- `linux-firmware` `ath9k_htc/` — evidence that only the **USB** Atheros parts
  need firmware; the PCIe AR9002/AR9003 parts have no entry (i.e. no blob).
