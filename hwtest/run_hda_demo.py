#!/usr/bin/env python3
"""Boot the HDA demo, play a tone, and verify QEMU captured non-silent audio.

Boots under intel-hda + hda-output with a `wav` audiodev writing to a file, then
parses that WAV: the driver plays a ~440 Hz square wave, so the capture must
contain a substantial fraction of loud samples of both polarities (not silence).

    python hwtest/build_hda_demo.py && python hwtest/run_hda_demo.py
"""
import os, struct, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "out")
ELF = os.path.join(OUT, "hda_demo.elf")
WAV = os.path.join(OUT, "hda_out.wav")
sys.path.insert(0, ROOT)
import build as b  # noqa: E402

def run_qemu():
    qemu = b._find_qemu()
    if not qemu:
        sys.exit("qemu-system-i386 not found")
    if os.path.exists(WAV):
        os.remove(WAV)
    cmd = [qemu, "-display", "none", "-serial", "stdio", "-no-reboot",
           "-kernel", ELF,
           "-audiodev", f"wav,id=snd0,path={WAV}",
           "-device", "intel-hda,id=hda0",
           "-device", "hda-output,bus=hda0.0,audiodev=snd0",
           "-device", "isa-debug-exit,iobase=0xf4,iosize=0x04"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        serial = res.stdout
    except subprocess.TimeoutExpired as e:
        serial = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
    print("----- serial log -----"); print(serial.strip()); print("----------------------")
    return serial

def check_wav():
    if not os.path.exists(WAV):
        sys.exit("FAIL: no WAV produced")
    data = open(WAV, "rb").read()
    if len(data) <= 44:
        sys.exit(f"FAIL: WAV has no audio data ({len(data)} bytes)")
    pcm = data[44:]
    n = len(pcm) // 2
    loud = pos = neg = 0
    for i in range(n):
        v = struct.unpack_from("<h", pcm, i * 2)[0]
        if abs(v) > 1000:
            loud += 1
            if v > 0: pos += 1
            else: neg += 1
    print(f"WAV: {len(data)} bytes, {n} samples, loud={loud} (pos={pos} neg={neg})")
    if loud > n * 0.2 and pos > 0 and neg > 0:
        print("PASS: HDA played a non-silent tone captured on the wire")
    else:
        sys.exit("FAIL: captured audio is silent or one-sided")

if __name__ == "__main__":
    serial = run_qemu()
    check_wav()
