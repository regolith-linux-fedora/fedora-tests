#!/usr/bin/env python3
"""Build the Boot Test base image: Fedora Cloud Base Generic -> Fedora Workstation with GDM and sway.

    boot/build_image.py --release 45 --arch x86_64 --ssh-pubkey key.pub --out cache/boot-45-x86_64.qcow2

Downloads the Cloud Base Generic qcow2 for the release, verifies its SHA256 against Fedora's CHECKSUM file
(and the CHECKSUM's OpenPGP signature when gpgv is installed), grows the disk, then boots it once with a
cloud-init seed that runs image/provision.sh and powers off. The result is cached by the workflow.
"""

import argparse
import base64
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vmtest.vm import VM, qemu_img  # noqa: E402

HERE = Path(__file__).resolve().parent
MIRROR = "https://dl.fedoraproject.org/pub/fedora/linux"
FEDORA_KEYS = "https://fedoraproject.org/fedora.gpg"


def images_url(release, arch):
    branch = "development" if release == "rawhide" else "releases"
    return f"{MIRROR}/{branch}/{release}/Cloud/{arch}/images/"


def fetch_text(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read().decode()


def find_image(release, arch):
    url = images_url(release, arch)
    listing = fetch_text(url)
    images = sorted(set(re.findall(rf'href="(Fedora-Cloud-Base-Generic-[^"]*\.{arch}\.qcow2)"', listing)))
    checksums = sorted(set(re.findall(rf'href="(Fedora-Cloud-[^"]*-{arch}-CHECKSUM)"', listing)))
    if not images or not checksums:
        sys.exit(f"no Cloud Base Generic qcow2 or CHECKSUM under {url}")
    return url, images[-1], checksums[-1]


def verify_checksum_signature(checksum_path, workdir):
    if not shutil.which("gpgv"):
        print("gpgv not installed: CHECKSUM signature not verified (SHA256 still is)")
        return False
    keys = workdir / "fedora.gpg"
    urllib.request.urlretrieve(FEDORA_KEYS, keys)
    keyring = workdir / "fedora.kbx"
    subprocess.run(["gpg", "--batch", "--no-default-keyring", "--keyring", str(keyring), "--import", str(keys)],
                   check=True, capture_output=True)
    subprocess.run(["gpgv", "--keyring", str(keyring), str(checksum_path)], check=True)
    print("CHECKSUM signature OK")
    return True


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(release, arch, workdir):
    url, image, checksum = find_image(release, arch)
    checksum_path = workdir / checksum
    urllib.request.urlretrieve(url + checksum, checksum_path)
    verify_checksum_signature(checksum_path, workdir)
    expected = re.search(rf"SHA256 \({re.escape(image)}\) = ([0-9a-f]{{64}})", checksum_path.read_text())
    if not expected:
        sys.exit(f"{image} not listed in {checksum}")
    path = workdir / image
    if not path.exists() or sha256(path) != expected.group(1):
        print(f"downloading {url}{image}", flush=True)
        urllib.request.urlretrieve(url + image, path)
    actual = sha256(path)
    if actual != expected.group(1):
        sys.exit(f"SHA256 mismatch for {image}: {actual} != {expected.group(1)}")
    print(f"{image}: SHA256 OK")
    return path, url + image, actual


def user_data(password, pubkey):
    text = (HERE / "image" / "user-data.yaml").read_text()
    provision = base64.b64encode((HERE / "image" / "provision.sh").read_bytes()).decode()
    return text.replace("@PASSWORD@", password).replace("@SSH_PUBKEY@", pubkey.strip()).replace("@PROVISION@", provision)


def make_seed(workdir, password, pubkey):
    seed_dir = workdir / "seed"
    seed_dir.mkdir(exist_ok=True)
    (seed_dir / "user-data").write_text(user_data(password, pubkey))
    (seed_dir / "meta-data").write_text("instance-id: boot-test\nlocal-hostname: boot-test\n")
    iso = workdir / "seed.iso"
    if shutil.which("cloud-localds"):
        cmd = ["cloud-localds", str(iso), str(seed_dir / "user-data"), str(seed_dir / "meta-data")]
    elif shutil.which("xorriso"):
        cmd = ["xorriso", "-as", "genisoimage", "-output", str(iso), "-volid", "cidata", "-joliet", "-rock",
               str(seed_dir / "user-data"), str(seed_dir / "meta-data")]
    elif shutil.which("genisoimage"):
        cmd = ["genisoimage", "-output", str(iso), "-volid", "cidata", "-joliet", "-rock",
               str(seed_dir / "user-data"), str(seed_dir / "meta-data")]
    else:
        sys.exit("need cloud-localds, xorriso or genisoimage to build the cloud-init seed")
    subprocess.run(cmd, check=True, capture_output=True)
    return iso


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--release", default="45")
    ap.add_argument("--arch", default="x86_64", choices=["x86_64", "aarch64"])
    ap.add_argument("--ssh-pubkey", required=True)
    ap.add_argument("--password", default="boot-test-123")
    ap.add_argument("--out", required=True)
    ap.add_argument("--workdir", default="work/image")
    ap.add_argument("--accel", default="kvm")
    ap.add_argument("--disk-size", default="20G")
    ap.add_argument("--memory", default="4096")
    ap.add_argument("--cpus", default="4")
    ap.add_argument("--timeout", type=int, default=3600, help="seconds for provisioning")
    args = ap.parse_args()

    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    source, source_url, source_sha = download(args.release, args.arch, workdir)

    disk = workdir / "provision.qcow2"
    shutil.copy(source, disk)
    qemu_img("resize", "-q", str(disk), args.disk_size)
    seed = make_seed(workdir, args.password, Path(args.ssh_pubkey).read_text())

    start = time.monotonic()
    vm = VM(args.arch, str(disk), workdir / "vm", accel=args.accel, memory=args.memory, cpus=args.cpus, seed=str(seed))
    vm.start()
    code = vm.wait_exit(args.timeout)
    if code is None:
        vm.qmp.screendump(str(workdir / "provision-timeout.png"))
        vm.stop()
        sys.exit(f"provisioning did not power off within {args.timeout}s; see {vm.serial}")
    serial = vm.serial.read_text(errors="replace")
    result = re.findall(r"BOOT-TEST-PROVISION: (.*)", serial)
    if not result or not result[-1].startswith("OK"):
        sys.exit(f"provisioning failed: {result[-1] if result else 'no marker on the console'}; see {vm.serial}")
    minutes = (time.monotonic() - start) / 60
    print(f"provisioned in {minutes:.1f} min: {result[-1]}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    qemu_img("convert", "-q", "-O", "qcow2", "-c", "-o", "compression_type=zstd", str(disk), str(out))
    meta = {"release": args.release, "arch": args.arch, "source": source_url, "source_sha256": source_sha,
            "provision_sha256": sha256(HERE / "image" / "provision.sh"), "provision_minutes": round(minutes, 1),
            "packages": result[-1][3:].split(), "built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    Path(str(out) + ".json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"wrote {out} ({out.stat().st_size >> 20} MiB)")


if __name__ == "__main__":
    main()
