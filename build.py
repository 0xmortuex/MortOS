#!/usr/bin/env python3
"""Build (and optionally boot) the MORT OS kernel.

    python build.py build     # compile + link -> build/kernel.elf
    python build.py check     # build, then verify it's a valid multiboot kernel
    python build.py run       # build, then boot it fullscreen in QEMU
    python build.py window    # same, but in a normal window
    python build.py iso       # build a bootable mort.iso (Limine + xorriso)
    python build.py run-iso   # build the ISO, then boot it in QEMU (-cdrom)
    python build.py disk      # create build/disk.img (MortFS) iff missing
    python build.py prog      # compile programs/*.mx -> build/*.bin
    python build.py build64   # build parallel x86-64 migration kernel
    python build.py check64   # verify the x86-64 ELF + Multiboot header
    python build.py run64     # boot the x86-64 migration kernel in QEMU

The kernel is written in Mort (kmain.mx). This script compiles it to freestanding
C with the Mort compiler, cross-compiles that plus the boot stub to 32-bit x86
with the Zig backend, and links them with linker.ld into a multiboot ELF.

The Mort compiler lives in its own repo. This script honors an explicit
$MORT_HOME override; otherwise it uses the pinned repo-local ./.mort toolchain.
If the cache is absent, the proven compiler tag is cloned automatically.
"""
import os
import hashlib
import json
import shutil
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = HERE
MORT_REPO = "https://github.com/0xmortuex/Mort"
MORT_KERNEL_VERSION = "0.18.0"
MORT_KERNEL_TAG = "v0.18.0"


