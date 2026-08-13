# Settings

A reference for the Settings app (`net/settings.mx`, 623 lines) — the fourth
built-in app (`F4`, or the Settings tile from the `F5` home launcher),
dispatched to `settings_draw()`/`settings_on_key()` when `g_app == 3`
(`kmain.mx:2849`, `kmain.mx:3518`). It only draws in graphics mode —
`settings_draw()` returns immediately `if !g_gfx` (`net/settings.mx:441`) — so
there is no text-mode Settings view. See [`docs/hardware.md`](hardware.md)
for the Hardware & Devices page in more depth (PCI scan, USB, AC'97); this
doc covers the rest of the app: the sidebar, navigation state machine, the
five interactive sub-pages, and search.

As the file's own header comment explains (`net/settings.mx:1-5`), it lives
under `net/` only because `build.py`'s glue loop (`build.py:113-121`) pulls
every `net/*.mx` file into the kernel, not because it's part of the
networking stack.

## The 13 sidebar sections

The default view (`g_settings_view == 0`) is a two-pane layout: a sidebar of
13 sections on the left, and the selected section's content on the right,
drawn by `settings_draw_sidebar()` (`net/settings.mx:349`-`371`). Only 8 rows
are visible at once; the sidebar scrolls (`g_settings_scroll`) as the
selection moves past the edges, with `^ more`/`v more` hints at
`net/settings.mx:352`-`353`.

| # | Section | Draw function | Kind |
|---|---------|---------------|------|
| 0 | Overview | `settings_overview` (`:177`) | read-only |
| 1 | Personalization | `settings_personalization_preview` (`:194`) | opens sub-page |
| 2 | Display | `settings_display` (`:205`) | read-only |
| 3 | Network | `settings_network` (`:238`) | opens sub-page |
| 4 | Apps | `settings_apps` (`:248`) | read-only |
| 5 | Time & language | `settings_clock_preview` (`:219`) | opens sub-page |
| 6 | Accessibility | `settings_accessibility` (`:311`) | opens sub-page |
| 7 | Privacy & security | `settings_privacy` (`:258`) | read-only |
| 8 | Power | `settings_power` (`:269`) | read-only (F12 does the real work) |
| 9 | Storage | `settings_storage` (`:227`) | read-only |
| 10 | Hardware | `settings_hardware` (`:280`) | opens sub-page |
| 11 | Update & About | `settings_update` (`:300`) | read-only |
| 12 | Diagnostics | `settings_diagnostics` (`:319`) | read-only |

Read-only sections only display kernel state — e.g. Display reads
`g_fb_w`/`g_fb_h`/`g_fb_pitch`, Storage reads `g_disk_ok`/`g_fs_ok` and calls
`settings_file_count()` (`:168`-`175`, which scans all 64 file-table entries
for `type == 1`), Diagnostics reads `g_ticks` and the heap bounds
(`g_heap_base`/`g_heap_brk`/`g_heap_end`). None of these sections take
`Enter` — pressing it on the sidebar only does something for the five
sections in the "opens sub-page" column above (`settings_enter()`,
`net/settings.mx:498`-`506`).

Two rows worth calling out as not-quite-live-data: `settings_hardware()`
displays the PS/2 keyboard row as a hardcoded literal `"Ready"`
(`:283`) rather than probing for a device — see
[`docs/hardware.md`](hardware.md) for that and the rest of the Hardware page.
Power's four actions (Lock/Sleep/Restart/Shut down) are described but not
triggerable from this page at all; the real controls are the global `F12`
power menu or the matching shell commands (`net/settings.mx:276`,
`docs/shell.md`).

## Navigation state machine

Four kernel globals drive the whole app:

- `g_settings_view` (`:11`) — which screen is showing: `0` sidebar, `1`
  personalization, `2` clock, `3` accessibility, `4` hardware controls, `5`
  network controls. (The source comment on this line only lists the first
  three values — a stale leftover from before views 3-5 were added.)
- `g_settings_section` (`:13`) — which of the 13 sidebar rows is selected,
  when `g_settings_view == 0`.
- `g_settings_sel` (`:12`) — which option row is selected, within whichever
  sub-page is open.
- `g_settings_scroll` (`:24`) — the sidebar's scroll offset (see above).

`settings_up()`/`settings_down()` (`:452`-`476`) branch on `g_settings_view`:
on the sidebar they move `g_settings_section` (clamped to 0-12) and adjust
`g_settings_scroll`; on a sub-page they move `g_settings_sel`, clamped to
that page's option count (`settings_down()`'s `last` local is `1` for every
sub-page except hardware controls, which has 6 options and sets `last = 5`,
`:473`-`474`). `settings_back()` (`:593`-`595`) returns to the sidebar from
any sub-page. `settings_enter()` (`:498`-`545`) is the one function that
reads both `g_settings_view` and the current selection to decide what to do —
see the per-page tables below.

