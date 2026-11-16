# What mortnet teaches us about Mort

Building a network stack in a language you also wrote means every milestone
stress-tests the language. This file collects what each milestone revealed —
it doubles as a wishlist for the next Mort version.

## From M6 (HTTP server)

1. **String literals saved the day — Mort escapes pass through to C.** The lexer
   keeps `\r\n` verbatim and re-emits it into a C string literal, so
   `"HTTP/1.1 200 OK\r\n"` is a real CRLF at runtime and `"..." as u64` gives its
   address. That turned the HTTP response from hundreds of hand-typed ASCII codes
   into readable text, and let the whole HTML page live as one literal. The
   missing piece is only the inverse — no way to write a literal into a mutable
   buffer without a copy loop, and no `char` literal for the request-parsing
   comparisons (`*b == 71` instead of `*b == 'G'`).

2. **The server (passive open) is the client state machine mirrored.** LISTEN →
   SYN_RCVD → ESTABLISHED reused every piece of M5's segment layer; the only new
   idea is learning the peer from the inbound SYN's source MAC/IP/port instead of
   ARPing first. Answering ARP for our own IP (via `net_handle_frame`) is what
   makes the guest reachable at all — the finale leans on M2's dispatcher.

3. **Seven milestones, one language change.** M0 needed nothing; M1 added
   `inl/outl`; M2–M6 added nothing. A NIC driver, ARP, ICMP, DHCP, DNS, a TCP
   client and server, and an HTTP server — all in Mort as it was after the first
   milestone. The standing wishlist for the language, in rough priority: a module
   system, `match`, `break`/`continue`, `char`/string ergonomics, packed structs.
   None were blockers; all would make the next stack half the size.

## From M5 (TCP)

1. **The state machine wants a `match`/`switch` and `break`.** The connection
   loop is a tower of nested `if`s keyed on `(state, flags)`, because Mort has
   neither multi-way branching nor loop `break`. It's correct and it fit, but a
   `match state { ... }` plus labelled exits would make the ESTABLISHED/close
   logic read the way the RFC state diagram looks. This is the clearest case yet
   for both features.

2. **32-bit sequence arithmetic just works** — `g_snd_nxt = g_snd_nxt + len`
   with `u32` wraparound is exactly TCP's model, and comparing `their_ack ==
   g_snd_nxt` needed no special modular-compare helper for this simple client
   (a full stack handling reordering/wrap would want `seq_lt` helpers, but the
   width and wrap semantics are already right).

3. **Still no new language features needed.** Four milestones running now
   (M2–M5) with zero additions to Mort after M1's `inl/outl`. The stack is
   real: ARP, ICMP, DHCP, DNS, and a TCP connection, all in a language whose
   compiler is a few thousand lines of Python. What's missing is ergonomics
   (modules, `match`, `break`, strings, packed structs), not power.

## From M4 (DNS)

1. **No `break` or `continue`.** Mort's only loop exits are the condition and
   `return`. DNS parsing is full of "scan until a sentinel" loops (label
   walking, name skipping, answer iteration), so each became a `done` flag or a
   nested flag-loop instead of a clean `while { ... break }`. It works and stays
   readable, but `break`/`continue` would noticeably simplify parser code — and
   there's a lot more of it coming in M5 (TCP) and M6 (HTTP).

2. **No string type — hostnames are hand-laid `[u8; N]` byte arrays.** `"example.com"`
   in a demo is written as `[101, 120, 97, ...]`. String literals exist as `*u8`
   for `print_string`, but there's no way to write one into a local buffer or
   index characters ergonomically. A `char` literal (`'e'`) and copying a string
   literal into a buffer would remove the ASCII-code tables the demos carry.

3. **Compression pointers parsed cleanly.** The one genuinely tricky part of DNS —
   an answer NAME that's a 2-byte pointer (`0xC0 | offset`) back into the
   question — needed only a top-two-bits check in `dns_skip_name`. Fixed-width
   `u8`/`u16` and bit ops carried it without fuss.

## From M3 (UDP + DHCP)

1. **`-O2` emits SSE, which triple-faults a bare-metal kernel.** The DHCP demo
   has larger buffers, and at `-O2` the compiler vectorized a zero-init into
   `xorps xmm0, xmm0` (`0f 57 c0`). The kernel runs with SSE disabled
   (`CR4.OSFXSR = 0`) and, being a minimal demo, installs no IDT — so that one
   instruction `#UD`s and, with no handler, cascades straight to a triple fault
   and reboot loop. M1/M2 were small enough that the vectorizer never fired.
   Fix: build freestanding with `-mno-sse -mno-sse2 -mno-mmx` so codegen stays
   scalar. **This matters for the eventual MORT OS integration** — the real
   kernel's `build.py` compiles `-O2` without these flags; it survives only
   because its current code doesn't trip the vectorizer. Adding a big
   packet-buffer memset could change that. Either add the flags there too, or
   have `kernel_setup` enable SSE (set `CR4.OSFXSR`).

