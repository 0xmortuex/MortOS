# Hardware: PCI, USB, and audio

Three files cover device discovery beyond the boot-critical framebuffer, PS/2
keyboard, and ATA disk drivers: `net/hardware.mx` (generic PCI capability
scan + the legacy PC speaker), `net/hci_usb.mx` (a UHCI USB 1.1
host-controller driver), and `net/audio.mx` (an Intel AC'97 audio driver).
They live under `net/` only because `build.py`'s glue loop compiles every
`net/*.mx` file into the same translation unit as `kmain.mx`
(`build.py:113`-`121`, per the header comment in `net/settings.mx`); none of
the three touch mortnet. `docs/networking.md` covers the actual TCP/IP
stack.

## PCI capability scan (`net/hardware.mx:12`-`34`)

`hw_scan_pci()` walks all 32 PCI slots × 8 functions on bus 0, reading each
device's class/subclass byte pair from PCI config space (mechanism #1, ports
`0xCF8`/`0xCFC` — the same `pci_read32`/`pci_write32` helpers defined in
`net/rtl8139.mx:46`-`54` and shared by all three files here). For every
device found it sets one of four capability flags by class/subclass:

| Class | Subclass | Flag set |
|---|---|---|
| `0x02` (network controller) | `0x00` | `g_hw_ethernet` |
| `0x0d` (wireless controller), or `0x02`/`0x80` | — | `g_hw_wifi` |
| `0x04` (multimedia controller) | `0x01` or `0x03` | `g_hw_audio` |
| `0x0c` (serial bus controller) | `0x03` | `g_hw_usb` |

(`net/hardware.mx:26`-`29`). `g_hw_pci_count` counts every responding
`(slot, func)` regardless of class. The scan is **not** run at boot — it
only runs the first time the Settings app's Hardware page is opened
(`if !g_hw_scanned { hw_scan_pci(); }`, `net/settings.mx:281`), or on a
manual rescan (`net/settings.mx:504`, `529`).

## PC speaker (`net/hardware.mx:36`-`58`)

`speaker_start(freq)` programs PIT channel 2 (port `0x43` command, port
`0x42` data) with a frequency divisor (`1193182 / freq`) and sets bits 0-1
of port `0x61` to gate the divider output into the speaker. `speaker_stop()`
clears those two bits. `speaker_test()` plays an 880 Hz tone for a fixed
busy-wait spin count (no PIT-tick timing). All three are no-ops when
`g_speaker_enabled` is `false` (default `true`, `net/hardware.mx:10`) — the
Settings speaker toggle flips that flag (`net/settings.mx:530`).

## Ethernet disconnect (`net/hardware.mx:60`-`66`)

`ethernet_disconnect()` clears `g_net_up` and, if the RTL8139 is up, writes
`0x00` to its command register (I/O base + `0x37`) to stop the receiver and
transmitter, then clears `g_rtl_ok`. Wired to the Settings network page's
disconnect action (`net/settings.mx:543`). There is no matching "start" path
here — reconnecting goes back through `net_dhcp` (`net/settings.mx:541`),
which calls `rtl_init` itself (see `docs/networking.md`).

## USB: UHCI host controller (`net/hci_usb.mx`)

Boot-time only: `usb_boot_init()` runs once from `kmain()`
(`kmain.mx:3616`), after the filesystem/account/shell setup but *before*
`init_pit()` and `asm("sti")` — so the whole USB sequence below runs with
interrupts off, purely by polling. The register-write comment at
`net/hci_usb.mx:205` says so directly: `outw(g_usb_io + 0x04, 0); //
polling until IRQ support is added`.

1. **Find the controller** — `usb_find_uhci()` (`net/hci_usb.mx:162`-`178`)
   walks PCI bus 0 for a device with class `0x0c`/subclass `0x03`/prog-if
   `0x00` (UHCI), reads its I/O base from BAR4 (config offset `0x20`), and
   enables I/O + bus-master in the command register.
2. **Reset the controller** — a global reset, then a host-controller reset,
   pulsed on the UHCI command register (`net/hci_usb.mx:198`-`204`).
3. **Probe the two root ports** — `usb_boot_reset_port()`
   (`net/hci_usb.mx:180`-`193`) pulses the port-reset bit on port offset
   `0x10` (root port 1), and if nothing answers, `0x12` (root port 2)
   (`net/hci_usb.mx:207`-`215`). It reads back the port-status register into
   `g_usb_port_status` and sets `g_usb_low_speed` from its low-speed bit
   (`0x0100`).
