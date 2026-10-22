"""Start and drive a QEMU VM: disk overlays, QMP, serial log and SSH."""

import os
import shlex
import shutil
import socket
import subprocess
import time
from pathlib import Path

from .qmp import QMP

# UEFI firmware for aarch64 (Ubuntu qemu-efi-aarch64, Fedora edk2-aarch64, Homebrew qemu)
AARCH64_FIRMWARE = [
    ("/usr/share/AAVMF/AAVMF_CODE.fd", "/usr/share/AAVMF/AAVMF_VARS.fd"),
    ("/usr/share/edk2/aarch64/QEMU_EFI-pflash.raw", "/usr/share/edk2/aarch64/vars-template-pflash.raw"),
    ("/opt/homebrew/share/qemu/edk2-aarch64-code.fd", "/opt/homebrew/share/qemu/edk2-arm-vars.fd"),
]


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def qemu_img(*args):
    subprocess.run(["qemu-img", *args], check=True)


def make_overlay(base, overlay):
    """A copy-on-write disk on top of the cached base image, so the base stays clean."""
    if os.path.exists(overlay):
        os.remove(overlay)
    qemu_img("create", "-q", "-f", "qcow2", "-F", "qcow2", "-b", os.path.abspath(base), overlay)


class VM:
    def __init__(self, arch, disk, workdir, accel="kvm", memory="4096", cpus="2", seed=None, ssh_key=None,
                 ssh_user="tester"):
        self.arch = arch
        self.disk = disk
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.accel = accel
        self.memory = memory
        self.cpus = cpus
        self.seed = seed
        self.ssh_key = ssh_key
        self.ssh_user = ssh_user
        self.ssh_port = free_port()
        self.qmp_path = str(self.workdir / "qmp.sock")
        self.serial = self.workdir / "serial.log"
        self.proc = None
        self.qmp = None

    def command(self):
        cpu = "host" if self.accel in ("kvm", "hvf") else "max"
        net = f"user,model=virtio-net-pci,hostfwd=tcp:127.0.0.1:{self.ssh_port}-:22"
        common = ["-m", self.memory, "-smp", self.cpus, "-cpu", cpu, "-display", "none",
                  "-qmp", f"unix:{self.qmp_path},server=on,wait=off",
                  "-nic", net, "-serial", f"file:{self.serial}",
                  "-drive", f"file={self.disk},if=virtio,format=qcow2",
                  "-device", "virtio-rng-pci"]
        if self.seed:
            common += ["-drive", f"file={self.seed},if=virtio,format=raw,readonly=on"]
        if self.arch == "x86_64":
            return ["qemu-system-x86_64", "-machine", f"q35,accel={self.accel}", "-vga", "virtio", *common]
        if self.arch == "aarch64":
            code, vars_ = self._firmware()
            return ["qemu-system-aarch64", "-machine", f"virt,accel={self.accel},gic-version=max",
                    "-device", "virtio-gpu-pci", "-device", "qemu-xhci", "-device", "usb-kbd", "-device", "usb-tablet",
                    "-drive", f"if=pflash,format=raw,readonly=on,file={code}",
                    "-drive", f"if=pflash,format=raw,file={vars_}", *common]
        raise ValueError(f"unsupported arch {self.arch}")

    def _firmware(self):
        for code, vars_template in AARCH64_FIRMWARE:
            if os.path.exists(code) and os.path.exists(vars_template):
                vars_ = self.workdir / "efivars.fd"
                shutil.copy(vars_template, vars_)
                size = os.path.getsize(code)
                if os.path.getsize(vars_) < size:          # pflash units must be the same size
                    with open(vars_, "ab") as f:
                        f.truncate(size)
                return code, vars_
        raise FileNotFoundError("no aarch64 UEFI firmware found (install qemu-efi-aarch64)")

    def start(self):
        cmd = self.command()
        (self.workdir / "qemu-command.txt").write_text(shlex.join(cmd) + "\n")
        self.proc = subprocess.Popen(cmd, stdout=open(self.workdir / "qemu.log", "w"), stderr=subprocess.STDOUT)
        self.qmp = QMP(self.qmp_path).connect()
        return self

    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def wait_exit(self, timeout):
        try:
            return self.proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return None

    def stop(self):
        if self.qmp:
            self.qmp.quit()
            self.qmp.close()
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    # ---- SSH

    def ssh(self, command, timeout=60, check=False, user=None):
        args = ["ssh", "-i", self.ssh_key, "-p", str(self.ssh_port),
                "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
                "-o", "ConnectTimeout=5", "-o", "BatchMode=yes", "-o", "LogLevel=ERROR",
                f"{user or self.ssh_user}@127.0.0.1", command]
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        if check and r.returncode != 0:
            raise RuntimeError(f"ssh {command!r} failed ({r.returncode}): {r.stderr.strip()}")
        return r

    def wait_ssh(self, timeout):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not self.alive():
                raise RuntimeError("QEMU exited while waiting for SSH")
            try:
                if self.ssh("true", timeout=15).returncode == 0:
                    return True
            except subprocess.TimeoutExpired:
                pass
            time.sleep(5)
        return False
