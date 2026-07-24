# Canonical VexFS image

VexFS is the read-only application image that carries the actual canonical
Vex Electron tree into MortOS. It is not a browser reimplementation and does
not contain a separately redrawn interface.

The x86-64 build requires a clean Vex checkout at commit
`1b10ec57fa9ebf77ed86c2d5d28f72aad7c1007a`. By default it is found beside
MortOS; `MORTOS_VEX_SOURCE` can select another checkout. The build packages:

- `package.json`
- every file under `src/`
- `assets/icon.svg` and `assets/icon.ico`
- every file under `assets/theme-previews/` when that directory exists

Paths are normalized below `/app/vex/` and sorted byte-for-byte. Each archive
entry stores its path, payload length, flags, and SHA-256 digest. `check64`
parses the complete image again, rejects malformed bounds, duplicate or
unsorted paths, digest mismatches, trailing data, a wrong package identity, or
missing `src/main.js` and renderer entry files.

## Binary layout

The 16-byte archive header contains:

| Offset | Size | Meaning |
| --- | --- | --- |
| 0 | 8 | ASCII magic `MORTVEX1` |
| 8 | 4 | little-endian format version (`1`) |
| 12 | 4 | entry count |

Each 8-byte-aligned entry contains:

| Offset | Size | Meaning |
| --- | --- | --- |
| 0 | 2 | UTF-8 path length |
| 2 | 2 | flags (currently zero) |
| 4 | 4 | payload length |
| 8 | 32 | SHA-256 of the payload |
| 40 | variable | path bytes, then payload bytes |

At boot, Mort validates the archive structure before exposing it. Ring-3
programs use `openat`, `read`, `pread64`, `lseek`, `fstat`, `newfstatat`,
`getdents64`, `poll`, and `close` through ordinary per-process descriptors.
`getcwd`/`chdir`, `AT_FDCWD`, directory-relative lookup, repeated separators,
and `.`/`..` normalization provide the path semantics needed by module
resolution.
Private file-backed `mmap` allocates independent user frames, copies the
requested immutable bytes, and keeps normal W^X enforcement.
Directories are inferred from the sorted file paths, carry read-only directory
metadata, and enumerate each immediate child once. No duplicate directory
records are stored in the image. The current image is immutable; writable
profiles, caches, downloads, and session state will live on the persistent
64-bit filesystem layer rather than modifying canonical app files.
