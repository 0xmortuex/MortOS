# Vex native port

MortuexOS does not ship a browser that merely borrows the Vex name. The
canonical product and design source is
[`0xmortuex/Vex`](https://github.com/0xmortuex/Vex), version 2.28.1. The native
port was initially aligned against upstream commit `1b10ec5`.

The upstream desktop application uses Electron, Chromium, Node.js, webviews,
and operating-system services supplied by Windows. Those binaries cannot run
unchanged inside a 32-bit freestanding hobby kernel. MortuexOS therefore ports
Vex at the product and workflow layer while replacing each host dependency with
a native Mort subsystem:

| Canonical Vex concept | MortuexOS implementation |
| --- | --- |
| Vex gold diamond and browser chrome | Rasterized by the Mort framebuffer UI |
| Vertical tabs and new-tab workflow | Four isolated bounded tab stacks, persistent recently closed tabs, pins, color groups, duplication, and reordering |
| Workspaces | Personal, Work, School, and Dev stacks with automatic full-stack recovery |
| Address / command surface | `Ctrl+K` actions, local suggestions, and `vex://` / HTTP / HTTPS navigation |
| History, bookmarks, sessions | Searchable history plus named tab snapshots in per-user MortFS records |
| Notes and Read Later | Eight bounded notes and eight queued web URLs in a private-safe native Library |
| Private browsing | No persistent history, session recovery, pins, or CA imports |
| Downloads manager | Eight persistent exact-byte MortFS records with type and transport metadata |
| Network and TLS | `mortnet`, RTL8139, DNS, TCP, and the Mort TLS 1.3 client |
| Web content | Fail-closed HTML-to-text engine; scripts and styles never execute |
| Reading and site controls | Persistent per-origin reading layout and extracted-link policy |
| Settings and trust | Native Vex pages backed by MortFS CA roots and host pins |
| Screenshots | Bounded 256×192 grayscale BMP capture of the live framebuffer |

This makes it a real platform port: it follows Vex's identity, information
architecture, and user workflows, while the executable implementation is
necessarily kernel-native. It does **not** claim that the Electron executable
or Chromium engine is embedded.

## Porting order

1. Shared identity, vertical tabs, library navigation, and command/address UI.
2. Isolated workspaces and persisted workspace selection.
3. Multi-item download manager, named sessions, searchable history, and an
   on-device Notes / Read Later Library.
4. Reading mode, per-site preferences, and native-renderer content controls.
5. Further web compatibility only after memory isolation, process support, and
   a substantially richer rendering engine exist.

Features that depend directly on Chromium extensions, JavaScript web apps,
DRM media, Electron webviews, or Node modules remain upstream-only until
MortuexOS has equivalent safe platform primitives.

## Audited upstream boundary

The following is an explicit capability audit against the canonical Vex
2.28.1 tree, not a list of hidden toggles.

| Upstream capability family | Native status | Missing platform prerequisite |
| --- | --- | --- |
| Vertical tabs, workspaces, pins, groups, duplicate/reorder, recently closed | Implemented with bounded MortFS recovery | — |
| History, bookmarks, named sessions, command bar | Implemented natively | — |
| Notes, Read Later, pin/delete/remove/export | Implemented with bounded local records and Markdown export | — |
| Downloads and screenshots | Exact bounded downloads plus whole-frame BMP capture | Chromium page capture/annotation remains unavailable |
| Reading mode and per-origin controls | Implemented for text layout and extracted-link exposure | — |
| HTML/CSS/DOM, JavaScript, forms, images, video, WebGL, web apps | Unsupported and fail-closed | Sandboxed processes, virtual memory, a DOM/layout engine, JS runtime, image/media codecs |
| Electron webviews, split screen, PiP, pop-outs, live tab previews | Unsupported | Multi-process web surfaces and a compositing window manager |
| Chromium extensions, content scripts, boosts, element zapping, full ad blocking | Unsupported | Extension sandbox plus DOM and request-interception APIs |
| Cookies, service workers, site storage, passwords/autofill | Unsupported | Same-origin storage model, encrypted secret service, renderer isolation |
| Page translation, read-aloud, media capture, conferencing | Unsupported | Language/speech runtimes, codecs, device-permission broker |
| AI agent, cloud workers, Ollama, MCP tools, sync | Unsupported | Large model/runtime support, credential/keychain isolation, public-Web compatibility |
| General public-Web PKI | Partially supported through explicit validated CA roots and host pins | Maintained root bundle, update/revocation policy, additional certificate algorithms |
| Per-domain zoom and rich accessibility transforms | Unsupported in the fixed 8×16 renderer | Scalable font shaping and a richer layout engine |

MortuexOS reports these limits directly. It does not label an unavailable
Chromium-dependent feature as working merely because the canonical desktop app
has it.
