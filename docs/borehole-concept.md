# Borehole: the MORT OS interface

Written before the code. The previous interface (launcher tiles, wallpaper, top bar, framed
windows, F-key app switching) is gone; none of its ideas carry over.

## The idea

MORT OS is not a desktop. It is a **geological cross-section of a drill site**. The whole
screen, edge to edge, is one vertical slice of ground with a drill shaft running down it.
There are no windows, panels or icons. There is only *depth*, and the only way to move is
up or down through rock.

Everything is a layer. The system has four strata, and they spell the OS's name from the
surface down:

| Stratum | Rock | Holds |
|---|---|---|
| **M** Machine | sandstone | what the machine is made of: real readings and hardware actions |
| **O** Objects | limestone | MortFS: directories are deeper rock, files are beds |
| **R** Run | shale | the shell, in a gallery cut out of the rock |
| **T** Terminate | granite | lock, sleep, restart, shut down |

The idea is self-similar: a directory path is literally a stack of strata (`/home/mortuex`
is three layers you have dug through), a file is a thin bed whose thickness grows with the
log of its size, and opening a file pulls a **core sample** out of the bed.

## Start screen

Dusk sky over a ragged ridge, with a drilling derrick standing on the surface. The sky's
colour and the sun or moon position come from the real-time clock. Below it four full-width
strata, each with its own lithology pattern, big name, one-line caption, a key cap, and one
huge letter of **M O R T** carved into the rock at the right edge. The drill bit sits in the
shaft at the selected stratum. It starts on **R**, so Enter gives a shell immediately.

## Layout

- Full bleed 1024x768, nothing floats and nothing has a frame.
- Left edge: a depth ruler (x 0-40) and the shaft (x 48-60), present on every screen.
- Strata are stacked by a single accordion: the open stratum takes all the height and the
  closed ones collapse to 26 px slivers that keep their label, position and order. You always
  see where you are in the column.

## Navigation

Vertical only. There is no app switcher, because there is nothing to switch between.

| Key | Effect |
|---|---|
| Up / Down | move the drill between strata, beds or actions |
| Enter | bore in: open the stratum, directory or file |
| Esc | climb back up one level |
| M O R T (on the surface) | drill straight to that stratum |

In a file: Up/Down scroll a line, PgUp/PgDn or Space scroll a screen.

## Reaching each capability

- **Shell**: `R`, or Enter at boot. Esc climbs out, and the shell keeps its text while you are
  away. Typing is untouched: every printable key goes to the shell.
- **Browse MortFS**: `O`, then Up/Down, Enter to descend, Esc to ascend. At the root, Esc
  returns to the surface.
- **View a file**: Enter on a bed. The core sample shows the contents with scrolling.
- **Machine**: `M`. Live readings plus actions that used to live in Settings: DHCP, disconnect,
  PCI rescan, speaker toggle and test, AC97 init, volume, test tone.
- **Power**: `T`, or the shell commands `power`, `lock`, `sleep`, `restart`, `shutdown`.

## Typography

Only the kernel's 8x16 bitmap font exists, so it is used in three deliberate registers:

- **Carved**: huge letters (x8), enlarged with an EPX pixel-doubling pass so diagonals stay
  smooth, cut into the rock as lit recesses.
- **Stencil**: stratum names at x4, same EPX pass, with a hard one-pixel shadow.
- **Field notes**: x1 text at 10 px advance and 20 px line pitch in the shell and in cores. The
  extra leading makes the 80x25 console fill 800x500 instead of looking like a VGA dump.

## Palette

Warm mineral colours. There is no blue and no cyan anywhere below the sky.

| Role | Colour |
|---|---|
| Field notes, captions | bone `E8DCC4` |
| Bright text | `F5EBD7` |
| The drill, selection, the single accent | vermilion `FF4B1F` |
| Shaft | `0C0908` |
| Gallery (shell background) | `14100C` |
| Core sample | pale bone slab with `2B1D12` ink |
| Sandstone / limestone / shale / granite | `7A5228` / `6A5B4A` / `4A2B20` / `262020` |

## Motion

Timer-driven at 100 Hz, always on real state:

- **Drilling reveal**: a scene is composed off-screen, then revealed row by row behind the
  drill bit, downward when boring in and upward when climbing out.
- **Bit travel**: changing selection slides the bit along the shaft instead of jumping.
- **Spark**: the bit's tip flickers while idle.
- **Sky**: the sun or moon and the clock follow the real-time clock.

A keypress during a reveal finishes it immediately, so the interface never makes you wait.

## Text-mode path

Without a framebuffer (`-kernel`, VGA text mode) none of this exists. The shell runs straight
on VGA as before. The console keeps one small seam (`put_cell_at`, `move_cursor`,
`clear_screen`, `scroll_up`), which is all the interface touches.
