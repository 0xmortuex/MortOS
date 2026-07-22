# Settings control center

Press `F4` to open MortOS Settings. The control center is written in Mort and
uses live kernel and driver state; unsupported hardware is reported honestly
instead of being represented by decorative switches.

## Pages and controls

- Overview: OS, CPU, memory, network, storage, and session summary.
- Personalization: live accent colors and desktop wallpapers.
- Display: framebuffer mode, resolution, pitch, and color depth.
- Clock: 12/24-hour mode and seconds visibility.
- Storage: MortFS status, file-table use, disk sectors, and Files shortcut.
- Network: RTL8139 state, MAC/IPv4 information, DHCP connect/disconnect, and
  the router-provided gateway and DNS server.
- Apps: launch Terminal, Files, and the native Vex browser.
- Privacy & Security: local-first security state and session locking.
- Power: lock, sleep, restart, shutdown, and the protected power menu.
- Hardware & Devices: PCI rescan, USB inventory/rescan, PC speaker controls,
  AC97 initialization, volume, and PCM testing.
- Accessibility: high contrast and navigation hints.
- Diagnostics: live uptime, timer, interrupt, PCI, USB, network, and filesystem
  health with explicit rescans.
- Update & About: build identity plus save/reset preference maintenance.

Typing while the sidebar is active opens Settings search. Results route to the
specific page or actionable control, and `Esc` clears the query before leaving
Settings. Arrow keys move selection; `Enter` opens or activates it.

## Persistence

User preferences are stored in `.mort-settings` in the current MortFS home:

- accent color and wallpaper;
- 12/24-hour clock and seconds visibility;
- high-contrast mode and navigation hints.

The control center validates the file before loading it. If the filesystem or
home directory is not writable, changes remain useful for the current session
and the UI reports the session-only state.

## Hardware boundary

Ethernet is functional through the RTL8139 driver. USB controllers and devices
are discovered automatically and can be rescanned. The hardware pages expose
real PCI, UHCI/OHCI/EHCI/xHCI inventory and descriptor data when available.

Wi-Fi and Bluetooth require both compatible physical hardware and a driver for
that chipset or USB device; a dongle is only one possible way to supply such
hardware. MortOS does not pretend those radios exist when no supported adapter
is detected. See the MortHardware repository for the reusable driver and
hardware-support work shared with MortOS.

## Verification

`python test.py settings-ui` boots the graphical ISO and checks page routing,
search, live controls, persistence, session-only fallback behavior, and the
Settings screenshot. Hardware discovery has its own `python test.py
usb-hotplug` regression.
