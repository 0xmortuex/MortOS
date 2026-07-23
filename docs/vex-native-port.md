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
| Vertical tabs and new-tab workflow | Four isolated bounded tab stacks in a native sidebar |
| Workspaces | Personal, Work, School, and Dev stacks with persisted selection |
| Address / command surface | `Ctrl+K` actions, local suggestions, and `vex://` / HTTP / HTTPS navigation |
| History, bookmarks, sessions | Per-user MortFS records |
| Private browsing | No persistent history, session recovery, pins, or CA imports |
| Downloads manager | Eight persistent exact-byte MortFS records with type and transport metadata |
| Network and TLS | `mortnet`, RTL8139, DNS, TCP, and the Mort TLS 1.3 client |
| Web content | Fail-closed HTML-to-text engine; scripts and styles never execute |
| Settings and trust | Native Vex pages backed by MortFS CA roots and host pins |

This makes it a real platform port: it follows Vex's identity, information
architecture, and user workflows, while the executable implementation is
necessarily kernel-native. It does **not** claim that the Electron executable
or Chromium engine is embedded.

## Porting order

1. Shared identity, vertical tabs, library navigation, and command/address UI.
2. Isolated workspaces and persisted workspace selection.
3. Multi-item download manager, named sessions, and searchable history.
4. Reading mode, per-site preferences, and content controls supported by the
   native renderer.
5. Further web compatibility only after memory isolation, process support, and
   a substantially richer rendering engine exist.

Features that depend directly on Chromium extensions, JavaScript web apps,
DRM media, Electron webviews, or Node modules remain upstream-only until
MortuexOS has equivalent safe platform primitives.