Key handling (`settings_on_key()`, `:597`-`623`) follows the same
extended-scancode pattern documented in
[`docs/shell.md`](shell.md#line-editing): `0xE0` (224) sets
`g_settings_ext`, and the *next* scancode is then read as an arrow key
(`72` Up, `80` Down, `75` Left — Left triggers `settings_back()`). Plain
`Enter` is scancode `28`, `Esc`/Backspace-as-back is `1`.

## Personalization (`g_settings_view == 1`)

`settings_draw_personalization()` (`:389`-`396`). Two rows, each just a
counter that `Enter` advances:

| Row | Enter action | Cycle |
|-----|---------------|-------|
| Accent color | `settings_apply_accent()` (`:478`-`487`) | 6 colors, named by `settings_accent_name()` (`:373`-`380`): Ocean, Violet, Forest, Coral, Amber, Ice |
| Wallpaper | `settings_apply_wallpaper()` (`:489`-`496`) | 4 gradients, named by `settings_wall_name()` (`:382`-`387`): Midnight, Aurora, Sunset, Graphite |

Both redraw the whole desktop (`draw_desktop()`) immediately, so the change
is visible outside the Settings window too — the accent color, for example,
also colors the selected sidebar row (`settings_sidebar_row`, `:32`-`41`).

## Clock (`g_settings_view == 2`)

`settings_draw_clock()` (`:398`-`404`). Two on/off toggles, both applied
immediately in `settings_enter()` (`:512`-`517`):

- `g_clock_24h` — 24-hour vs. 12-hour time.
- `g_clock_seconds` — whether the top-bar clock shows seconds.

Toggling either calls `draw_topbar()` right away, so the top-right clock
updates without leaving Settings.

## Accessibility (`g_settings_view == 3`)

`settings_draw_accessibility()` (`:406`-`412`). Two toggles
(`settings_enter()`, `:518`-`527`):

- `g_settings_high_contrast` — when turned on, forces the accent to
  `0xffc928` and the wallpaper to a black/near-black gradient, overriding
  whatever Personalization had set; turning it back off restores the
  default ocean accent/wallpaper *and* resets `g_settings_accent`/
  `g_settings_wall` to `0`, so a custom Personalization choice does not
  survive a high-contrast round-trip.
- `g_settings_show_hints` — whether the bottom-of-screen key-hint line
  (`"Up/Down: browse   Enter: open   /: search"`, etc.) is drawn at all.
  This is the one toggle that hides its own hint line once turned off
  (`net/settings.mx:370`, `:411`).

## Hardware & devices controls (`g_settings_view == 4`)

Reached via the Hardware sidebar section. `settings_draw_hardware_controls()`
(`:426`-`438`) and its six `Enter` actions (`:528`-`536`) — PCI rescan,
speaker toggle/test, AC'97 init, volume cycling, and a PCM test tone — are
covered in full in [`docs/hardware.md`](hardware.md#surfaced-in-settings-netsettingsmx),
including the volume-cycling clamp behavior. Not repeated here.

## Ethernet (`g_settings_view == 5`)

`settings_draw_network_controls()` (`:414`-`424`), reached from the Network
sidebar section. Two actions (`settings_enter()`, `:537`-`544`):

- **Connect with DHCP** — shows a "connecting..." screen, then calls
  `net_dhcp()` with `g_net_quiet` set so the DHCP handshake doesn't spam its
  usual console output into the Settings window.
- **Disconnect adapter** — calls `ethernet_disconnect()`
  (`net/hardware.mx`, see [`docs/hardware.md`](hardware.md)).

Below the two actions it shows live driver/lease/IP status the same way
the read-only Network overview section does (`settings_draw_ip()`,
`:158`-`166`, reading `g_our_ip` byte-by-byte).

## Search

Pressing `/` (scancode `53`) from the sidebar opens a search overlay
(`settings_draw_search()`, `:130`-`156`) instead of navigating sections.
It's a fixed, hand-written index — 16 keyword strings, each tagged with the
sidebar section it should jump to — filtered live as you type by
`settings_matches()` (`:78`-`96`), a case-insensitive substring scan (via
`settings_lower()`, `:72`-`75`) with no fuzzy matching. Up to 8 matches are
shown (`settings_search_candidate()`'s `shown < 8` guard, `:123`).

Typing is handled by `settings_search_key()` (`:570`-`591`): printable ASCII
32-126 appends to a 24-byte query buffer (`g_settings_query`, capped at 22
characters so a NUL terminator always fits), Backspace (`14`) removes the
last character, and Enter (`28`) calls `settings_open_search_result()`
(`:547`-`568`), which re-walks the same keyword list to find the `n`-th
match (`g_settings_result_sel`) and jump to its section — leaving
`g_settings_search` and returning to the sidebar. `Esc` (`1`) exits the
search overlay without picking anything.

Not every keyword maps to a *unique* section: "24 hour time clock language"
and "show seconds" both point at section 5 (Clock), and "accent color
theme"/"wallpaper background" both point at section 1 (Personalization) —
searching either term for a section lands on the same page, just via a
different matched phrase.
