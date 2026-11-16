# What was built in MortOS

This is the public implementation record for the hardware work integrated into MortOS on 22 July 2026.

| MortOS commit | Work delivered |
| --- | --- |
| [`6f57f8c`](https://github.com/0xmortuex/MortOS/commit/6f57f8c) | Vendored the Mort networking stack and exposed `net`/`httpd` shell commands. The stack includes Ethernet, ARP, IPv4, ICMP, UDP, DHCP, DNS, TCP, and HTTP support around RTL8139. |
| [`9499d8e`](https://github.com/0xmortuex/MortOS/commit/9499d8e) | Added generic PCI capability discovery, Settings hardware status, Ethernet lifecycle controls, and legacy PC-speaker support. |
| [`2dfd9c4`](https://github.com/0xmortuex/MortOS/commit/2dfd9c4) | Added Intel 82801AA AC'97 discovery, volume control, PCM DMA, and Settings controls. |
| [`fab3759`](https://github.com/0xmortuex/MortOS/commit/fab3759) | Corrected PCI scanning to include all eight functions per slot, enabling discovery of multifunction USB controllers. |
| [`111c4ac`](https://github.com/0xmortuex/MortOS/commit/111c4ac) | Added minimal freestanding `memset`, `memcpy`, and `memmove` primitives required by optimized kernel builds. |
| [`48a2c0d`](https://github.com/0xmortuex/MortOS/commit/48a2c0d) | Added boot-time UHCI ownership, root-port enumeration, USB address assignment, device/configuration descriptors, VID/PID, and interface class reporting in Settings. |
| [`8db9d6b`](https://github.com/0xmortuex/MortOS/commit/8db9d6b) | Added USB `SET_CONFIGURATION`, endpoint discovery, HID boot-protocol selection, interrupt-IN polling, usage-to-scancode translation, and working USB keyboard input. |
| [`8268e3e`](https://github.com/0xmortuex/MortOS/commit/8268e3e) | Added HID boot-mouse reports, signed pointer movement, button state, a framebuffer cursor, launcher tile clicks, and Settings section clicks. |
| [`5866840`](https://github.com/0xmortuex/MortOS/commit/5866840) | Added Bluetooth USB class/endpoint discovery, HCI Reset control transport, Command Complete validation, and honest Detected/Reset sent/Ready Settings states. |
| [`d853628`](https://github.com/0xmortuex/MortOS/commit/d853628) | Added per-device USB addresses, an eight-entry device table, both UHCI root ports, one-level hub power/reset/status enumeration, and simultaneous keyboard/mouse bindings. |
| [`c3a72a7`](https://github.com/0xmortuex/MortOS/commit/c3a72a7) | Added a Settings USB Devices inventory showing address, VID/PID, class/protocol, and configuration state for each enumerated device. |
| [`9a0e226`](https://github.com/0xmortuex/MortOS/commit/9a0e226) | Added automatic root/hub USB hot-plug recovery, manual Settings rescan, topology event diagnostics, and a 13-assertion QEMU regression suite. |
| [`560309e`](https://github.com/0xmortuex/MortOS/commit/560309e) | Completed actionable Settings pages and search routing, added live hardware/network/storage/privacy/power/diagnostic controls, and persisted per-user preferences in MortFS. |
| [`8785757`](https://github.com/0xmortuex/MortOS/commit/8785757) | Replaced the local Vex mock-up with a native Mort browser using DHCP, DNS, ARP, TCP and HTTP, including tabs, history, bookmarks, links, redirects, private mode and downloads. |
| [`1db04ca`](https://github.com/0xmortuex/MortOS/commit/1db04ca) | Added private local address suggestions, HTTP/1.1 chunked-transfer decoding, public Settings/browser architecture guides, and a 17-assertion end-to-end browser regression. |
| [`84581ca`](https://github.com/0xmortuex/MortOS/commit/84581ca) | Removed QEMU-specific routing assumptions: DHCP now records subnet mask, gateway and DNS options, while Vex performs subnet-aware ARP routing through the leased gateway. |
| [`d8cae3c`](https://github.com/0xmortuex/MortOS/commit/d8cae3c) | Added Content-Type-aware HTML/plain-text rendering, safe rejection of unsupported binary media, and expanded the native browser regression to 21 assertions. |
| [`07a7820`](https://github.com/0xmortuex/MortOS/commit/07a7820) | Connected the existing Mort USB/PS2 pointer path to Vex tabs, new-tab control, navigation buttons, address bar, history, bookmarks and extracted-link rows. |
| [`10f4d73`](https://github.com/0xmortuex/MortOS/commit/10f4d73) | Added an end-to-end QEMU check that enumerates a USB mouse, moves the live MortOS pointer, clicks Vex's new-tab control, and verifies the tab state change. |
| [`b041161`](https://github.com/0xmortuex/MortOS/commit/b041161) | Added MortFS-backed recovery of the last non-private HTTP page, exposed only through an explicit Home action so startup never makes an unexpected network request. |
| [`fefc822`](https://github.com/0xmortuex/MortOS/commit/fefc822) | Began the native HTTPS foundation in Mort with freestanding SHA-256, HMAC-SHA256 and HKDF-SHA256, each publish-gated by standard boot-time test vectors. |
| [`4b12841`](https://github.com/0xmortuex/MortOS/commit/4b12841) | Added the ChaCha20 block function in Mort and gated it with the RFC 8439 test vector as the next TLS 1.3 cipher-suite prerequisite. |
| [`2cfcaee`](https://github.com/0xmortuex/MortOS/commit/2cfcaee) | Added Poly1305 and the combined ChaCha20-Poly1305 AEAD construction in Mort, with RFC 8439 tag, ciphertext, and combined-authentication vectors. |
| [`a3a7b4b`](https://github.com/0xmortuex/MortOS/commit/a3a7b4b) | Added constant-time-ladder X25519 in Mort, validated against RFC 7748's iteration vector plus Alice/Bob public keys and shared secret. |
| [`c750da0`](https://github.com/0xmortuex/MortOS/commit/c750da0) | Added TLS 1.3 HKDF-Expand-Label and Derive-Secret encoding in Mort, validated against the published RFC 8448 handshake trace. |
| [`7a2d54a`](https://github.com/0xmortuex/MortOS/commit/7a2d54a) | Added a native Mort TLS 1.3 ClientHello builder with SNI, supported versions/groups, X25519 key share, signature algorithms, and ChaCha20-Poly1305; guest tests parse the complete wire structure. |
| [`051365e`](https://github.com/0xmortuex/MortOS/commit/051365e) | Added a fail-closed x86 RDRAND entropy gate in Mort for ephemeral TLS keys, including CPUID detection, retry handling, and distinct nonzero 256-bit sample validation. |
| [`02f035e`](https://github.com/0xmortuex/MortOS/commit/02f035e) | Added strict TLS 1.3 ServerHello parsing in Mort, validated against RFC 8448 and independently checked for negotiated version, cipher suite, X25519 group, and extracted server key. |
| [`072fd88`](https://github.com/0xmortuex/MortOS/commit/072fd88) | Implemented the TLS 1.3 post-hello key schedule in Mort: X25519 agreement with all-zero rejection, handshake/client/server traffic secrets, and directional write keys and IVs, verified against RFC 8448. |
| [`3d28000`](https://github.com/0xmortuex/MortOS/commit/3d28000) | Added full-size ChaCha20-Poly1305 TLS record authentication/decryption, sequence-number nonce construction, inner-content decoding, and a fail-closed forged-tag test that proves plaintext is not released before authentication. |
| [`28e6ceb`](https://github.com/0xmortuex/MortOS/commit/28e6ceb) | Added TLS 1.3 Finished-key derivation and constant-time server Finished verification in Mort, checked against the RFC 8448 transcript through CertificateVerify and its published verify-data value. |
| [`25e1691`](https://github.com/0xmortuex/MortOS/commit/25e1691) | Closed four hostile-input bounds bugs: overflow-safe chunk-size decoding, validated IPv4/TCP lengths before receive arithmetic, persisted history-index validation/string termination, and complete USB descriptor bounds checks. |
| [`58797d1`](https://github.com/0xmortuex/MortOS/commit/58797d1) | Added a bounded TLS handshake-stream reassembler that handles split headers, split bodies, and coalesced messages independently of encrypted-record boundaries. |
| [`9495694`](https://github.com/0xmortuex/MortOS/commit/9495694) | Added canonical DER framing and bounded TLS 1.3 Certificate-list parsing, rejecting indefinite/non-minimal lengths, truncation, trailing bytes, malformed signatures, oversized chains, and entry/extension mismatches. |
| [`c51791f`](https://github.com/0xmortuex/MortOS/commit/c51791f) | Added strict X.509 Subject Alternative Name DNS matching with case folding, DNS-label syntax validation, and single-leftmost-label wildcard rules; embedded and broad top-level wildcards are rejected. |
| [`b8289e8`](https://github.com/0xmortuex/MortOS/commit/b8289e8) | Added structural TBSCertificate traversal and extraction of canonical serial, validity, SubjectPublicKeyInfo, and extensions; UTCTime/GeneralizedTime receive calendar/leap-year checks and SAN is located by OID. |
| [`80c760e`](https://github.com/0xmortuex/MortOS/commit/80c760e) | Added fail-closed certificate-time validation against a stable full CMOS date, handling BCD/binary and 12/24-hour RTC modes while rejecting missing centuries, impossible dates, and unstable update windows. |
| [`761e387`](https://github.com/0xmortuex/MortOS/commit/761e387) | Added RSA SubjectPublicKeyInfo parsing with exact `rsaEncryption` parameters, byte-aligned key framing, canonical positive integers, 2048–4096-bit odd modulus policy, and bounded odd exponent validation. |
| [`537d068`](https://github.com/0xmortuex/MortOS/commit/537d068) | Added bounded big-integer RSA public arithmetic in Mort using Montgomery multiplication and verified the complete recovered PKCS#1 block from RFC 8448's published certificate signature. |
| [`35f7a55`](https://github.com/0xmortuex/MortOS/commit/35f7a55) | Added strict RSA PKCS#1 v1.5/SHA-256 certificate-signature checks and RSA-PSS-SHA256/MGF1 TLS CertificateVerify validation, including malformed-digest rejection. |
| [`088077e`](https://github.com/0xmortuex/MortOS/commit/088077e) | Connected RSA-PSS to TLS 1.3 CertificateVerify parsing, exact server-context construction, transcript hashing, negotiated-scheme enforcement, and end-to-end RFC 8448 signature verification. |
| [`9b55565`](https://github.com/0xmortuex/MortOS/commit/9b55565) | Completed the TLS 1.3 post-server-Finished key schedule: master secret, client/server application traffic secrets, directional write material, and client Finished generation. |
| [`fcee003`](https://github.com/0xmortuex/MortOS/commit/fcee003) | Added capacity-checked outbound TLS 1.3 records with sequence nonces, authenticated headers, inner content types, optional padding, ciphertext, and tags. |
| [`886a57c`](https://github.com/0xmortuex/MortOS/commit/886a57c) | Connected Vex HTTPS URLs to the real RTL8139/TCP path: fresh RDRAND-backed X25519 ClientHello exchange, bounded TLS record-stream reassembly, strict live ServerHello validation, and handshake-key derivation while keeping response content behind the certificate trust gate. |
| [`1cff8ad`](https://github.com/0xmortuex/MortOS/commit/1cff8ad) | Added live protected-handshake processing: strict optional compatibility-CCS validation, ChaCha20-Poly1305 record authentication/decryption, sequence tracking, handshake-stream feed, and required EncryptedExtensions; Vex now advertises only its implemented RSA-PSS authentication scheme. |
| [`fd12701`](https://github.com/0xmortuex/MortOS/commit/fd12701) | Verified the complete live TLS server flight: bounded transcript accumulation, leaf certificate DER/RSA/RTC-validity checks, RSA-PSS CertificateVerify verification, and server Finished verification; chain trust remains fail-closed. |
| [`e3c8e00`](https://github.com/0xmortuex/MortOS/commit/e3c8e00) | Added an explicit trust-on-first-use workflow for private HTTPS: SHA-256 leaf fingerprints are scoped to host and port, saved in MortFS only after `K` approval, compared in constant time, and never persisted from private mode. |
| [`6a59ad8`](https://github.com/0xmortuex/MortOS/commit/6a59ad8) | Completed the pinned TLS client handshake: live master/application secrets and traffic keys, encrypted client Finished, host-confirmed handshake completion, sequence-zero application state, prompt close of untrusted connections, and key cleanup on failure. |
| [`bd417cf`](https://github.com/0xmortuex/MortOS/commit/bd417cf) | Enabled authenticated pinned HTTPS pages: encrypted GET requests, application-record authentication/decryption, bounded NewSessionTicket handling, safe HTTP accumulation/rendering, HTTPS UI state, application-key cleanup, and FIN-safe delivery of the final TLS record. |
| [`df3a408`](https://github.com/0xmortuex/MortOS/commit/df3a408) | Added visible HTTPS trust management in Browser Settings, persistent-pin clearing, secure-scheme preservation for relative links, authenticated-page link extraction coverage, and corrected stale UI capability descriptions. |
| [`11ed913`](https://github.com/0xmortuex/MortOS/commit/11ed913) | Audited and corrected the browser's security claims and live Network status so working pinned HTTPS is distinguished precisely from the still-unimplemented public-CA chain/root-store mode. |
| [`c8f71ab`](https://github.com/0xmortuex/MortOS/commit/c8f71ab) | Added bounded RSA certificate-chain traversal, full-chain RTC validity checks, exact issuer/subject linking, SHA256-with-RSA child-signature verification, final-anchor fingerprint pins, and a renewal regression using two different leaves under one private CA. |
| [`316412c`](https://github.com/0xmortuex/MortOS/commit/316412c) | Enforced X.509 roles and identity: CA/leaf BasicConstraints, keyCertSign/digitalSignature usage, serverAuth EKU, DNS or IPv4 SAN matching, duplicate-role rejection, and fail-closed unknown critical extensions. |
| [`52ca551`](https://github.com/0xmortuex/MortOS/commit/52ca551) | Added a bounded per-user MortFS CA-root store, strict self-signed DER import, constant-time anchor lookup, private-mode refusal, Vex Settings import/clear controls, automatic trust across independent leaf renewals, and BasicConstraints path-length enforcement. |
| [`6c83a98`](https://github.com/0xmortuex/MortOS/commit/6c83a98) | Upgraded imported roots from hash-only pins to validated DER trust anchors, migrated legacy VXR1 stores, completed chains against a local issuer when servers omit the root, and enforced the local root's path-length constraint. |
| [`25d2460`](https://github.com/0xmortuex/MortOS/commit/25d2460) | Expanded Vex trust storage to fifteen DER anchors within one MortFS extent and added atomic concatenated-DER bundle import, duplicate skipping, VXR1/VXR2 migration, capacity enforcement, persistence, and invalid-bundle rollback. |
| [`dd6e778`](https://github.com/0xmortuex/MortOS/commit/dd6e778) | Added bounded non-text HTTP/HTTPS downloads: Vex stages up to 12 KiB outside the text renderer, derives and sanitizes a MortFS filename from the URL, saves the exact bytes only on explicit request, and reports the last saved filename and size. |
| [`337ca1b`](https://github.com/0xmortuex/MortOS/commit/337ca1b) | Brought the Claude-designed MortuexOS desktop language into the real framebuffer kernel and began the canonical Vex native port: shared gold-diamond identity, warm browser shell, vertical tabs/library, floating dock, rounded UI primitives, and an explicit upstream-to-native boundary document. |
| [`123d73a`](https://github.com/0xmortuex/MortOS/commit/123d73a) | Added Personal, Work, School, and Dev Vex workspaces with independent four-tab stacks and persisted active-workspace selection. |
| [`093c91e`](https://github.com/0xmortuex/MortOS/commit/093c91e) | Added the canonical-style `Ctrl+K` Vex command bar with page navigation, new/private tab actions, workspace switching, and address fallback. |
| [`7e84cbe`](https://github.com/0xmortuex/MortOS/commit/7e84cbe) | Replaced the session-only last-download display with an eight-record MortFS manager containing exact filename, byte count, text/binary kind, and HTTP/HTTPS metadata; private saves remain deliberately unrecorded. |
| [`f36c5fb`](https://github.com/0xmortuex/MortOS/commit/f36c5fb) | Added strict shared HTTP/1.0/1.1 status-line parsing for normal responses and redirects, rejecting unsupported versions, non-decimal codes, and missing separators before body rendering. |
| [`32aeb7e`](https://github.com/0xmortuex/MortOS/commit/32aeb7e) | Added four persistent named Vex session snapshots, private-mode save refusal, a Saved Sessions page, command-bar save/open/delete workflows, and case-insensitive on-device History search. |
| [`76dc419`](https://github.com/0xmortuex/MortOS/commit/76dc419) | Added a native reading layout and eight persistent per-origin profiles for reading mode and extracted-link policy, enforced private-mode non-persistence, and repaired alias-unsafe reload so saved controls reapply on a real refresh. |
| [`c0aa1ca`](https://github.com/0xmortuex/MortOS/commit/c0aa1ca) | Hardened HTTP message framing with line-anchored header recognition, bounded decimal Content-Length parsing, duplicate/ambiguous framing rejection, and truncated-body refusal before rendering. |
| [`eb933c7`](https://github.com/0xmortuex/MortOS/commit/eb933c7) | Completed browser-data clearing for download metadata, named sessions, and per-site profiles through Settings and the command bar, with private-mode refusal and preservation of downloaded MortFS files. |
| [`c1854cf`](https://github.com/0xmortuex/MortOS/commit/c1854cf) | Added automatic full tab-stack recovery for all four Vex workspaces plus a persistent four-item recently closed ring and command/keyboard reopen workflow, while excluding private navigation from the journal. |
| [`74791f6`](https://github.com/0xmortuex/MortOS/commit/74791f6) | Added the native Vex Library with eight persistent short notes and eight Read Later URLs, a local page and command-bar workflows, clickable reopening, private-mode non-persistence, reboot recovery, and durable data clearing. |
| [`3759e8e`](https://github.com/0xmortuex/MortOS/commit/3759e8e) | Added persistent per-workspace tab pins and three color groups, duplication and left/right ordering, pinned-tab close protection, and canonical Ctrl+T/W/L/R/F/H/D/Tab/1–4 shortcuts. |
| [`3e8e9b0`](https://github.com/0xmortuex/MortOS/commit/3e8e9b0) | Completed the feasible native Vex productivity set: note pin/delete/Markdown export, individual Read Later removal, bounded 256×192 BMP framebuffer capture, full private-session state rollback, global app shortcuts from Home, an explicit upstream capability boundary, refreshed screenshots, and modernized full-system regressions. |

## Demonstrated results

- RTL8139 Ethernet obtained a DHCP address (`10.0.2.15`) on QEMU's default user network.
- AC'97 initialized and accepted a 48 kHz PCM test-tone buffer.
- UHCI enumerated QEMU's USB tablet as one device, read VID/PID `0627:0001`, and identified USB interface class `3` (HID).
- QEMU's USB keyboard configured as class/protocol `3/1`, navigated the graphical desktop, and entered a working terminal command through UHCI reports.
- QEMU's USB mouse moved a live framebuffer cursor and opened Settings by clicking its launcher tile.
- A combined QEMU topology enumerated keyboard, class-9 hub, and downstream mouse as three devices; keyboard navigation and mouse selection worked during the same boot.
- The Settings USB Devices page displayed all three addressed devices and their descriptor identities during that combined-device boot.
- Automated QEMU tests removed and reattached both a root-port keyboard and a hub-connected mouse; the device table and HID bindings recovered in all 13 assertions.
- MortOS remained responsive in the graphical launcher and Settings app after boot-time USB enumeration.
- Vex loaded a host-served page through the guest RTL8139 path, followed a relative link and redirect, decoded a chunked response, and preserved browser state across reboot.
- The combined shell, USB, Settings, and browser verification completed 41/41 assertions on the documented tree.
- The portable-route browser regression completed 19/19 assertions, including validation of the router and DNS values delivered by DHCP.
- Content handling completed 21/21 browser assertions, including literal plain text, chunked HTML, and binary-response rejection.
- The USB-mouse browser pass completed 22/22 assertions with an actual pointer-driven toolbar click.
- Private-safe session recovery completed 24/24 browser assertions, including stored URL validation and explicit restore.
- The final combined gate completed 48/48 assertions: 4 shell, 13 USB hot-plug, 7 Settings, and 24 native-browser checks.
- The TLS primitive checkpoint completed 7/7 smoke assertions, including SHA-256, RFC 4231 HMAC and RFC 5869 HKDF vectors inside the booted kernel.
- The ChaCha20 checkpoint completed 8/8 smoke assertions with the RFC 8439 block vector inside the booted kernel.
- The authenticated-encryption checkpoint completed 10/10 smoke assertions after validating Poly1305 and the full ChaCha20-Poly1305 AEAD vector.
- The key-exchange checkpoint completed 11/11 smoke assertions with RFC 7748 iteration and full Diffie-Hellman agreement vectors.
- The TLS 1.3 key-schedule checkpoint completed 12/12 smoke assertions with an RFC 8448 derived-secret trace.
- The ClientHello checkpoint completed 13/13 smoke assertions, including independent parsing of record/handshake lengths and mandatory extensions from guest memory.
- The hardware-entropy checkpoint completed 14/14 smoke assertions under QEMU's maximum x86 CPU profile with a live nonzero RDRAND sample.
- The ServerHello checkpoint completed 15/15 smoke assertions, including extraction and independent verification of the RFC 8448 X25519 server key.
- The handshake-keys checkpoint completed 16/16 smoke assertions with independent guest-memory checks of the RFC 8448 handshake secret, server traffic secret, write key, and IV.
- The encrypted-record checkpoint completed 18/18 smoke assertions, covering forged-tag rejection and authenticated recovery of a TLS 1.3 handshake payload.
- The Finished-verification checkpoint completed 19/19 smoke assertions against the RFC 8448 server Finished value.
- The input-hardening checkpoint completed 21/21 boot assertions plus the full 24/24 browser and 13/13 USB hot-plug regressions.
- The handshake-reassembly checkpoint rejects oversized messages and reconstructs fragmented/coalesced messages inside the booted kernel.
- The certificate-container checkpoint completed 22/22 smoke assertions with valid extraction and malformed-DER/list rejection.
- The certificate-hostname checkpoint completed 23/23 smoke assertions across exact, wildcard, multi-label, malformed-label, and overbroad-pattern cases.
- The X.509 field checkpoint completed 24/24 smoke assertions with normalized validity, SPKI/extension bounds, and SAN extraction.
- The RTC-validity checkpoint completed 25/25 smoke assertions with a live full-date read from QEMU CMOS.
- The RSA-key checkpoint completed 26/26 smoke assertions using a generated long-form 2048-bit DER vector plus malformed-exponent rejection.
- The RSA-arithmetic checkpoint completed 27/27 smoke assertions, independently checking the recovered signature-block prefix and SHA-256 digest in guest memory.
- The RSA-signature checkpoint completed 29/29 smoke assertions across RFC 8448 certificate and CertificateVerify encodings plus corrupted-digest rejection.
- The TLS CertificateVerify checkpoint completed 30/30 smoke assertions with independent validation of the RFC server-context digest.
- The application-key checkpoint completed 31/31 smoke assertions with independent guest-memory checks of the RFC master secret, both application secrets, and client Finished.
- The outbound-record checkpoint completed 32/32 smoke assertions with a padded encrypt/decrypt round trip and undersized-buffer rejection.
- The live-negotiation checkpoint completed 25/25 browser assertions against a host TLS 1.3 server plus the full 32/32 boot/crypto/security smoke gate.
- The protected-handshake checkpoint again completed 25/25 browser assertions and 32/32 smoke assertions while keeping certificate trust fail-closed.
- The server-flight checkpoint completed 25/25 browser assertions and 32/32 smoke assertions with live CertificateVerify and Finished authentication.
- The certificate-pin checkpoint completed 27/27 browser assertions and 32/32 smoke assertions, including private-mode refusal and reboot persistence.
- The pinned client-handshake checkpoint completed 28/28 browser assertions and 32/32 smoke assertions, including confirmation from the host TLS implementation.
- The authenticated-HTTPS checkpoint completed 28/28 browser assertions and 32/32 smoke assertions, with the host inspecting the encrypted GET and Vex rendering the authenticated response marker.
- The HTTPS trust-management checkpoint completed 29/29 browser assertions and 32/32 smoke assertions, including reboot persistence followed by an explicit Settings clear.
- The chain-anchor checkpoint completed 29/29 browser assertions and 32/32 smoke assertions; a renewed leaf/key under the same pinned CA remained trusted only after full issuer-signature verification.
- The strict X.509-policy checkpoint kept the live browser gate at 29/29 and expanded boot/crypto/security validation to 33/33 assertions.
- The imported-root checkpoint completed 32/32 live browser assertions and 33/33 boot/crypto/security assertions, including host-pin fallback, private-mode import refusal, an independently renewed leaf under the imported CA, reboot persistence, and explicit root clearing.
- The local-anchor chain-building checkpoint kept both gates green while the live TLS server deliberately omitted its root certificate; Vex completed the chain from the transmitted leaf to the validated MortFS anchor.
- The CA-bundle checkpoint completed 34/34 live browser assertions and 33/33 boot/crypto/security assertions, including duplicate elimination, two-root reboot persistence, deliberate source corruption, atomic rollback, and explicit clearing.
- The binary-download checkpoint completed 39/39 live browser assertions and 33/33 boot/crypto/security assertions, including hostile URL-filename sanitization, zero binary leakage into the text renderer, byte-exact MortFS persistence over HTTP and authenticated HTTPS, reboot survival, and corrupt-bundle rollback.
- The canonical-Vex identity and workspace checkpoints completed 43/43 live browser assertions; the command-bar checkpoint expanded that gate to 45/45.
- The persistent download-manager checkpoint completed 48/48 live browser assertions and 33/33 boot/crypto/security assertions, including private-mode non-recording, exact per-record length/type/transport metadata, three-save indexing, and full reboot recovery.
- The strict HTTP status checkpoint completed 49/49 live browser assertions and 33/33 boot/crypto/security assertions; a malicious `2A0` status was rejected before its body reached the renderer.
- The named-session and searchable-History checkpoint completed 53/53 live browser assertions and 33/33 boot/crypto/security assertions, including private-tab save refusal and full session-library reboot recovery.
- The reading/site-control checkpoint completed 57/57 live browser assertions and 33/33 boot/crypto/security assertions, including origin-scoped link blocking, alias-safe reload, preference reapplication, and full reboot recovery.
- The HTTP framing checkpoint completed 59/59 live browser assertions and 33/33 boot/crypto/security assertions, including live ambiguous-framing and truncated-body attacks whose markers never reached the renderer.
- The browser-data checkpoint completed 61/61 live browser assertions and 33/33 boot/crypto/security assertions; direct post-shutdown MortFS inspection proved all three clears persisted while exact downloaded files remained intact.
- The workspace-journal checkpoint completed 64/64 live browser assertions and 33/33 boot/crypto/security assertions, including multi-entry LIFO reopen, all-workspace recovery, and reopening a closed tab after a full reboot.
- The Notes/Read Later checkpoint completed 67/67 live browser assertions and 33/33 boot/crypto/security assertions, including exact record contents, private-mode refusal, full reboot recovery, clickable local-library integration, and direct post-shutdown proof that clearing both collections persisted.
- The tab-organization checkpoint completed 70/70 live browser assertions and 33/33 boot/crypto/security assertions, including persistent pin/group metadata, duplicate/reorder behavior, and canonical shortcut routing.
- The final native-productivity checkpoint completed 75/75 browser, 33/33 smoke, 7/7 Settings, 13/13 USB hot-plug, 9/9 graphics, 23/23 filesystem, and 11/11 compiled-program assertions. It verified private-state rollback, exact BMP/Markdown files, downloaded-file preservation, Home-to-app function keys, per-user filesystem permissions, and `/bin` execution.

## What this does not claim

- No new physical hardware was manufactured.
- PCI Wi-Fi detection is not a Wi-Fi MAC/PHY driver.
- USB Bluetooth-class recognition is not yet a Bluetooth HCI, L2CAP, pairing, or profile stack.
- USB keyboard support is not yet a general hub, hot-plug, arbitrary-HID, storage, or isochronous subsystem.
- QEMU validation is not proof of compatibility with arbitrary physical chip revisions.

These distinctions are deliberate so readers can see exactly what MortOS can do today and what remains engineering work.
