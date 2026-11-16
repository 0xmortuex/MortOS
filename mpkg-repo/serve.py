#!/usr/bin/env python3
"""Serve the mort-repo over plain HTTP for `mpkg` on MORT OS.

MORT OS has no TLS yet, so it can't fetch from HTTPS hosts like GitHub Pages.
This serves the repo over HTTP on port 8000. From MORT OS running under QEMU
user-mode networking, the host is reachable at 10.0.2.2, so `mpkg` points at
    http://10.0.2.2:8000/
and downloads /index and /packages/<file>.

    python serve.py            # serve on 0.0.0.0:8000

For real deployment you'd host the same files behind any plain-HTTP endpoint
(or add TLS to MORT OS down the line).
"""
import http.server
import os
import socketserver

PORT = 8000
os.chdir(os.path.dirname(os.path.abspath(__file__)))


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("  ", self.address_string(), "-", fmt % args)


with socketserver.TCPServer(("0.0.0.0", PORT), Handler) as httpd:
    print(f"mort-repo serving on http://0.0.0.0:{PORT}/  "
          f"(MORT OS reaches it at http://10.0.2.2:{PORT}/)")
    httpd.serve_forever()