2. **No struct-based headers — everything is byte pokes.** Without a way to
   overlay a struct on a raw buffer (packed structs, pointer casts to a struct
   type at an arbitrary address), every header field is a hand-written
   `be16_store(buf + off, ...)`. It works and is explicit, but a `@packed`
   struct mapped onto a `*u8` would cut the driver and protocol code in half
   and remove a class of offset-arithmetic bugs. Biggest single win Mort could
   hand mortnet.

## From M2 (ARP + ICMP)

1. **No modules, no imports — the stack is one giant translation unit.** mortc
   compiles a single `.mx` file, so `build_demo.py` and `test/run_tests.py`
   concatenate every `net/*.mx` (+ the driver, + one demo main) into one file
   before compiling. It works because Mort emits all prototypes first, so call
   order across "modules" doesn't matter — but there's no namespacing, and every
   global (`g_our_ip`, `g_rtl_rxbuf`, ...) shares one flat scope. A real module
   system (or even a documented multi-file compile) is the biggest missing
   ergonomic feature now.

2. **M2 needed no new language features.** After M1 added `inl/outl`, the whole
   IPv4 + ARP + ICMP layer and the RX ring compiled with what Mort already had:
   fixed-width ints, pointers, structs-free byte poking through `u64` addresses,
   and `&&`/`||` in conditions. That's a good sign the core is capable — the
   friction is now ergonomics (modules, `&arr[i]`, `const`), not capability.

3. **`%` and unsigned wrap both behave.** The RX ring cursor uses
   `(off + advance) % 8192` and `(off - 16) as u16` (deliberate wrap to 0xFFF0
   for the card's CAPR quirk); both generated correct C. Handy to have
   confirmed for the sliding-window arithmetic coming in M5 (TCP).

## From M1 (NIC driver)

1. **The language was missing 32-bit port I/O.** Mort v0.7 had `inb/outb`
   and `inw/outw`, but PCI configuration space is addressed through a dword
   register pair on ports `0xCF8`/`0xCFC`, which needs `inl/outl`. Added them
   to the compiler (typechecker + codegen, emitted only when used, 5 new
   tests) — the first time mortnet drove a change to Mort itself. Committed
   upstream in the Mort repo.

2. **Pointer-to-`u32` casts warn but are correct on the 32-bit target.**
   `&g_rtl_txbuf as u32` triggers `-Wpointer-to-int-cast`, exactly like the
   MORT OS ATA driver's `buf as u32`. Harmless: the kernel is 32-bit with
   identity-mapped memory, so a pointer *is* a `u32`. A future `--freestanding`
   host-word-size note or a `ptr_addr()` intrinsic could silence it.

3. **Polled TX needs no interrupts**, which let the demo kernel skip the
   GDT/IDT entirely and use a 30-line boot stub — so the M1 demo is
   self-contained in `demo/` and doesn't fork MORT OS's 1800-line kernel.

## From M0 (foundations)

1. **`&arr[i]` is not addressable.** Mort v0.7 can take the address of a
   variable but not of an array element. mortnet's answer: all buffer APIs
   trade in `u64` addresses (`buf_addr(slot)`), the same idiom the kernel
   uses for hardware memory. A future `&arr[i]` (or slices) would make the
   call sites prettier.

2. **Repeat initializers materialize every element.** `[0; 12800]` emits
   12,800 literal zeros into the generated C (~50 KB of text for the packet
   pool). Harmless but ugly; zero-init elision in codegen (`{0}` or a
   `memset`-free static) is an easy compiler win.

3. **No `const`.** Slot size (1600) and slot count (8) appear as literals
   with comments instead of named compile-time constants. Top-level `let`
   works but is mutable state, not a constant.

4. **Struct layout follows C, padding included.** Verified empirically:
   `struct { used: u8, len: u16, data: [u8; 16] }` puts `data` at offset 4.
   mortnet avoids offset arithmetic into structs regardless — parsing
   happens through the `be16_load`/`be32_load` helpers.

5. **What already worked without a single fight:** fixed-width unsigned
   types with proper wrap semantics, bitwise ops keeping their width
   (`swap16` emits fully-cast C), global arrays as static storage, range
   `for` with typed counters, and `--emit-c` as a zero-dependency
   front-end test. The checksum and endian modules compiled correctly on
   the first try.
