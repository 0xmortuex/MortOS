# Source notes

These files are extracted from the tested MortOS `settings` branch and remain close to the integrated code so register-level behavior is auditable.

Suggested composition order for a single Mort translation unit:

1. `endian.mx`
2. `ethernet.mx`
3. `rtl8139.mx`
4. `hardware.mx`
5. `ac97.mx`
6. `uhci.mx`

MortOS's compiler resolves functions across its combined translation unit, so the exact textual order is not significant there.

Known integration detail: `hardware.mx` contains the MortOS-specific `ethernet_disconnect()` lifecycle helper. Omit or adapt that function if your host does not expose `g_net_up`, `g_rtl_ok`, and `g_rtl_io`.

The USB implementation updates `g_hw_bluetooth` when it finds a Bluetooth-class interface; include `hardware.mx` or provide that boolean in the host.

`uhci.mx` also exposes `usb_hid_poll_scancode()` for HID boot keyboards. It returns XT set-1 make codes so a small host adapter can share an existing PS/2-style input dispatcher. All controller logic and HID translation remain Mort code.

HID boot mice use `usb_hid_poll_mouse()`, which publishes signed relative movement and button bits. A Mort framebuffer adapter is provided in `examples/framebuffer_mouse.mx`.