def _find_mort():
    override = os.environ.get("MORT_HOME")
    if override:
        if os.path.isfile(os.path.join(override, "mortc.py")):
            return override
        sys.exit(f"MORT_HOME does not contain mortc.py: {override}")

    dest = os.path.join(HERE, ".mort")
    if os.path.isfile(os.path.join(dest, "mortc.py")):
        version_file = os.path.join(dest, "mort", "__init__.py")
        version = ""
        if os.path.isfile(version_file):
            with open(version_file, encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("__version__"):
                        parts = line.split('"')
                        if len(parts) >= 2:
                            version = parts[1]
                        break
        if version != MORT_KERNEL_VERSION:
            sys.exit(
                f"repo-local Mort is {version or 'unknown'}, but the kernel "
                f"requires {MORT_KERNEL_VERSION}. Run: "
                f"git -C .mort checkout --detach {MORT_KERNEL_TAG}")
        return dest

    print(f"Mort compiler not found -- cloning {MORT_REPO} {MORT_KERNEL_TAG} "
          "into .mort/ ...")
    subprocess.run([
        "git", "clone", "--branch", MORT_KERNEL_TAG, "--depth", "1",
        MORT_REPO, dest,
    ], check=True)
    return dest


sys.path.insert(0, _find_mort())

import mortc  # noqa: E402

TARGET = "x86-freestanding-none"           # 32-bit x86, bare metal
TARGET64 = "x86_64-freestanding-none"      # 64-bit x86, bare metal
BUILD = os.path.join(HERE, "build")
ELF = os.path.join(BUILD, "kernel.elf")
BUILD64 = os.path.join(BUILD, "x86_64")
ELF64 = os.path.join(BUILD64, "kernel.elf")          # bootable ELF32 trampoline
PAYLOAD64 = os.path.join(BUILD64, "kernel64.elf")   # genuine ELF64 Mort kernel
PAYLOAD64_BIN = os.path.join(BUILD64, "payload.bin")
USER64_ELFS = {
    name: os.path.join(BUILD64, f"user_{name}.elf")
    for name in ("probe", "isolation", "survivor", "preempt")
}
USER64_ELF = USER64_ELFS["probe"]
CXX64_ELF = os.path.join(BUILD64, "user_cxx.elf")
VEXFS64 = os.path.join(BUILD64, "vexfs.bin")
SYSROOT_SOURCE64 = os.path.join(HERE, "sysroot", "x86_64-mortos")
SYSROOT64 = os.path.join(BUILD64, "sysroot")
VEX_EXPECTED_COMMIT = "1b10ec57fa9ebf77ed86c2d5d28f72aad7c1007a"
LIBUV_ROOT = os.path.join(HERE, "third_party", "libuv")
LIBUV_EXPECTED_COMMIT = "1cfa32ff59c076ffb6ed735bbc8c18361558661f"
LIBUV_PLATFORM = os.path.join(HERE, "ports", "libuv", "mortos_platform.h")
LIBUV_SOURCES = (
    "src/uv-common.c",
    "src/uv-data-getter-setters.c",
    "src/version.c",
    "src/timer.c",
    "src/threadpool.c",
    "src/unix/async.c",
    "src/unix/core.c",
    "src/unix/loop.c",
    "src/unix/loop-watcher.c",
    "src/unix/no-proctitle.c",
    "src/unix/pipe.c",
    "src/unix/poll.c",
    "src/unix/posix-hrtime.c",
    "src/unix/posix-poll.c",
    "src/unix/process.c",
    "src/unix/signal.c",
    "src/unix/stream.c",
    "src/unix/thread.c",
    "src/unix/udp.c",
)
DISK = os.path.join(BUILD, "disk.img")

# User programs: compiled from programs/*.mx into flat binaries the kernel
# loads at 0x00A00000 and enters at byte 0 (see programs/prog.ld / pstart.s).
PROGRAMS = os.path.join(HERE, "programs")
PROGRAMS64 = os.path.join(HERE, "programs64")


def _vex_source():
    """Locate and verify the canonical Vex source pinned by this port."""
    candidate = os.environ.get("MORTOS_VEX_SOURCE")
    if not candidate:
        candidate = os.path.join(os.path.dirname(HERE), "Vex")
    candidate = os.path.abspath(candidate)
    package = os.path.join(candidate, "package.json")
    if not os.path.isfile(package):
        sys.exit(
            "x86-64 Vex build needs the canonical Vex checkout; set "
            "MORTOS_VEX_SOURCE or place Vex beside MortOS")
    head = subprocess.run(
        ["git", "-C", candidate, "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True).stdout.strip()
    if head != VEX_EXPECTED_COMMIT:
        sys.exit(
            f"canonical Vex revision mismatch: got {head}, "
            f"expected {VEX_EXPECTED_COMMIT}")
    dirty = subprocess.run(
        ["git", "-C", candidate, "status", "--porcelain",
         "--untracked-files=no"],
        check=True, capture_output=True, text=True).stdout.strip()
    if dirty:
        sys.exit("canonical Vex checkout has tracked modifications; "
                 "package from a clean source tree")
    return candidate


def _build_vexfs():
    """Pack the canonical Electron application files into deterministic VexFS."""
    source = _vex_source()
    relative_files = ["package.json"]
    for root_name in ("src", os.path.join("assets", "theme-previews")):
        root = os.path.join(source, root_name)
        if not os.path.isdir(root):
            continue
        for dirpath, _dirs, files in os.walk(root):
            for filename in files:
                relative_files.append(os.path.relpath(
                    os.path.join(dirpath, filename), source))
    for asset in (os.path.join("assets", "icon.svg"),
                  os.path.join("assets", "icon.ico")):
        if os.path.isfile(os.path.join(source, asset)):
            relative_files.append(asset)

    relative_files = sorted(set(
        path.replace("\\", "/") for path in relative_files))
    archive = bytearray(b"MORTVEX1")
    archive.extend(struct.pack("<II", 1, len(relative_files)))
    for relative in relative_files:
        host_path = os.path.join(source, *relative.split("/"))
        with open(host_path, "rb") as fh:
            payload = fh.read()
        guest_path = ("/app/vex/" + relative).encode("utf-8")
        if len(guest_path) > 0xFFFF or len(payload) > 0xFFFFFFFF:
            sys.exit(f"VexFS entry is too large: {relative}")
        archive.extend(struct.pack("<HHI", len(guest_path), 0, len(payload)))
        archive.extend(hashlib.sha256(payload).digest())
        archive.extend(guest_path)
        archive.extend(payload)
        while len(archive) % 8:
            archive.append(0)
    with open(VEXFS64, "wb") as fh:
        fh.write(archive)
    print(
        f"built {os.path.relpath(VEXFS64, ROOT)} "
        f"({len(relative_files)} canonical Vex files at "
        f"{VEX_EXPECTED_COMMIT[:7]})")
    return bytes(archive)

# Bootable-ISO tooling (downloaded + cached once under kernel/tools/).
TOOLS = os.path.join(HERE, "tools")
ISO = os.path.join(BUILD, "mort.iso")
# Limine boots our multiboot1 kernel unchanged; both tools are portable Windows
# .exe files, so no WSL/MSYS2 is needed. Pinned to a stable Limine branch.
LIMINE_ZIP = "https://github.com/limine-bootloader/limine/archive/refs/heads/v8.x-binary.zip"
XORRISO_ZIP = "https://github.com/PeyTy/xorriso-exe-for-windows/archive/refs/heads/master.zip"
LIMINE_CONF = """timeout: 3

/MORT OS
    protocol: multiboot1
    path: boot():/boot/kernel.elf
    module_path: boot():/boot/welcome.txt
    module_path: boot():/boot/startup.txt
"""

# Files staged onto the ISO and loaded as multiboot modules. Module 0
# (welcome.txt) is shown by `readme`; module 1 (startup.txt) is a script of
# shell commands the kernel runs at boot, like an /etc/rc.
WELCOME_TXT = """Welcome to MORT OS.

You are looking at a file that lived on the ISO, was loaded from disk by the
Limine bootloader as a multiboot module, and is now being read by the kernel.

Everything here -- the kernel, its shell, and the Mort language it is written
in -- was built from scratch. Type 'help' for commands.
"""

STARTUP_TXT = """echo running startup script loaded from disk...
about
"""

# Seeded onto a fresh MortFS disk image so first boot's `ls` shows something.
HELLO_TXT = "this file lives on the MortFS disk\n"


def _zig():
    # The kernel cross-compiles to 32-bit x86, so it needs Zig specifically —
    # not whatever host cc find_c_compiler() would prefer.
    cc = mortc.find_zig()
    if not cc:
        sys.exit("kernel build needs the Zig backend — run: pip install ziglang")
    return cc


def build():
    os.makedirs(BUILD, exist_ok=True)
    cc = _zig()

    # 1. Mort kernel -> freestanding C. The kernel is kmain.mx plus the vendored
    # mortnet network stack in net/*.mx (ordered so declarations resolve; Mort
    # emits prototypes first, so calls across files work regardless). All one
    # translation unit, compiled together.
    net_dir = os.path.join(HERE, "net")
    net_src = ""
    if os.path.isdir(net_dir):
        for name in sorted(os.listdir(net_dir)):
            if name.endswith(".mx"):
                with open(os.path.join(net_dir, name), encoding="utf-8") as fh:
                    net_src += fh.read() + "\n"
    with open(os.path.join(HERE, "kmain.mx"), encoding="utf-8") as fh:
        combined = net_src + fh.read()
    c_source = mortc.compile_to_c(combined, freestanding=True)
    kmain_c = os.path.join(BUILD, "kmain.c")
    with open(kmain_c, "w", encoding="utf-8") as fh:
        fh.write(c_source)

    # -mno-sse/-mmx: the kernel runs with SSE disabled (CR4.OSFXSR=0). At -O2 the
    # compiler can vectorize a memset/zero-init to xorps, which would #UD; forbid
    # vector codegen so the network buffers stay scalar. (See mortnet notes.)
    c_flags = ["-target", TARGET, "-ffreestanding", "-fno-builtin", "-fno-stack-protector",
               "-fno-pie", "-fno-asynchronous-unwind-tables", "-fno-unwind-tables",
               "-mno-sse", "-mno-sse2", "-mno-mmx", "-O2"]
    asm_flags = ["-target", TARGET, "-fno-pie"]  # assembling needs no C flags
    kmain_o = os.path.join(BUILD, "kmain.o")
    runtime_o = os.path.join(BUILD, "runtime.o")
    boot_o = os.path.join(BUILD, "boot.o")
    idt_o = os.path.join(BUILD, "idt.o")

    # 2. Compile the kernel C and assemble the boot + interrupt stubs.
    subprocess.run([*cc, *c_flags, "-c", kmain_c, "-o", kmain_o], check=True)
    subprocess.run([*cc, *c_flags, "-c", os.path.join(HERE, "runtime.c"),
                    "-o", runtime_o], check=True)
    subprocess.run([*cc, *asm_flags, "-c", os.path.join(HERE, "boot.s"), "-o", boot_o],
                   check=True)
    subprocess.run([*cc, *asm_flags, "-c", os.path.join(HERE, "idt.s"), "-o", idt_o],
                   check=True)

    # 3. Link into a static, non-PIE multiboot ELF using our linker script.
    subprocess.run([
        *cc, "-target", TARGET, "-nostdlib", "-static", "-no-pie",
        "-Wl,-T," + os.path.join(HERE, "linker.ld"),
        "-Wl,--build-id=none",
        "-o", ELF, boot_o, kmain_o, runtime_o, idt_o,
    ], check=True)
    print(f"built {os.path.relpath(ELF, ROOT)}")


def build64():
    """Build the parallel x86-64 migration kernel.

    Multiboot still enters through a small 32-bit assembly trampoline. It
    enables long mode and calls a Mort-compiled 64-bit kernel entry. Keeping
    this separate from ``build`` preserves the working 32-bit desktop while
    drivers and userspace move across in tested slices.
    """
    os.makedirs(BUILD64, exist_ok=True)
    sysroot_include = os.path.join(SYSROOT64, "include")
    sysroot_lib = os.path.join(SYSROOT64, "lib")
    os.makedirs(sysroot_lib, exist_ok=True)
    shutil.copytree(
        os.path.join(SYSROOT_SOURCE64, "include"),
        sysroot_include,
        dirs_exist_ok=True,
    )
    libuv_head = subprocess.run(
        ["git", "-C", LIBUV_ROOT, "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True).stdout.strip()
    if libuv_head != LIBUV_EXPECTED_COMMIT:
        sys.exit(
            f"libuv revision mismatch: got {libuv_head}, "
            f"expected {LIBUV_EXPECTED_COMMIT}")
    vexfs = _build_vexfs()
    cc = _zig()
    arch = os.path.join(HERE, "arch", "x86_64")

    c_flags = [
        "-target", TARGET64, "-ffreestanding", "-fno-builtin",
        "-fno-stack-protector", "-fno-pie", "-fno-asynchronous-unwind-tables",
        "-fno-unwind-tables", "-mno-red-zone", "-mno-sse", "-mno-sse2",
        "-mno-mmx", "-O2",
    ]
    asm_flags = ["-target", TARGET64, "-fno-pie"]

    # Build four separate Mort ELF64 processes. The kernel embeds each complete
    # executable, validates it, and loads it into an independent address space.
    user_start_o = os.path.join(BUILD64, "user_pstart.o")
    user_syscall_o = os.path.join(BUILD64, "user_syscall.o")
    user_runtime_o = os.path.join(BUILD64, "user_runtime.o")
    subprocess.run([*cc, *c_flags, "-c", os.path.join(HERE, "runtime.c"),
                    "-o", user_runtime_o], check=True)
    subprocess.run([*cc, *asm_flags, "-c",
                    os.path.join(PROGRAMS64, "pstart.s"),
                    "-o", user_start_o], check=True)
    subprocess.run([*cc, *asm_flags, "-c",
                    os.path.join(PROGRAMS64, "syscall.s"),
                    "-o", user_syscall_o], check=True)
    for user_name, user_elf in USER64_ELFS.items():
        with open(os.path.join(PROGRAMS64, user_name + ".mx"),
                  encoding="utf-8") as fh:
            user_c_source = mortc.compile_to_c(
                fh.read(), freestanding=True)
        user_c = os.path.join(BUILD64, "user_" + user_name + ".c")
        user_o = os.path.join(BUILD64, "user_" + user_name + ".o")
        with open(user_c, "w", encoding="utf-8") as fh:
            fh.write(user_c_source)
        subprocess.run([*cc, *c_flags, "-c", user_c, "-o", user_o],
                       check=True)
        subprocess.run([
            *cc, "-target", TARGET64, "-nostdlib", "-static", "-no-pie",
            "-Wl,-T," + os.path.join(PROGRAMS64, "prog.ld"),
            "-Wl,--build-id=none", "-Wl,-e,_user_start",
            "-o", user_elf, user_start_o, user_syscall_o, user_o,
            user_runtime_o,
        ], check=True)

    # Build a separately linked freestanding C++ process. This is the first
    # executable consumer of the x86_64-mortos C/C++ runtime layer.
    cxx = cc[:-1] + ["c++"]
    ar = cc[:-1] + ["ar"]
    cxx_flags = [
        *c_flags, "-fno-exceptions", "-fno-rtti",
        "-fno-threadsafe-statics", "-isystem", sysroot_include,
    ]
    cxx_start_o = os.path.join(BUILD64, "user_cxx_start.o")
    cxx_runtime_o = os.path.join(BUILD64, "user_cxx_runtime.o")
    libc_o = os.path.join(BUILD64, "user_libc.o")
    cxx_probe_o = os.path.join(BUILD64, "user_cxx_probe.o")
    libuv_objects = []
    libuv_object_dir = os.path.join(BUILD64, "libuv")
    os.makedirs(libuv_object_dir, exist_ok=True)
    libuv_flags = [
        "-target", TARGET64, "-ffreestanding", "-fno-builtin",
        "-fno-stack-protector", "-fno-pie",
        "-fno-asynchronous-unwind-tables", "-fno-unwind-tables",
        "-mno-red-zone", "-mno-sse", "-mno-sse2", "-mno-mmx", "-O2",
        "-ffunction-sections", "-fdata-sections",
        "-D__MORTOS__=1", "-D_GNU_SOURCE=1",
        "-include", LIBUV_PLATFORM,
        "-isystem", sysroot_include,
        "-I", os.path.join(LIBUV_ROOT, "include"),
        "-I", os.path.join(LIBUV_ROOT, "src"),
    ]
    for source in LIBUV_SOURCES:
        source_path = os.path.join(LIBUV_ROOT, *source.split("/"))
        object_name = source.replace("/", "_").removesuffix(".c") + ".o"
        object_path = os.path.join(libuv_object_dir, object_name)
        subprocess.run(
            [*cc, *libuv_flags, "-c", source_path, "-o", object_path],
            check=True,
        )
        libuv_objects.append(object_path)
    libuv = os.path.join(sysroot_lib, "libuv.a")
    subprocess.run([*ar, "rcs", libuv, *libuv_objects], check=True)
    subprocess.run([*cc, *asm_flags, "-c",
                    os.path.join(PROGRAMS64, "cxx_start.s"),
                    "-o", cxx_start_o], check=True)
    subprocess.run([*cxx, *cxx_flags, "-c",
                    os.path.join(PROGRAMS64, "cxx_runtime.cpp"),
                    "-o", cxx_runtime_o], check=True)
    subprocess.run([*cxx, *cxx_flags, "-c",
                    os.path.join(PROGRAMS64, "libc.cpp"),
                    "-o", libc_o], check=True)
    probe_flags = [
        *cxx_flags, "-fstack-protector-all",
        "-D__MORTOS__=1", "-include", LIBUV_PLATFORM,
        "-isystem", os.path.join(LIBUV_ROOT, "include"),
    ]
    subprocess.run([*cxx, *probe_flags, "-c",
                    os.path.join(PROGRAMS64, "cxx_probe.cpp"),
                    "-o", cxx_probe_o], check=True)
    crt1 = os.path.join(sysroot_lib, "crt1.o")
    libmortos = os.path.join(sysroot_lib, "libmortos.a")
    shutil.copy2(cxx_start_o, crt1)
    subprocess.run([
        *ar, "rcs", libmortos,
        user_syscall_o, cxx_runtime_o, libc_o, user_runtime_o,
    ], check=True)
    subprocess.run([
        *cc, "-target", TARGET64, "-nostdlib", "-static", "-no-pie",
        "-Wl,-T," + os.path.join(PROGRAMS64, "prog.ld"),
        "-Wl,--build-id=none", "-Wl,--gc-sections", "-Wl,-e,_user_start",
        "-o", CXX64_ELF, crt1, cxx_probe_o, libuv, libmortos,
    ], check=True)

    # Invalidate Zig's .incbin cache whenever the userspace ELF changes.
    user_hasher = hashlib.sha256()
    for user_elf in [*USER64_ELFS.values(), CXX64_ELF]:
        with open(user_elf, "rb") as fh:
            user_hasher.update(fh.read())
    user_hasher.update(vexfs)
    user_digest = user_hasher.hexdigest()
    with open(os.path.join(arch, "user_blob.s"), encoding="utf-8") as fh:
        user_blob_source = fh.read()
    generated_user_blob = os.path.join(BUILD64, "user_blob.generated.s")
    with open(generated_user_blob, "w", encoding="utf-8") as fh:
        fh.write(f"/* embedded userspace sha256: {user_digest} */\n")
        fh.write(user_blob_source)

    with open(os.path.join(arch, "kernel64.mx"), encoding="utf-8") as fh:
        c_source = mortc.compile_to_c(fh.read(), freestanding=True)
    kernel_c = os.path.join(BUILD64, "kernel64.c")
    with open(kernel_c, "w", encoding="utf-8") as fh:
        fh.write(c_source)

    kernel_o = os.path.join(BUILD64, "kernel64.o")
    runtime_o = os.path.join(BUILD64, "runtime.o")
    entry_o = os.path.join(BUILD64, "entry64.o")
    cpu_o = os.path.join(BUILD64, "cpu64.o")
    user_blob_o = os.path.join(BUILD64, "user_blob.o")
    boot_o = os.path.join(BUILD64, "boot.o")

    subprocess.run([*cc, *c_flags, "-c", kernel_c, "-o", kernel_o], check=True)
    subprocess.run([*cc, *c_flags, "-c", os.path.join(HERE, "runtime.c"),
                    "-o", runtime_o], check=True)
    subprocess.run([*cc, *asm_flags, "-c", os.path.join(arch, "entry64.s"),
                    "-o", entry_o], check=True)
    subprocess.run([*cc, *asm_flags, "-c", os.path.join(arch, "cpu64.s"),
                    "-o", cpu_o], check=True)
    subprocess.run([*cc, *asm_flags, "-c", generated_user_blob,
                    "-o", user_blob_o], cwd=HERE, check=True)
    subprocess.run([
        *cc, "-target", TARGET64, "-nostdlib", "-static", "-no-pie",
        "-Wl,-T," + os.path.join(arch, "linker.ld"),
        "-Wl,--build-id=none", "-Wl,-e,_payload_start",
        "-o", PAYLOAD64, entry_o, cpu_o, user_blob_o, kernel_o, runtime_o,
    ], check=True)

    objcopy = cc[:-1] + ["objcopy"]
    subprocess.run([*objcopy, "-O", "binary", PAYLOAD64, PAYLOAD64_BIN], check=True)

    # QEMU's direct Multiboot loader requires an i386 ELF container. Its only
    # job is to enter long mode and jump to the embedded ELF64 payload. Zig's
    # compiler cache does not track .incbin contents, so generate a wrapper
    # whose text includes the payload digest and necessarily invalidates the
    # cached assembly object when the 64-bit kernel changes.
    with open(PAYLOAD64_BIN, "rb") as fh:
        payload_digest = hashlib.sha256(fh.read()).hexdigest()
    with open(os.path.join(arch, "boot.s"), encoding="utf-8") as fh:
        boot_source = fh.read()
    generated_boot = os.path.join(BUILD64, "bootstrap.generated.s")
    with open(generated_boot, "w", encoding="utf-8") as fh:
        fh.write(f"/* embedded payload sha256: {payload_digest} */\n")
        fh.write(boot_source)

    asm32_flags = ["-target", TARGET, "-fno-pie"]
    subprocess.run([*cc, *asm32_flags, "-c", generated_boot,
                    "-o", boot_o], cwd=HERE, check=True)
    subprocess.run([
        *cc, "-target", TARGET, "-nostdlib", "-static", "-no-pie",
        "-Wl,-T," + os.path.join(arch, "bootstrap.ld"),
        "-Wl,--build-id=none", "-Wl,-e,_start64",
        "-o", ELF64, boot_o,
    ], check=True)
    print(f"built {os.path.relpath(PAYLOAD64, ROOT)} (ELF64 Mort kernel)")
    for user_elf in USER64_ELFS.values():
        print(f"built {os.path.relpath(user_elf, ROOT)} (ELF64 Mort userspace)")
    print(f"built {os.path.relpath(CXX64_ELF, ROOT)} (ELF64 C++ userspace)")
    print(f"built {os.path.relpath(SYSROOT64, ROOT)} "
          "(x86_64-mortos bootstrap sysroot)")
    print(f"built {os.path.relpath(ELF64, ROOT)} (Multiboot trampoline + payload)")


def check64():
    """Validate the parallel kernel without weakening the 32-bit checks."""
    build64()
    with open(PAYLOAD64, "rb") as fh:
        payload = fh.read()
    with open(ELF64, "rb") as fh:
        bootstrap = fh.read()

    def require(cond, msg):
        if not cond:
            sys.exit(f"x86-64 kernel check FAILED: {msg}")

    sysroot_header = os.path.join(
        SYSROOT64, "include", "mortos", "syscall.h")
    sysroot_stdlib = os.path.join(SYSROOT64, "include", "stdlib.h")
    sysroot_crt = os.path.join(SYSROOT64, "lib", "crt1.o")
    sysroot_library = os.path.join(SYSROOT64, "lib", "libmortos.a")
    for required_sysroot_file in (
        sysroot_header, sysroot_stdlib, sysroot_crt, sysroot_library,
    ):
        require(os.path.isfile(required_sysroot_file),
                f"bootstrap sysroot is missing {required_sysroot_file}")
    with open(sysroot_header, "rb") as fh:
        syscall_header = fh.read()
    require(b"mortos_epoll_wait" in syscall_header
            and b"mortos_getrandom" in syscall_header,
            "bootstrap syscall header is incomplete")
    with open(sysroot_library, "rb") as fh:
        require(fh.read(8) == b"!<arch>\n",
                "libmortos.a is not a static archive")

    require(payload[:4] == b"\x7fELF", "payload is not an ELF file")
    require(payload[4] == 2, "kernel payload is not ELFCLASS64")
    machine = struct.unpack("<H", payload[18:20])[0]
    require(machine == 0x3E, f"expected EM_X86_64 (0x3e), got {hex(machine)}")
    entry = struct.unpack("<Q", payload[24:32])[0]
    require(entry == 0x200000,
            f"ELF64 payload entry is {hex(entry)}, expected 0x200000")

    magic_value = 0x1BADB002
    require(bootstrap[:4] == b"\x7fELF", "bootstrap is not an ELF file")
    require(bootstrap[4] == 1, "Multiboot bootstrap is not ELFCLASS32")
    bootstrap_machine = struct.unpack("<H", bootstrap[18:20])[0]
    require(bootstrap_machine == 0x03, "Multiboot bootstrap is not EM_386")
    head = bootstrap[:8192]
    offset = -1
    for i in range(0, len(head) - 11, 4):
        if struct.unpack("<I", head[i:i + 4])[0] == magic_value:
            offset = i
            break
    require(offset >= 0, "Multiboot header not found in the first 8 KiB")
    magic, flags, checksum = struct.unpack("<III", head[offset:offset + 12])
    require(flags == 0x3,
            f"unexpected Multiboot flags {hex(flags)} (want ALIGN|MEMINFO = 0x3)")
    require((magic + flags + checksum) & 0xFFFFFFFF == 0,
            "Multiboot checksum is invalid")

    with open(PAYLOAD64_BIN, "rb") as fh:
        payload_bin = fh.read()
    require(payload_bin and payload_bin in bootstrap,
            "ELF64 payload is not embedded in the Multiboot image")

    checked_users = {**USER64_ELFS, "cxx": CXX64_ELF}
    for user_name, user_path in checked_users.items():
        with open(user_path, "rb") as fh:
            user_elf = fh.read()
        require(user_elf[:4] == b"\x7fELF" and user_elf[4] == 2,
                f"userspace {user_name} is not ELFCLASS64")
        user_machine = struct.unpack("<H", user_elf[18:20])[0]
        require(user_machine == 0x3E,
                f"userspace {user_name} is not EM_X86_64")
        user_entry = struct.unpack("<Q", user_elf[24:32])[0]
        require(user_entry == 0x01000000,
                f"{user_name} entry is {hex(user_entry)}, expected 0x01000000")
        user_phoff = struct.unpack("<Q", user_elf[32:40])[0]
        user_phentsize = struct.unpack("<H", user_elf[54:56])[0]
        user_phnum = struct.unpack("<H", user_elf[56:58])[0]
        require(user_phentsize >= 56 and 0 < user_phnum <= 32,
                f"userspace {user_name} has an invalid program-header table")
        require(user_phoff + user_phentsize * user_phnum <= len(user_elf),
                f"userspace {user_name} program headers exceed the file")
        load_segments = 0
        for index in range(user_phnum):
            header = user_phoff + index * user_phentsize
            segment_type, flags = struct.unpack(
                "<II", user_elf[header:header + 8])
            if segment_type != 1:
                continue
            load_segments += 1
            virtual_address = struct.unpack(
                "<Q", user_elf[header + 16:header + 24])[0]
            memory_size = struct.unpack(
                "<Q", user_elf[header + 40:header + 48])[0]
            require(not (flags & 1 and flags & 2),
                    f"userspace {user_name} has a writable+executable segment")
            require(0x01000000 <= virtual_address
                    and virtual_address + memory_size <= 0x01100000,
                    f"userspace {user_name} segment is outside process window")
        require(load_segments > 0,
                f"userspace {user_name} has no PT_LOAD segments")
        require(user_elf in payload_bin,
                f"userspace {user_name} is not embedded in kernel payload")

    with open(VEXFS64, "rb") as fh:
        vexfs = fh.read()
    require(vexfs[:8] == b"MORTVEX1" and len(vexfs) >= 16,
            "canonical VexFS header is invalid")
    vexfs_version, vexfs_count = struct.unpack("<II", vexfs[8:16])
    require(vexfs_version == 1 and 0 < vexfs_count <= 4096,
            "canonical VexFS version/count is invalid")
    cursor = 16
    vex_files = {}
    previous_path = ""
    for _index in range(vexfs_count):
        require(cursor + 40 <= len(vexfs), "VexFS entry header is truncated")
        path_length, entry_flags, data_length = struct.unpack(
            "<HHI", vexfs[cursor:cursor + 8])
        digest = vexfs[cursor + 8:cursor + 40]
        path_start = cursor + 40
        data_start = path_start + path_length
        data_end = data_start + data_length
        require(path_length > 0 and entry_flags == 0
                and data_start >= path_start and data_end >= data_start
                and data_end <= len(vexfs), "VexFS entry bounds are invalid")
        path = vexfs[path_start:data_start].decode("utf-8")
        payload = vexfs[data_start:data_end]
        require(path > previous_path, "VexFS paths are not unique and sorted")
        require(hashlib.sha256(payload).digest() == digest,
                f"VexFS digest mismatch for {path}")
        vex_files[path] = payload
        previous_path = path
        cursor = (data_end + 7) & ~7
    require(cursor == len(vexfs), "VexFS has trailing or misaligned data")
    for required_vex_path in (
        "/app/vex/package.json",
        "/app/vex/src/main.js",
        "/app/vex/src/renderer/start.html",
    ):
        require(required_vex_path in vex_files,
                f"VexFS is missing {required_vex_path}")
    package = json.loads(vex_files["/app/vex/package.json"])
    require(package.get("name") == "vex"
            and package.get("version") == "2.28.1"
            and package.get("main") == "src/main.js",
            "VexFS package identity does not match canonical Vex 2.28.1")
    require(vexfs in payload_bin,
            "canonical VexFS is not embedded in the kernel payload")

    print(f"OK: genuine ELF64 Mort payload at 0x200000")
    print("OK: five isolated W^X ELF64 userspace images at 0x01000000")
    print(f"OK: {vexfs_count} canonical Vex files embedded from "
          f"{VEX_EXPECTED_COMMIT[:7]}")
    print(f"OK: ELF32 Multiboot trampoline; valid header at file offset {offset}")
    print("OK: ELF64 payload embedded in the bootable image")
    print("Boot it with:  python build.py run64")


def check():
    build()
    with open(ELF, "rb") as fh:
        data = fh.read()

    # Explicit raises (not assert) so `python -O` can't silently skip validation.
    def require(cond, msg):
        if not cond:
            sys.exit(f"kernel check FAILED: {msg}")

    require(data[:4] == b"\x7fELF", "output is not an ELF file")
    require(data[4] == 1, "expected a 32-bit (ELFCLASS32) kernel")
    machine = struct.unpack("<H", data[18:20])[0]
    require(machine == 0x03, f"expected EM_386 (0x03), got {hex(machine)}")

    # Validate the whole multiboot header (magic, flags, checksum), 4-byte
    # aligned within the first 8 KiB — not just the magic word.
    MAGIC = 0x1BADB002
    head = data[:8192]
    offset = -1
    for i in range(0, len(head) - 11, 4):
        if struct.unpack("<I", head[i:i + 4])[0] == MAGIC:
            offset = i
            break
    require(offset >= 0, "multiboot magic not found in the first 8 KiB")
    magic, flags, checksum = struct.unpack("<III", head[offset:offset + 12])
    require(flags == 0x7,
            f"unexpected multiboot flags {hex(flags)} (want ALIGN|MEMINFO|GRAPHICS = 0x7)")
    require((magic + flags + checksum) & 0xFFFFFFFF == 0,
            "multiboot checksum invalid (magic + flags + checksum != 0)")

    print(f"OK: 32-bit x86 multiboot ELF; valid header at file offset {offset}")
    print("Boot it with:  python build.py run")


def _fetch_zip(url, dest):
    import io
    import urllib.request
    import zipfile
    os.makedirs(dest, exist_ok=True)
    print(f"  downloading {url} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "mort-build"})
    with urllib.request.urlopen(req) as r:
        data = r.read()
    zipfile.ZipFile(io.BytesIO(data)).extractall(dest)


def _find(root, name):
    for dirpath, _dirs, files in os.walk(root):
        if name in files:
            return os.path.join(dirpath, name)
    return None


def _cygpath(p):
    """Convert a Windows path to the Cygwin form xorriso.exe expects."""
    p = os.path.abspath(p)
    drive, rest = os.path.splitdrive(p)
    return "/cygdrive/" + drive[0].lower() + rest.replace("\\", "/")


def iso():
    """Build a BIOS+UEFI bootable, USB-writable ISO using Limine + xorriso."""
    build()
    os.makedirs(TOOLS, exist_ok=True)

    # 1. Ensure the (portable, Windows) tools are present — download + cache once.
    if not _find(TOOLS, "limine.exe"):
        _fetch_zip(LIMINE_ZIP, os.path.join(TOOLS, "limine"))
    if not _find(TOOLS, "xorriso.exe"):
        _fetch_zip(XORRISO_ZIP, os.path.join(TOOLS, "xorriso"))
    limine = _find(TOOLS, "limine.exe")
    xorriso = _find(TOOLS, "xorriso.exe")
    if not limine or not xorriso:
        sys.exit("iso: could not locate limine.exe / xorriso.exe after download.")
    lim_dir = os.path.dirname(limine)

    # 2. Stage the ISO tree: kernel + Limine boot files + config.
    root = os.path.join(BUILD, "iso_root")
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(os.path.join(root, "boot"), exist_ok=True)
    os.makedirs(os.path.join(root, "EFI", "BOOT"), exist_ok=True)
    shutil.copy(ELF, os.path.join(root, "boot", "kernel.elf"))
    with open(os.path.join(root, "boot", "limine.conf"), "w", encoding="utf-8") as fh:
        fh.write(LIMINE_CONF)
    with open(os.path.join(root, "boot", "welcome.txt"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(WELCOME_TXT)
    with open(os.path.join(root, "boot", "startup.txt"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(STARTUP_TXT)
    for name in ("limine-bios.sys", "limine-bios-cd.bin", "limine-uefi-cd.bin"):
        src = _find(lim_dir, name)
        if src:
            shutil.copy(src, os.path.join(root, "boot", name))
    for name in ("BOOTX64.EFI", "BOOTIA32.EFI"):
        src = _find(lim_dir, name)
        if src:
            shutil.copy(src, os.path.join(root, "EFI", "BOOT", name))
    if not os.path.exists(os.path.join(root, "boot", "limine-bios-cd.bin")):
        sys.exit("iso: limine-bios-cd.bin not found in the Limine download — "
                 "the release layout may have changed.")

    # 3. Master a hybrid El Torito ISO, then make the BIOS path bootable.
    # xorriso is a Cygwin build, so host paths must be in /cygdrive/... form.
    subprocess.run([
        xorriso, "-as", "mkisofs", "-R", "-r", "-J",
        "-b", "boot/limine-bios-cd.bin",
        "-no-emul-boot", "-boot-load-size", "4", "-boot-info-table",
        "--efi-boot", "boot/limine-uefi-cd.bin",
        "-efi-boot-part", "--efi-boot-image", "--protective-msdos-label",
        _cygpath(root), "-o", _cygpath(ISO),
    ], check=True)
    subprocess.run([limine, "bios-install", ISO], check=True)
    print(f"built {os.path.relpath(ISO, ROOT)}")
    print(f"boot it with:  python build.py run-iso   (or -cdrom {os.path.basename(ISO)})")


def build_program(mx_path, out_bin):
    """Compile one Mort program (programs/*.mx) into a flat binary at out_bin.

    Same proven 4-step recipe as the kernel, but linked with programs/prog.ld
    so the whole image sits at the fixed load base 0x00A00000 with the entry
    stub (pstart.s) first, then objcopy'd to a raw flat binary (no ELF headers).
    Intermediate .c/.o/.elf land in BUILD, never the repo.
    """
    os.makedirs(BUILD, exist_ok=True)
    cc = _zig()
    name = os.path.splitext(os.path.basename(mx_path))[0]

    # 1. Mort program -> freestanding C (main becomes mort_main, which pstart calls).
    with open(mx_path, encoding="utf-8") as fh:
        c_source = mortc.compile_to_c(fh.read(), freestanding=True)
    prog_c = os.path.join(BUILD, name + ".c")
    with open(prog_c, "w", encoding="utf-8") as fh:
        fh.write(c_source)

    c_flags = ["-target", TARGET, "-ffreestanding", "-fno-builtin", "-fno-stack-protector",
               "-fno-pie", "-fno-asynchronous-unwind-tables", "-fno-unwind-tables",
               "-O2"]
    asm_flags = ["-target", TARGET, "-fno-pie"]  # assembling needs no C flags
    prog_o = os.path.join(BUILD, name + ".o")
    runtime_o = os.path.join(BUILD, "runtime.o")
    pstart_o = os.path.join(BUILD, name + ".pstart.o")
    prog_elf = os.path.join(BUILD, name + ".elf")

    # 2. Compile the program C and assemble the entry stub.
    subprocess.run([*cc, *c_flags, "-c", prog_c, "-o", prog_o], check=True)
    subprocess.run([*cc, *c_flags, "-c", os.path.join(HERE, "runtime.c"),
                    "-o", runtime_o], check=True)
    subprocess.run([*cc, *asm_flags, "-c", os.path.join(PROGRAMS, "pstart.s"),
                    "-o", pstart_o], check=True)

    # 3. Link at the fixed load base with the flat-image linker script.
    subprocess.run([
        *cc, "-target", TARGET, "-nostdlib", "-static", "-no-pie",
        "-Wl,-T," + os.path.join(PROGRAMS, "prog.ld"),
        "-Wl,--build-id=none", "-Wl,-e,_pstart",   # entry stub, silences _start warning
        "-o", prog_elf, pstart_o, prog_o, runtime_o,
    ], check=True)

    # 4. Strip ELF headers down to a raw flat binary the kernel loads verbatim.
    objcopy = cc[:-1] + ["objcopy"]  # find_zig() ends in "cc"; swap for "objcopy"
    subprocess.run([*objcopy, "-O", "binary", prog_elf, out_bin], check=True)
    print(f"built {os.path.relpath(out_bin, ROOT)}")


def _program_sources():
    """Return sorted absolute paths of every programs/*.mx source."""
    if not os.path.isdir(PROGRAMS):
        return []
    return [os.path.join(PROGRAMS, n) for n in sorted(os.listdir(PROGRAMS))
            if n.endswith(".mx")]


def prog():
    """Build every programs/*.mx into BUILD/<name>.bin."""
    sources = _program_sources()
    if not sources:
        sys.exit(f"prog: no *.mx programs found in {os.path.relpath(PROGRAMS, ROOT)}")
    for mx in sources:
        name = os.path.splitext(os.path.basename(mx))[0]
        build_program(mx, os.path.join(BUILD, name + ".bin"))


def ensure_disk():
    """Create the MortFS disk image iff it is missing.

    An existing image is never touched, so files written inside the OS persist
    across rebuilds; `python mkfs.py build/disk.img` is the explicit wipe path.
    A fresh image is seeded with the text file plus the compiled program
    binaries (added raw, no CRLF normalization), so first boot can `exec hello.bin`.
    """
    if os.path.exists(DISK):
        return
    os.makedirs(BUILD, exist_ok=True)
    import mkfs  # lives next to this script; sys.path[0] is HERE
    seed = os.path.join(BUILD, "hello.txt")
    with open(seed, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(HELLO_TXT)

    # Compile the programs and seed only the ones that build successfully.
    bins = []
    for mx in _program_sources():
        name = os.path.splitext(os.path.basename(mx))[0]
        out_bin = os.path.join(BUILD, name + ".bin")
        build_program(mx, out_bin)
        bins.append((out_bin, name + ".bin"))

    mkfs.make(DISK, adds=[(seed, "hello.txt")], bins=bins)


def disk():
    if os.path.exists(DISK):
        print(f"{os.path.relpath(DISK, ROOT)} already exists — leaving it alone "
              "(files written in the OS persist). Wipe with: "
              "python mkfs.py build/disk.img")
        return
    ensure_disk()


def run_iso():
    iso()
    ensure_disk()
    qemu = _find_qemu()
    if not qemu:
        sys.exit("qemu-system-i386 not found — install QEMU to boot the ISO.")
    print("Booting the MORT OS ISO in QEMU...")
    subprocess.run([qemu, "-cdrom", ISO, "-hda", DISK])


def _find_qemu():
    found = shutil.which("qemu-system-i386")
    if found:
        return found
    # Windows: QEMU installs here but usually isn't added to PATH.
    import glob
    for pattern in (
        r"C:\Program Files\qemu\qemu-system-i386.exe",
        r"C:\Program Files*\qemu*\qemu-system-i386.exe",
    ):
        hits = glob.glob(pattern)
        if hits:
            return hits[0]
    return None


def _find_qemu64():
    found = shutil.which("qemu-system-x86_64")
    if found:
        return found
    import glob
    for pattern in (
        r"C:\Program Files\qemu\qemu-system-x86_64.exe",
        r"C:\Program Files*\qemu*\qemu-system-x86_64.exe",
    ):
        hits = glob.glob(pattern)
        if hits:
            return hits[0]
    return None


def run64():
    build64()
    qemu = _find_qemu64()
    if not qemu:
        sys.exit("qemu-system-x86_64 not found — install QEMU to boot MORT64.")
    print("Booting the MORT OS x86-64 migration kernel. "
          "Serial boot status is printed in this terminal; Ctrl+C stops QEMU.")
    subprocess.run([
        qemu, "-machine", "q35", "-cpu", "max", "-m", "256M",
        "-display", "none",
        "-serial", "stdio", "-monitor", "none",
        "-netdev", "user,id=mortnet",
        "-device", "rtl8139,netdev=mortnet",
        "-kernel", ELF64,
    ])


def _run(fullscreen):
    build()
    ensure_disk()
    qemu = _find_qemu()
    if not qemu:
        sys.exit("qemu-system-i386 not found — install QEMU (e.g. `winget install "
                 "SoftwareFreedomConservancy.QEMU`) to boot the kernel.")
    # GTK display: hide the menu bar and scale the 80x25 console to the window.
    display = "gtk,zoom-to-fit=on,show-menubar=off"
    cmd = [qemu, "-display", display, "-kernel", ELF, "-hda", DISK]
    if fullscreen:
        cmd.insert(1, "-full-screen")
        print("Booting MORT OS fullscreen. Ctrl+Alt+F toggles fullscreen, "
              "Ctrl+Alt+G releases the mouse, Ctrl+Alt+Q quits.")
    else:
        print("Booting MORT OS. Maximise the window to scale it up; "
              "Ctrl+Alt+G releases the mouse; close the window to exit.")
    # A list argv lets subprocess quote the (space-containing) ELF path for us.
    subprocess.run(cmd)


def run():
    _run(fullscreen=True)


def run_windowed():
    _run(fullscreen=False)


COMMANDS = {
    "build": build, "check": check, "run": run, "window": run_windowed,
    "iso": iso, "run-iso": run_iso, "disk": disk, "prog": prog,
    "build64": build64, "check64": check64, "run64": run64,
}

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd not in COMMANDS:
        sys.exit(f"unknown command {cmd!r}; use one of: {', '.join(COMMANDS)}")
    COMMANDS[cmd]()
