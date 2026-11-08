# The Machine stratum (formerly Settings)

The Settings app is gone, along with accent colours, wallpapers, clock-format
toggles, search and every other idea it carried. What it could actually *do*
moved to the **M** stratum of the Borehole interface
([`docs/borehole-concept.md`](borehole-concept.md)), in `ui/borehole.mx`. Only
the framebuffer path has it; `-kernel` VGA text mode has no interface at all.

Open it with `M` on the surface. Esc climbs back out.

## Readings

`ui_compose_machine()` reads kernel state when the scene is composed:

| Row | Source |
|---|---|
| RAM | the multiboot memory map (`ui_ram_mib`), or a message if the bootloader gave none |
| Heap used | `g_heap_brk - g_heap_base` |
| Uptime | `g_ticks / 100`, redrawn once a second |
| Disk, MortFS | `g_disk_ok`, `g_fs_ok` |
| Display | fixed text: the interface only runs at 1024x768x32 (`ui_init` halts otherwise) |
| Network | `g_our_ip` when `g_net_up`, else whether `g_rtl_ok` found an adapter |
| USB | `g_usb_devices` when `g_usb_ok` |

## Actions

Up/Down picks a row, Enter runs it (`ui_machine_run`), and the scene is then
recomposed so the readings update:

| Row | Calls |
|---|---|
| Connect with DHCP | `net_dhcp()` with `g_net_quiet` set |
| Disconnect adapter | `ethernet_disconnect()` |
| Rescan PCI devices | `hw_scan_pci()` |
| PC speaker on or off | toggles `g_speaker_enabled`, `speaker_stop()` when turning off |
| Test PC speaker | `speaker_test()` (does nothing while the speaker is off) |
| Initialize AC97 | `ac97_init()` then `hw_scan_pci()` |
| Raise audio volume | `ac97_set_volume((g_audio_volume + 25) % 125)` |
| Test AC97 tone | `ac97_test_tone()` |

These run inside the keyboard interrupt, like every shell command, so the
interface freezes for as long as they take (see
[`docs/architecture.md`](architecture.md#a-shell-command-runs-inside-the-keyboard-isr-interrupts-off)).

## The clock

The time at the top right of every screen comes from `ui_clock_text()`, always
24-hour `HH:MM:SS`.

### The RTC reads are unguarded against the chip's own update cycle

`ui_clock_text()` goes through `rtc_reg()`, which does `outb(0x70, reg)` then
`inb(0x71)`. Nothing in the kernel reads CMOS register `0x0A`, where an
MC146818-compatible RTC exposes its Update-In-Progress flag. The safe way to
read such a chip is to poll that flag, or read twice and compare, because it
holds the time registers mid-update for a stretch roughly once a second. This
kernel does neither, so a read landing in that window can come back torn.
`fs_now()` shares the same unguarded `rtc_reg()` calls to stamp file times; see
[`docs/fs-design.md`](fs-design.md)'s `mtime` note.
