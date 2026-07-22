# Vex browser

Vex is MortOS's native, keyboard-first web browser. Its browser shell, state
management, HTTP client, TCP connection handling, HTML-to-text renderer, and
MortFS integration are written in Mort and run inside the kernel. It does not
embed Chromium, WebKit, Gecko, libc, or a host-side proxy.

## What works

- Up to four tabs with page titles, switching, creation, and closing.
- Clickable tabs, new-tab control, navigation buttons, address bar, history,
  bookmarks, and extracted-link rows when a mouse is attached.
- Address entry for `vex://`, `http://`, and bare host names.
- Private, on-device address suggestions from bookmarks and recent history.
- Back, forward, home, reload, scrolling, and find-in-page.
- Persistent bookmarks and six-entry history in the current user's
  `.vex-state` MortFS file.
- Explicit session recovery: Home offers the last non-private HTTP page, but
  never reconnects automatically at startup.
- Private mode, which prevents new visits from entering persistent history.
- Content-Type-aware rendering for HTML and literal plain-text responses.
  Script/style bodies are never executed or displayed, and unsupported binary
  media is rejected instead of being misrendered.
- Link extraction, relative-link resolution, a keyboard link picker, and up to
  three HTTP redirects.
- DHCP lease parsing for address/subnet/router/DNS, DNS A queries, subnet-aware
  ARP routing, TCP handshakes, HTTP/1.0 requests, and HTTP/1.1 chunked-transfer
  decoding over an RTL8139 interface.
- Saving the current rendered document as `vex-page.txt` in the user's home
  directory.
- Local pages for Home, About, History, Bookmarks, Downloads, Settings, and
  Network status.

## Controls

| Key | Action |
| --- | --- |
| `F3` | Open Vex from anywhere in the desktop |
| `/` | Edit the address; Up/Down chooses a local suggestion |
| Left / Right | Back / forward |
| Up / Down | Scroll the page or move through a list |
| `1` / `4` | Home / reload |
| `5` / `6` / `7` / `8` | Bookmarks / history / downloads / settings |
| `9` | Restore the last normal HTTP page from Home |
| `B` | Bookmark the current page |
| `F` | Find text in the current HTTP document |
| `L` | Open the extracted-links panel |
| `D` | Save the rendered document to MortFS |
| `T` / `X` | New tab / close tab |
| `Tab` | Switch to the next tab |
| `P` | Toggle private mode |
| `C` | Clear history while on `vex://settings` |

## Network path

```text
address bar
    -> URL parser
    -> DHCP address, subnet, gateway, and DNS (when no lease exists)
    -> DNS or IPv4 literal
    -> ARP for the host or gateway
    -> TCP handshake and stream collection
    -> HTTP status, redirect, and chunked-body handling
    -> safe HTML-to-text conversion
    -> framebuffer renderer
```

The QEMU test route uses the guest's RTL8139 adapter, not a mocked browser API.
`python test.py browser-ui` starts a host HTTP server and verifies this entire
path in the booted ISO, drives the toolbar through an enumerated USB mouse, and
checks persistence across a reboot.

## Security and current engine boundary

Vex deliberately blocks `https://` instead of silently downgrading it because
MortOS does not yet have a TLS implementation or certificate store. It does
not execute JavaScript, accept cookies, load images or media, apply CSS layout,
submit forms, or provide a general-purpose DOM. HTTP traffic is unencrypted and
must not be used for passwords or other sensitive data.

The TLS foundation is being built as independently testable Mort primitives.
SHA-256, HMAC-SHA256, HKDF-SHA256, X25519, ChaCha20, Poly1305, and their
combined AEAD construction are present and must pass published standard vectors
during every boot. X25519 is checked both against the one-iteration function
vector and Alice/Bob public/shared-secret vectors. TLS 1.3's encoded HKDF labels
and `Derive-Secret` operation are checked against an RFC 8448 handshake trace.
A native ClientHello builder now emits SNI, TLS 1.3 supported versions,
Curve25519 groups/key share, signature algorithms, and the
TLS_CHACHA20_POLY1305_SHA256 cipher suite; the guest-memory regression parses
its record and handshake lengths plus each required extension. This does
**not** enable HTTPS by itself: ServerHello/record processing, authentication,
X.509 parsing, trust anchors, hostname checks, and time validation must also be
complete.

Those are browser-engine projects in their own right, not hidden switches.
The UI reports these limits directly so supported local pages and small HTTP
documents remain useful without giving a false security promise.

## Verification

```bash
python build.py check
python test.py browser-ui
python test.py settings-ui
python test.py usb-hotplug
python test.py smoke
```

The browser regression covers real DHCP configuration, ARP, TCP and HTTP
loading, HTML and literal plain-text rendering, binary-content rejection,
script/style removal, links, redirects, chunked responses, local suggestions,
keyboard and mouse tab controls, private mode, bookmarks, downloads,
explicit normal-session recovery, screenshots, and bookmark persistence after
a full reboot.