4. **Enumerate the first device found** — a hand-built control-transfer
   pipeline using a fixed frame list (`g_usb_frame_mem`) and a single
   queue head (`g_usb_qh`/`usb_td`, `net/hci_usb.mx:28`-`30`) that chains
   transfer descriptors:
   - `usb_boot_descriptor8()` (`:32`-`64`) — `GET_DESCRIPTOR` for the first
     8 bytes of the device descriptor (enough to read `bMaxPacketSize0`).
   - `usb_boot_set_address()` (`:66`-`80`) — `SET_ADDRESS(1)`.
   - `usb_boot_descriptor18()` (`:82`-`108`) — the full 18-byte device
     descriptor at the new address; extracts `g_usb_class`,
     `g_usb_max_packet`, `g_usb_vid`, `g_usb_pid`.
   - `usb_boot_parse_configuration()` (`:140`-`160`) — fetches the
     configuration descriptor (9 bytes, then the full `wTotalLength`, up to
     64 bytes captured), walks its sub-descriptors for the first interface
     descriptor (type `4`), and records
     `g_usb_interface_class`/`_subclass`/`_protocol`. If that interface is
     class `0xe0`/subclass `0x01` (the standard Bluetooth-HCI-over-USB
     class), it sets `g_hw_bluetooth = true` (`net/hci_usb.mx:155`) — this
     is the *only* thing that sets that flag; there is no Bluetooth HCI
     driver, just this classification.

Limits worth knowing before trusting a "device found" reading: only one
root-port device is ever enumerated (the loop returns after the first port
that responds), there's no hub support, no re-enumeration if a device is
hot-plugged after boot, and no runtime USB driver beyond this one-shot
boot-time probe — no keyboard/mouse/mass-storage class drivers exist.

## AC'97 audio (`net/audio.mx`)

Unlike USB, audio init is **on-demand**, not automatic at boot — it only
runs when the Settings app's "Initialize AC97" control is used
(`net/settings.mx:532`).

- `ac97_init()` (`:9`-`31`) scans PCI bus 0 for vendor `0x8086`/device
  `0x2415` (Intel 82801AA AC'97), reads its native-audio-mixer (NAM) and
  native-audio-bus-master (NABM) I/O bases from BARs 0 and 1 (config offsets
  `0x10`/`0x14`), enables I/O + bus-master, then does a cold reset via the
  NABM global-control register (offset `0x2c`), resets the codec mixer,
  enables variable-rate audio, and sets the front DAC rate to 48000 Hz.
- `ac97_set_volume(percent)` (`:33`-`41`) converts a 0-100 percent value to
  a 0-31 attenuation step written to the NAM master-volume register (offset
  `0x02`); `0` mutes via that register's mute bit instead.
- `ac97_fill_tone()`/`ac97_test_tone()` (`:43`-`69`) generate one square
  wave into a 1024-stereo-frame buffer (`g_ac97_pcm`) and kick off playback
  through a single-entry buffer descriptor list (`g_ac97_bdl`) on the
  NABM PCM-out DMA engine (offsets `0x10`/`0x15`/`0x1b`). There is no
  capture path (no microphone input) and no interrupt-driven refill — one
  buffer plays once.

## Surfaced in Settings (`net/settings.mx`)

- **Hardware & Devices overview** — `settings_hardware()`
  (`:280`-`298`) shows live-read rows for most of the state above
  (`g_hw_ethernet`, `g_hw_wifi`, `g_usb_ok`/`g_usb_devices`/
  `g_usb_addressed`/`g_usb_vid`/`g_usb_pid`/`g_usb_interface_class`,
  `g_hw_audio`), plus `g_gfx` and `g_disk_ok` for the framebuffer and ATA
  driver. One row is not a live reading: "PS/2 keyboard" always prints the
  literal string `"Ready"` (`net/settings.mx:283`) — there's no keyboard
  presence probe anywhere in the source, so that row is a label, not a
  sensor.
- **Device Controls** — `settings_draw_hardware_controls()`
  (`:426`-`438`), dispatched from `settings_enter()`
  (`:528`-`535`): rescan PCI, toggle/test the PC speaker, initialize AC'97,
  cycle volume in steps of 25 (`(g_audio_volume + 25) % 125`, passed into
  `ac97_set_volume`, whose own `> 100` clamp folds the one case that would
  land on 120 down to 100 before it's stored — so the displayed value cycles
  cleanly through 0/25/50/75/100, never above), and play the AC'97 test
  tone. Wi-Fi and Bluetooth are shown as read-only rows sourced from
  `g_hw_wifi`/`g_hw_bluetooth`.
