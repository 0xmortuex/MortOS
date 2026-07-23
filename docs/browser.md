# Legacy framebuffer browser

This page documents the legacy framebuffer web compatibility prototype. It is
not the canonical [`0xmortuex/Vex`](https://github.com/0xmortuex/Vex) browser,
because it does not execute Vex's Electron/Chromium application source. See
[the canonical Vex port plan](vex-native-port.md) and
[the historical prototype mapping](vex-compatibility-prototype.md).

## What works

- Canonical Vex chrome with its gold diamond, vertical tab sidebar, workspace
  header, library navigation, and new-tab surface.
- Personal, Work, School, and Dev workspaces with isolated four-tab stacks;
  the active workspace persists in the user's `.vex-state` file.
- A canonical `Ctrl+K` command bar that opens local Vex pages, creates tabs,
  toggles private mode, switches workspaces, or treats non-command input as an
  address.
- Up to four tabs with page titles, switching, creation, and closing.
- Clickable tabs, new-tab control, navigation buttons, address bar, history,
  bookmarks, and extracted-link rows when a mouse is attached.
- Address entry for `vex://`, `http://`, `https://`, and bare host names.
- Private, on-device address suggestions from bookmarks and recent history.
- Back, forward, home, reload, scrolling, and find-in-page.
- Persistent bookmarks and six-entry history in the current user's
  `.vex-state` MortFS file.
- Case-insensitive search directly on the History page with `F`; matching stays
  entirely on-device and selects the local entry for reopening.
- Explicit session recovery: Home offers the last non-private HTTP page, but
  never reconnects automatically at startup.
- Four named workspace snapshots persisted in `.vex-sessions`. Each restores
  up to four tab URLs, titles, and the active tab through `session save NAME`,
  `session open NAME`, and `session delete NAME` in the command bar.
- Automatic `.vex-workspaces` recovery for every workspace's tab URLs, titles,
  tab count, and active tab, plus a four-item recently closed stack. Normal
  changes sync immediately; private navigation is excluded.
- Persistent organization metadata for every live workspace tab: pin/unpin,
  three bounded color groups (`Focus`, `Research`, and `Later`), duplication,
  and left/right reordering. Pinned tabs must be unpinned before closing, and a
  duplicate inherits its source group without inheriting its pin.
- A native Vex Library persisted in `.vex-library`: up to eight short
  Markdown-style notes and eight HTTP/HTTPS Read Later entries. `note TEXT`
  saves a note, `read later` queues the active page, and queued pages reopen
  from the local Library page. Notes can be pinned, unpinned, deleted, and
  exported together as `vex-notes.md`; Read Later entries can be removed
  individually. Private pages cannot change or export the store.
- A distraction-reduced reading layout toggled with `M`, plus eight per-origin
  profiles in `.vex-sites` that remember reading mode and whether extracted
  links are exposed. Private mode may use reading mode transiently but never
  writes or changes site profiles.
- Private mode snapshots the full normal workspace/tab state on entry and
  restores it on exit. Temporary URLs, titles, tab creation/closing, and
  workspace changes therefore disappear instead of leaking into a later
  journal save. A verified certificate may remain available for explicit
  approval immediately after exit; the normal session is restored afterward.
- Content-Type-aware rendering for HTML and literal plain-text responses.
  Script/style bodies are never executed or displayed. Other response types
  are staged as bounded binary downloads instead of being misrendered.
- Link extraction, relative-link resolution, a keyboard link picker, and up to
  three HTTP redirects.
- DHCP lease parsing for address/subnet/router/DNS, DNS A queries, subnet-aware
  ARP routing, TCP handshakes, HTTP/1.0 requests, and HTTP/1.1 chunked-transfer
  decoding over an RTL8139 interface.
- Strict HTTP/1.0 and HTTP/1.1 status-line parsing rejects unsupported
  versions, non-decimal codes, and missing separators before redirects or
  response bodies are accepted.
- Header names are recognized only at line boundaries. `Content-Length` uses
  bounded decimal parsing, duplicate or invalid values fail closed,
  `Content-Length` plus chunked transfer is rejected as ambiguous, and a body
  shorter than its declared length is never rendered.
- TLS 1.3 with X25519, RSA-PSS authentication, ChaCha20-Poly1305 records,
  strict RSA certificate-chain validation, explicit host/port anchor pins,
  imported CA roots, encrypted HTTP requests, and authenticated HTML/plain-text
  responses.
- Saving the current rendered document as `vex-page.txt` in the user's home
  directory, plus exact binary downloads under a sanitized URL-derived name.
- A native `Ctrl+Alt+S` screenshot path that downsamples the live framebuffer
  into a valid 256×192, 8-bit grayscale `vex-shot.bmp`. Its exact 50,230-byte
  format fits safely inside one 64 KiB MortFS file extent.
- An eight-record, newest-first download manager persisted in
  `.vex-downloads`, with exact filename, byte count, text/binary kind, and
  HTTP/HTTPS metadata. Private-mode saves are deliberately not indexed.
- Browser-data controls clear history, download metadata, named sessions,
  per-site profiles, or Notes and Read Later independently. Clearing download
  history deliberately keeps the downloaded MortFS files; all clear operations
  persist immediately and private mode cannot perform them.
- Local pages for Home, About, History, Bookmarks, Downloads, Saved Sessions,
  Library, Settings, and Network status.

## Controls

| Key | Action |
| --- | --- |
| `F3` | Open Vex from anywhere in the desktop |
| `Ctrl+K` | Open the Vex command bar |
| `Ctrl+T` / `Ctrl+W` | Open a tab / close the active unpinned tab |
| `Ctrl+Tab` / `Ctrl+1`…`Ctrl+4` | Cycle tabs / select a tab directly |
| `Ctrl+L` / `Ctrl+R` | Focus the address / reload |
| `Ctrl+F` / `Ctrl+H` | Find / open History |
| `Ctrl+D` | Bookmark the active page |
| `Ctrl+Shift+N` | Open the Notes and Read Later Library |
| `Ctrl+Alt+S` | Save a bounded framebuffer screenshot as `vex-shot.bmp` |
| `S` | Open Saved Sessions |
| `Q` | Open the Notes and Read Later Library |
| `/` | Edit the address; Up/Down chooses a local suggestion |
| Left / Right | Back / forward |
| Up / Down | Scroll the page or move through a list |
| `1` / `4` | Home / reload |
| `5` / `6` / `7` / `8` | Bookmarks / history / downloads / settings |
| `9` | Restore the last normal HTTP page from Home |
| `B` | Bookmark the current page |
| `F` | Find page text, or search entries on the History page |
| `M` | Toggle the reading layout for the current text page |
| `L` | Open the extracted-links panel |
| `D` | Save the rendered document to MortFS |
| `T` / `X` | New tab / close tab |
| `Ctrl+Shift+T` | Reopen the most recently closed tab |
| `Tab` | Switch to the next tab |
| `W` | Cycle Personal / Work / School / Dev workspaces |
| `P` | Toggle private mode |
| `K` | Approve the currently verified but untrusted HTTPS certificate pin |
| `C` | Clear history while on `vex://settings` |
| `V` | Clear the saved HTTPS certificate pin on `vex://settings` |
| `I` | Validate and import `vex-root.der` from the current home or `/` |
| `A` | Atomically import concatenated DER roots from `vex-roots.der` |
| `U` | Clear all imported CA roots on `vex://settings` |
| `J` / `Y` / `O` | Clear download history / named sessions / site profiles in Settings |
| `E` | Clear Notes and Read Later on `vex://settings` |

The command bar also accepts `library`, `note TEXT`, `read later`, and
`clear library`. Individual Library actions use `pin note N`, `unpin note N`,
`delete note N`, `remove later N`, and `export notes`. Tab organization is
available through `pin tab`, `unpin tab`,
`duplicate tab`, `move tab left`, `move tab right`, and `group focus`,
`group research`, `group later`, or `group none`.

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

Vex supports authenticated TLS 1.3 for validated RSA certificate chains and
never silently downgrades `https://`. Trust can come from an explicit
host-and-port anchor pin or from one of up to fifteen user-imported CA roots.
It does not yet ship a bundled public CA set, revocation service, or automatic
root-update channel, so arbitrary public websites are not universally trusted
out of the box. It also does not execute
JavaScript, accept cookies, load images or media, apply CSS layout, submit
forms, or provide a general-purpose DOM. Plain HTTP remains unencrypted and
must not be used for passwords or other sensitive data.

The per-origin controls are limited to capabilities the native renderer truly
owns: reading layout and extracted-link exposure. They are not cosmetic
JavaScript/cookie toggles; those active-content systems do not exist at all.

Non-text HTTP and authenticated HTTPS bodies are kept out of the renderer and
copied into a separate zero-padded 12 KiB staging buffer. The proposed filename
comes only from the final URL path segment and is restricted to ASCII letters,
digits, dot, dash, and underscore; empty or special `.`/`..` names fall back to
`vex-download.bin`. Pressing `D` writes the exact bounded payload to a normal
MortFS file after capacity and permission checks. The Downloads page reports
the eight newest saved names, byte counts, types, and transports across reboots.

Screenshot export is deliberately a bounded whole-frame capture rather than
canonical Vex's Chromium page-capture and annotation pipeline. It uses a
dedicated 49.5 KiB kernel buffer; it never reuses MortFS metadata or sector
scratch memory.

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
not stop at the outbound message: a strict ServerHello parser validates record
and handshake lengths, the negotiated TLS version/cipher, and the X25519 server
key share against RFC 8448's published trace. The post-hello key schedule now
computes the X25519 shared secret, rejects the forbidden all-zero result, and
derives both handshake traffic secrets plus their write keys and IVs. Those
outputs are checked byte-for-byte against the same published trace during boot.
Mort also constructs per-record nonces from the write IV and sequence number,
authenticates TLS 1.3 record headers and ciphertext, rejects forged Poly1305
tags before releasing plaintext, and decodes the authenticated inner content
type and padding. The AEAD path accepts the full TLS ciphertext limit rather
than only small test messages. Mort derives the Finished key and verifies the
server's constant-time HMAC over the authenticated transcript; the RFC 8448
transcript-through-CertificateVerify and Finished values are checked at boot.
The handshake byte stream is reassembled independently of record boundaries,
including split four-byte headers, split bodies, and multiple messages in one
record, behind a fail-closed 64 KiB per-message resource limit.
The certificate path begins with a canonical DER reader and bounded TLS 1.3
Certificate-list parser. Indefinite or non-minimal lengths, truncation, trailing
bytes, oversized chains, malformed BIT STRING signatures, and entry/extension
length mismatches are rejected before higher-level X.509 processing.
Subject Alternative Name DNS matching is ASCII case-insensitive, rejects
malformed names and embedded wildcards, and permits a wildcard only as the
complete left-most label matching exactly one host label. Broad `*.com`-style
patterns are rejected.
TBSCertificate traversal validates the optional version, canonical positive
serial number, required field order, validity sequence, SubjectPublicKeyInfo,
and explicitly tagged extensions. UTCTime and GeneralizedTime are normalized
with leap-year/calendar validation, and the SAN extension is located by OID
without trusting nested lengths.
Certificate validity uses a stable double-read of the full CMOS date and time,
covering BCD or binary RTCs and 12- or 24-hour mode. A missing/invalid century,
an update in progress that never stabilizes, or an impossible calendar value
fails closed instead of substituting a guessed date.
RSA SubjectPublicKeyInfo parsing requires the `rsaEncryption` OID with canonical
NULL parameters, a byte-aligned BIT STRING, a positive odd 2048- to 4096-bit
modulus, and a positive odd bounded exponent. The long-form DER path is covered
by a generated 2048-bit parser vector.
Mort also has a bounded 1024- to 4096-bit RSA public operation (the 1024-bit
floor exists only so the historical RFC trace can test the arithmetic; X.509
policy still requires at least 2048 bits). Its Montgomery implementation is
checked by recovering the complete PKCS#1 signature block from RFC 8448's
published certificate, including the expected SHA-256 digest.
Strict EMSA-PKCS1-v1_5 checking requires the complete SHA-256 DigestInfo,
at least eight `FF` padding octets, and no trailing data. TLS CertificateVerify
uses RSA-PSS-SHA256 with MGF1-SHA256, a 32-byte salt, the modulus top-bit rule,
and full delimiter/padding/hash validation. Both accept/reject paths use RFC
8448 values and deliberately corrupted digests at boot.
The TLS CertificateVerify parser enforces the negotiated
`rsa_pss_rsae_sha256` scheme and exact signature framing. Mort constructs the
TLS 1.3 server verification input (`64 * 0x20`, context string, separator, and
transcript hash), reproduces RFC 8448's message digest, and validates its actual
CertificateVerify signature end to end.
After the authenticated server Finished message, Mort derives the master secret,
client/server application traffic secrets, directional write material, and the
client Finished value. The master, both application secrets, and client Finished
are checked byte-for-byte against RFC 8448 before application records are
eligible to be sent.
The outbound record path builds the sequence-number nonce, authenticated header,
TLSInnerPlaintext content type, optional zero padding, ciphertext, and tag in a
capacity-checked buffer. Its boot test round-trips a padded handshake record and
also proves an undersized destination is rejected without an out-of-bounds write.
The browser's real network path now recognizes `https://`, defaults to port 443,
uses fresh RDRAND material for each X25519 keypair and ClientHello random, sends
the ClientHello through RTL8139/TCP, reassembles a fragmented/coalesced TLS
record stream, validates a live ChaCha20-Poly1305 ServerHello, and derives the
live handshake traffic keys. It then validates an optional compatibility CCS,
authenticates and decrypts the first protected record, and requires the
EncryptedExtensions handshake message. It continues across protected records,
parses the leaf certificate, validates its RTC validity interval and RSA key,
verifies RSA-PSS CertificateVerify against the exact transcript, and verifies
the server Finished value. Presented RSA chains are iterated within the 16-entry
certificate-list bound; every certificate receives RTC validity validation,
adjacent issuer/subject Names must match exactly, and every child
SHA256-with-RSA signature is verified using the next certificate's key. The
leaf must assert `CA:FALSE`, digitalSignature, serverAuth EKU, and a matching
DNS or IPv4 SAN. Every issuer must assert `CA:TRUE` and keyCertSign. Duplicate
role extensions and unrecognized critical extensions are rejected.
BasicConstraints `pathLenConstraint` is parsed as a canonical nonnegative
integer and enforced against the number of subordinate CA certificates.
The SHA-256 fingerprint of the final verified chain anchor can then be approved
explicitly with `K`; Vex stores the host-and-port-scoped anchor pin in the user's
MortFS state and compares it in constant time on later connections. Private
mode cannot persist trust. Alternatively, Settings can import a self-signed DER
CA from `vex-root.der` in the user's home or filesystem root. Import re-runs
canonical certificate parsing, RTC validity, CA BasicConstraints/keyCertSign,
critical-extension, RSA issuer, and self-signature checks before storing only
the validated DER anchor and its SHA-256 fingerprint in the bounded
`.vex-roots` MortFS store.
Settings can also validate a `vex-roots.der` file containing concatenated
canonical DER certificates. Bundle import skips already trusted roots, rejects
the entire in-memory transaction if any new entry is invalid or would exceed
the fifteen-root bound, and persists only after every entry passes. The VXR3
store occupies 122 of a MortFS file's 128-sector extent and migrates earlier
VXR1 hash-only and VXR2 DER stores in place. Malformed stores reset fail-closed.
If a server follows normal TLS practice and omits the
self-signed root, Vex verifies the signature on the final presented
intermediate (or leaf) against each locally stored root and completes the path
without requiring the server to transmit that root. On a trusted reconnect,
Vex derives both application
traffic secrets and keys, encrypts and sends client Finished, and retains
sequence-zero application state for the HTTPS request. Vex encrypts the GET,
accepts authenticated application records, safely ignores bounded NewSessionTicket
handshake messages, accumulates the response within the HTTP receive limit, and
passes it to the same content-type-aware text renderer used by HTTP. No
application bytes are released before record authentication and trust validation.
Relative links from an authenticated HTTPS page retain the `https://` scheme,
host, and non-default port rather than silently downgrading to HTTP.
This enables pinned and explicitly provisioned-CA HTTPS, not automatic
public-Web PKI. Chain construction,
RSA issuer signatures, certificate roles, usages, critical-extension policy,
and DNS/IPv4 SAN identity are enforced, including renewed leaf certificates
under the same trusted anchor. General public-Web compatibility still needs a
maintained CA bundle, revocation/update policy, and additional certificate
algorithms. Until then, an unmatched anchor fails closed for explicit approval
or CA provisioning.

Ephemeral TLS material is also fail-closed behind an x86 hardware-entropy gate.
Mort checks CPUID for RDRAND, retries failed samples, and enables the gate only
after two nonzero, distinct 256-bit samples. CPUs without an accepted source do
not get predictable fallback keys; HTTPS remains unavailable on them until a
second audited entropy provider exists.

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

The 75-assertion browser regression covers real DHCP configuration, ARP, TCP,
HTTP, and TLS
loading, HTML and literal plain-text rendering, bounded HTTP and authenticated
HTTPS binary staging with byte-exact MortFS saves,
script/style removal, links, redirects, chunked responses, local suggestions,
keyboard and mouse tab controls, full private-session discard, bookmarks,
downloads, Notes pin/export/delete and Read Later persistence/private isolation,
valid BMP screenshot output without filesystem corruption, explicit normal-session
recovery, screenshots, live ServerHello through
Finished verification, private-mode pin refusal, pinned encrypted GET/response,
private-mode root-import refusal, CA import, a separately renewed leaf under
the imported root with that root omitted by the server, and bookmark/root
persistence plus trust clearing after a full reboot.
