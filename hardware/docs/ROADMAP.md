# Roadmap

## USB host stack

- Replace fixed boot delays with monotonic deadlines and decoded TD errors.
- Support multiple queue heads and reusable control-transfer construction.
- Extend one-level hub traversal to nested/multi-TT hubs and replace full-bus hot-plug rescans with incremental removal and address reuse.
- Build interrupt and isochronous transfer APIs.
- Add typematic keyboard repeat, lock-key LEDs, wheel/extra-button handling, and a general HID report-descriptor parser.
- Add USB mass-storage transport after a block-device API exists.

## Bluetooth

- Match Wireless Controller interface class `e0/01/01`.
- Verify the USB HCI Reset/Command Complete path on identified controllers.
- Add bulk ACL and isochronous SCO transfers, local feature discovery, scan, and connection management.
- Add L2CAP and an initial pairing/security model.
- Select profiles explicitly rather than claiming generic Bluetooth support.

## Wi-Fi

- Choose one documented chipset or emulator target before writing a driver.
- Implement device reset, firmware-loading policy if required, RX/TX rings, and interrupts.
- Add 802.11 management, authentication, association, and WPA2/WPA3 through a clearly scoped security design.
- Keep “controller detected” separate from “driver ready” and “network connected.”

## PCI and DMA

- Traverse PCI bridges and buses beyond bus 0.
- Parse BAR sizes and capabilities safely.
- Add MSI/MSI-X behind a host interrupt API.
- Introduce a DMA allocator, physical-address translation, pinning, and memory barriers.
- Define support for 64-bit and IOMMU-enabled kernels.

## Existing devices

- RTL8139: interrupt-driven RX/TX, descriptor completion, link state, statistics, and recovery.
- AC'97: completion interrupts, streaming buffers, underrun recovery, capture, and codec capability probing.
- PC speaker: timer-backed non-blocking tones.

## Quality

- Expand emulator-driven hardware assertions beyond the current root/hub USB hot-plug suite.
- Register-level traces for failure diagnosis.
- Fuzz descriptor parsers with host-side tests.
- Hardware support matrix generated from reproducible reports.
- Versioned host-kernel adapter API.
