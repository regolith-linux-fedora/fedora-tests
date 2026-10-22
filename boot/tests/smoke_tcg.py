#!/usr/bin/env python3
"""Plumbing smoke test for machines without KVM (e.g. a Docker container on a Mac).

    boot/tests/smoke_tcg.py --release 44 --arch x86_64 --workdir work/smoke

Downloads and verifies the stock Cloud Base image, boots it under TCG with a minimal cloud-init seed
(user + SSH key, no provisioning), then exercises what the Boot Test relies on: SSH, the loginctl
session parser, and QMP screendump and send-key. It does not install Workstation or log in at GDM;
that needs KVM (see boot/README.md).
"""

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

BOOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BOOT))

import boot_test  # noqa: E402
import build_image  # noqa: E402
from vmtest.vm import VM, make_overlay  # noqa: E402

SEED = """#cloud-config
users:
  - name: tester
    sudo: "ALL=(ALL) NOPASSWD:ALL"
    ssh_authorized_keys: ["{key}"]
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--release", default="44")
    ap.add_argument("--arch", default="x86_64")
    ap.add_argument("--workdir", default="work/smoke")
    ap.add_argument("--timeout", type=int, default=1800)
    args = ap.parse_args()

    work = Path(args.workdir)
    work.mkdir(parents=True, exist_ok=True)
    image, url, sha = build_image.download(args.release, args.arch, work)

    key = work / "id_ed25519"
    if not key.exists():
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
    seed_dir = work / "seed"
    seed_dir.mkdir(exist_ok=True)
    (seed_dir / "user-data").write_text(SEED.format(key=(work / "id_ed25519.pub").read_text().strip()))
    (seed_dir / "meta-data").write_text("instance-id: smoke\nlocal-hostname: smoke\n")
    seed = work / "seed.iso"
    subprocess.run(["cloud-localds", str(seed), str(seed_dir / "user-data"), str(seed_dir / "meta-data")], check=True)

    overlay = str(work / "overlay.qcow2")
    make_overlay(image, overlay)
    vm = VM(args.arch, overlay, work / "vm", accel="tcg", memory="2048", cpus="4", seed=str(seed), ssh_key=str(key))
    start = time.monotonic()
    vm.start()
    try:
        vm.qmp.screendump(str(work / "01-early.png"))
        if not vm.wait_ssh(args.timeout):
            sys.exit(f"no SSH within {args.timeout}s; see {vm.serial}")
        print(f"SSH up after {time.monotonic() - start:.0f}s:", vm.ssh("cat /etc/fedora-release", check=True).stdout.strip())
        sessions = boot_test.parse_sessions(vm.ssh(boot_test.SESSIONS, check=True).stdout)
        print("sessions:", sessions)
        vm.qmp.send_keys(["ret"])
        vm.qmp.type_text("tester")
        time.sleep(5)                                   # TCG redraws slowly
        vm.qmp.screendump(str(work / "02-console.png"))
        size = (work / "02-console.png").stat().st_size
        print(f"screendump: {size} bytes")
        if size < 1000:
            sys.exit("screendump too small")
        print("SMOKE OK")
    finally:
        vm.stop()
        shutil.rmtree(work / "seed", ignore_errors=True)


if __name__ == "__main__":
    main()
