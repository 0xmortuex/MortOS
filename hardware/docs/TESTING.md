# Testing

## Verified environment

The initial drivers were verified on 22 July 2026 with QEMU 11.0.50 on an x86 freestanding MortOS build.

| Test | QEMU device option | Expected observation |
| --- | --- | --- |
| RTL8139 | `-device rtl8139` | Driver initializes, reads MAC, obtains DHCP connectivity in MortOS |
| AC'97 | `-device AC97` | Controller reports ready; PCM test submission succeeds |
| UHCI + HID | `-usb -device usb-tablet` | One USB device, descriptor ready, VID 1575, PID 1, interface class 3 |
| UHCI keyboard | `-usb -device usb-kbd` | Device configured, class/protocol `3/1`; keyboard navigates Settings and enters `echo usb-ok` |
| UHCI mouse | `-usb -device usb-mouse` | Device configured as HID boot mouse; relative movement draws a cursor and a left click opens Settings |
| UHCI hub topology | `-usb -device usb-kbd -device usb-mouse` | Three devices (keyboard, class-9 hub, downstream mouse); keyboard and mouse work simultaneously; Settings lists all three addresses and descriptor identities |
| UHCI root hot-plug | QEMU monitor `device_del` / `device_add usb-kbd` | Device table removes/re-adds the keyboard automatically and restores its HID binding |
| UHCI hub hot-plug | QEMU monitor `device_del` / `device_add usb-mouse` | Downstream mouse disappears/re-enumerates automatically and its HID binding returns |

Bluetooth USB HCI currently has no standard QEMU device target. The class parser, control-transfer builder, Reset opcode/event matching, Mort compilation, and absent-device boot path are tested; successful controller initialization must not be claimed until a real or passthrough controller returns status zero.

The VID/PID values above are decimal values shown by MortOS Settings. In hexadecimal they are `0627:0001`, QEMU's emulated tablet identity.

## Recommended test progression

1. Boot in QEMU without optional devices and confirm every initializer fails cleanly.
2. Add exactly one target controller and verify discovery.
3. Verify register reset and controller-ready state.
4. Exercise DMA while capturing emulator logs or packets.
5. Run repeated cold boots and guest resets.
6. Add malformed, absent, slow, and unsupported-device cases.
7. Only then test a specifically identified physical machine.

## MortOS regression checks

The MortOS tree includes a smoke suite:

```powershell
python build.py build
python test.py smoke
python test.py usb-hotplug
python build.py iso
```

The repository includes `tests/platform_stubs.mx`, a Mort-only compile contract that supplies MortOS-owned state referenced by one lifecycle helper. Freestanding Mort supplies the typed x86 port-I/O primitives. The stub exists to expose missing host dependencies during compiler checks and is not part of a bootable kernel.

The USB verification used an ISO boot to obtain the framebuffer desktop, opened Settings → Hardware using only QEMU's USB keyboard, confirmed the live configuration fields, opened Terminal, and successfully entered `echo usb-ok`. The general smoke test covers the boot banner, help, echo, and uptime. The `usb-hotplug` suite uses QEMU monitor commands plus ELF-symbol state reads for 13 machine-readable root-port and hub-port assertions.

## Reporting a result

Include:

- CPU/platform or QEMU version.
- Exact device option or PCI/USB vendor and product IDs.
- Whether paging/IOMMU is enabled.
- Controller BAR values and relevant status bits.
- Reproduction commands.
- Whether the failure occurs at discovery, reset, transfer submission, or completion.
