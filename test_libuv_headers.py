#!/usr/bin/env python3
"""Compile Node 24.17.0's exact libuv public header for x86_64-mortos."""

from pathlib import Path
import subprocess
import sys

import mortc


HERE = Path(__file__).resolve().parent
LIBUV = HERE / "third_party" / "libuv"
SYSROOT = HERE / "build" / "x86_64" / "sysroot"
PLATFORM = HERE / "ports" / "libuv" / "mortos_platform.h"
PROBE = HERE / "ports" / "libuv" / "header_probe.c"
PROBE_OBJECT = HERE / "build" / "x86_64" / "libuv-header-probe.o"
EXPECTED_REVISION = "1cfa32ff59c076ffb6ed735bbc8c18361558661f"


def main() -> None:
    subprocess.run(
        [sys.executable, str(HERE / "build.py"), "check64"], check=True)
    revision = subprocess.check_output(
        ["git", "-C", str(LIBUV), "rev-parse", "HEAD"], text=True).strip()
    if revision != EXPECTED_REVISION:
        raise SystemExit(
            f"libuv revision mismatch: {revision} != {EXPECTED_REVISION}")

    compiler = mortc.find_zig()
    if not compiler:
        raise SystemExit("libuv header test needs the Zig backend")
    subprocess.run(
        [
            *compiler,
            "-target", "x86_64-freestanding-none",
            "-ffreestanding", "-fno-builtin",
            "-D__MORTOS__=1",
            "-include", str(PLATFORM),
            "-isystem", str(SYSROOT / "include"),
            "-I", str(LIBUV / "include"),
            "-x", "c", "-c", str(PROBE),
            "-o", str(PROBE_OBJECT),
        ],
        check=True,
    )
    print("OK: libuv 1.52.1 public headers compile for x86_64-mortos")


if __name__ == "__main__":
    main()
