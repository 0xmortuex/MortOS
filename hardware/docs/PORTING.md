# Porting guide

## 1. Provide x86 I/O primitives

The code expects these functions with the obvious widths:

```mort
fn inb(port: u16) -> u8;
fn inw(port: u16) -> u16;
fn inl(port: u16) -> u32;
fn outb(port: u16, value: u8);
fn outw(port: u16, value: u16);
fn outl(port: u16, value: u32);
```

They must be privileged x86 `in`/`out` operations and must not be reordered across controller programming sequences.

## 2. Decide who owns PCI access

`rtl8139.mx` includes PCI configuration mechanism #1 helpers using `0xCF8/0xCFC`. If your kernel already has a PCI subsystem, remove those helpers and route `pci_read32`/`pci_write32` to the host implementation.

The present scan covers bus 0 only. A kernel targeting physical machines should enumerate host bridges, PCI-to-PCI bridges, secondary buses, and functions according to header type.

## 3. Fix the DMA address model

MortOS currently uses identity-addressed memory with paging disabled. The drivers therefore pass pointers directly to devices:

```mort
outl(register, &buffer as u32);
```

Do not retain this in a higher-half or virtual-memory kernel. Allocate pinned DMA memory, translate it to a device-visible physical address, enforce each controller's alignment and address-width rules, and add the platform's required cache maintenance or memory barriers.

Important alignments in the current source:

- UHCI frame list: 4096 bytes.
- UHCI queue heads and transfer descriptors: 16 bytes.
- AC'97 buffer descriptor list: controller-visible and stable during playback.
- RTL8139 RX/TX buffers: controller-visible and stable while enabled.

## 4. Choose initialization context

Call `usb_boot_init()` before enabling interrupts in the current implementation. It resets the UHCI controller, resets a root port, and uses polling delays. Do not call it from a keyboard/UI interrupt handler.

RTL8139 and AC'97 initialization also perform controller resets and must run in a context where port access and bounded waits are safe.

## 5. Separate drivers from UI state

Treat the exported globals as a temporary diagnostics ABI. Production integration should expose immutable snapshots or driver query functions. Settings should never directly reset hardware.

## 6. Remove MortOS-only glue

The exact `hardware.mx` snapshot includes `ethernet_disconnect()`, which references MortOS globals from the RTL8139/network stack. A different kernel can omit that function or replace it with its own lifecycle operation.

The complete MortOS network protocol stack lives in the [MortOS repository](https://github.com/0xmortuex/MortOS/tree/settings/net). This repository carries the hardware-facing RTL8139 layer and its immediate frame helpers.

## 7. Add real timeouts and errors

The early drivers use bounded spin delays. A port should replace these with monotonic deadlines, decode controller error bits, log failures, recover stalled hardware, and avoid assuming QEMU timing.

## 8. Route HID keyboard events

Call `usb_hid_poll_scancode()` from a periodic tick after `usb_boot_init()` has configured a HID boot keyboard. A non-zero return value is an XT set-1 make code. Read `g_usb_hid_shift` and `g_usb_hid_extended` before dispatching it. The polling function only reports newly pressed keys; key releases, typematic repeat, and LED output remain host work.

For HID boot mice, call `usb_hid_poll_mouse()`. A successful poll updates signed `g_usb_mouse_dx`/`g_usb_mouse_dy` and the standard three low button bits in `g_usb_mouse_buttons`. See `examples/framebuffer_mouse.mx` for cursor rendering; hide the cursor before repainting any underlying UI region, then show it again afterward.

The current UHCI table supports eight addressed devices and one level of class-9 hubs. Increase the fixed arrays only after checking Mort compiler output size and UHCI schedule-memory requirements. Production ports should add address reuse and explicit detach handling before hot-plug is enabled.
