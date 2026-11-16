# MortHardware

Reusable bare-metal hardware drivers extracted from [MortOS](https://github.com/0xmortuex/MortOS), a hobby operating-system kernel written in the Mort language.

This repository records the hardware-support work built for MortOS and provides the source, integration contract, test recipes, and design notes needed to reuse it in another Mort kernel. It is software that controls hardware; it is not a physical board, chipset, or dongle.

**All driver and example implementation code in this repository is written in Mort (`.mx`).** Markdown files are documentation only; there is no C, C++, or Rust hardware implementation hidden behind the Mort API.

## What works today

| Area | Current capability | Verified with | Status |
| --- | --- | --- | --- |
| PCI | Configuration mechanism #1, bus 0 scan, all 32 slots and 8 functions | QEMU PCI topology | Working |
| Ethernet | RTL8139 discovery, reset, MAC read, DMA TX, RX ring, frame transmit/receive | QEMU `rtl8139` | Working |
| Audio | Intel 82801AA AC'97 discovery, mixer volume, 48 kHz PCM-out DMA, test tone | QEMU `AC97` | Working |
| USB | UHCI discovery/reset, per-device addressing, descriptors, hubs, downstream ports, automatic hot-plug rescans, and configuration | QEMU root and hub detach/reattach tests | Working foundation |
| USB HID | Boot keyboard and mouse reports, interrupt-IN polling, key translation, signed pointer movement, and three buttons | QEMU `usb-kbd`, `usb-mouse` | Working |
| USB classes | Interface class/subclass/protocol and interrupt/bulk endpoint detection | USB HID devices | Working |
| PC speaker | PIT channel 2 tone generation and gate control | Legacy PC speaker interface | Working |
| Wi-Fi | PCI capability detection only | PCI class scan | Driver not implemented |
| Bluetooth | USB class/endpoint discovery, HCI command transport, Reset command, Command Complete validation | Mort compiler + no-device regressions | Needs controller verification |

“Working foundation” for USB means the host controller can enumerate both root ports, configure hubs and downstream devices, recover automatically from tested root/hub attach and removal events, and operate a boot keyboard and mouse simultaneously. It does not yet mean nested hubs, arbitrary HID report descriptors, mass storage, isochronous transfers, or Bluetooth traffic are complete.

## Repository layout

```text
src/
  ac97.mx       Intel 82801AA AC'97 PCM driver
  endian.mx     byte-order helpers used by Ethernet
  ethernet.mx   Ethernet frame helpers
  hardware.mx   PCI capability scan and PC speaker
  rtl8139.mx    Realtek RTL8139 Ethernet driver
  uhci.mx       USB 1.1 UHCI enumeration foundation
docs/
  ARCHITECTURE.md
  MORTOS-BUILD-LOG.md
  PORTING.md
  ROADMAP.md
  TESTING.md
examples/
  boot.mx
```

## Kernel contract

The drivers intentionally rely on a very small host-kernel surface:

- `inb`, `inw`, `inl` and `outb`, `outw`, `outl` for x86 port I/O.
- PCI configuration-space access through ports `0xCF8` and `0xCFC`.
- Storage whose physical address is visible to 32-bit DMA hardware.
- A short early-boot delay mechanism.
- Initialization before interrupts for the current polling UHCI path.

MortOS currently runs with paging off, so a Mort pointer is also the physical DMA address. A kernel with paging enabled must replace every direct `&buffer as u32` DMA address with a physical-address translation and must keep the buffers pinned.

Read [the porting guide](docs/PORTING.md) before using the code outside MortOS.

## Minimal integration

Compile the required `.mx` files into the kernel's Mort translation unit, provide the platform functions above, then initialize during boot:

```mort
hw_scan_pci();
rtl_init();       // optional Ethernet
ac97_init();      // optional audio
usb_boot_init();  // before enabling interrupts in the current implementation
```

For a configured HID boot keyboard, call `usb_hid_poll_scancode()` from a periodic kernel tick and route each non-zero set-1 make code to the host input dispatcher. The companion globals `g_usb_hid_shift` and `g_usb_hid_extended` describe modifiers and extended navigation keys. For a boot mouse, call `usb_hid_poll_mouse()` and consume `g_usb_mouse_dx`, `g_usb_mouse_dy`, and `g_usb_mouse_buttons`. MortOS polls at 100 Hz.

`examples/framebuffer_mouse.mx` is a Mort-only 32-bpp cursor adapter with background save/restore. MortOS extends it with launcher-tile and Settings-section clicks.

See [examples/boot.mx](examples/boot.mx) for a fuller example and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for ownership and data flow.

## MortOS integration

The active MortOS implementation is on the [`settings` branch](https://github.com/0xmortuex/MortOS/tree/settings). Its Settings app exposes live status for Ethernet, wireless capability, AC'97, storage, and other kernel capabilities. A dedicated USB Devices page lists up to six addressed devices with address, VID/PID, interface class/protocol, and configuration state.

The exact implementation history and commit IDs are recorded in [docs/MORTOS-BUILD-LOG.md](docs/MORTOS-BUILD-LOG.md).

## Safety and scope

This is experimental kernel code. It can program PCI command registers, perform DMA, reset controllers, and drive I/O ports. Run it in QEMU first. Real hardware needs chipset-specific testing, correct DMA mapping, interrupt routing, cache coherency, and robust timeout/error handling.

## Contributing

Useful next contributions include nested/multi-TT hub support, incremental device removal, arbitrary HID report parsing, USB mass storage, Bluetooth controller validation and higher protocols, a documented Wi-Fi chipset target, interrupt-driven operation, PCI bus/bridge traversal, and physical-hardware test reports. Please include the device vendor/product ID, emulator or machine model, logs, and reproduction steps.

## License

MIT © 2026 Fadi Raad (0xmortuex). See [LICENSE](LICENSE).
