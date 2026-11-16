#!/usr/bin/env python3
"""mortnet host test harness.

Mort compiles one file at a time (mortc takes a single .mx), so this script
does what the MORT OS build does: it assembles a translation unit by
concatenating every net/*.mx with one test file, then compiles and runs it
with mortc on the host and checks the printed output.

Each test/test_*.mx declares its expected stdout in header comments:

    //! expect: 13330

Requirements: Python 3.8+, the Mort compiler (found via $MORT_HOME, a
sibling ../Mort checkout, or cloned into .mort/), and any C compiler mortc
can find (cc/gcc/clang, or `pip install ziglang`).
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MORT_REPO = "https://github.com/0xmortuex/Mort"


def find_mort():
    candidates = [
        os.environ.get("MORT_HOME"),
        os.path.join(os.path.dirname(ROOT), "Mort"),
        os.path.join(ROOT, ".mort"),
    ]
    for c in candidates:
        if c and os.path.isfile(os.path.join(c, "mortc.py")):
            return c
    dest = os.path.join(ROOT, ".mort")
    print(f"Mort compiler not found -- cloning {MORT_REPO} into .mort/ ...")
    subprocess.run(["git", "clone", "--depth", "1", MORT_REPO, dest], check=True)
    return dest


def main():
    mort = find_mort()
    mortc = os.path.join(mort, "mortc.py")
    build = os.path.join(ROOT, "build")
    os.makedirs(build, exist_ok=True)

    net_dir = os.path.join(ROOT, "net")
    net_src = ""
    for name in sorted(os.listdir(net_dir)):
        if name.endswith(".mx"):
            with open(os.path.join(net_dir, name), encoding="utf-8") as fh:
                net_src += fh.read() + "\n"

    tests = sorted(
        n for n in os.listdir(HERE) if n.startswith("test_") and n.endswith(".mx")
    )
    failed = 0
    for name in tests:
        with open(os.path.join(HERE, name), encoding="utf-8") as fh:
            test_src = fh.read()
        expected = re.findall(r"^//! expect:\s*(-?\d+)\s*$", test_src, re.M)

        combined = os.path.join(build, name)
        with open(combined, "w", encoding="utf-8") as fh:
            fh.write(net_src + "\n" + test_src)

        out = os.path.join(build, name[:-3])
        proc = subprocess.run(
            [sys.executable, mortc, combined, "--run", "-o", out],
            capture_output=True, text=True,
        )
        got = [ln.strip() for ln in proc.stdout.splitlines()
               if re.fullmatch(r"-?\d+", ln.strip())]

        if proc.returncode != 0:
            print(f"FAIL  {name}  (compile/run error)")
            print(proc.stderr.strip() or proc.stdout.strip())
            failed += 1
        elif got != expected:
            print(f"FAIL  {name}")
            print(f"      expected: {expected}")
            print(f"      got:      {got}")
            failed += 1
        else:
            print(f"PASS  {name}  ({len(expected)} checks)")

    total = len(tests)
    print(f"\n{total - failed}/{total} test programs passed.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
