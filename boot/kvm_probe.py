#!/usr/bin/env python3
"""Does this machine give QEMU working KVM? Prints a report and writes it as JSON.

    boot/kvm_probe.py --out kvm-probe.json

Checks /dev/kvm, then starts a paused QEMU with accel=kvm for the host architecture and asks it over QMP
(`query-kvm`) whether KVM is enabled. Exit status 0 means KVM works.
"""

import argparse
import json
import os
import platform
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vmtest.qmp import QMP  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="kvm-probe.json")
    args = ap.parse_args()

    machine = platform.machine()
    report = {"machine": machine, "kernel": platform.release(), "dev_kvm": os.path.exists("/dev/kvm")}
    if report["dev_kvm"]:
        st = os.stat("/dev/kvm")
        report["dev_kvm_mode"] = oct(stat.S_IMODE(st.st_mode))
        report["dev_kvm_rw"] = os.access("/dev/kvm", os.R_OK | os.W_OK)
    try:
        report["cpu_virt_flags"] = sorted({f for line in open("/proc/cpuinfo") if line.startswith(("flags", "Features"))
                                           for f in line.split(":", 1)[1].split() if f in ("vmx", "svm")})
    except OSError:
        pass

    if machine in ("aarch64", "arm64"):
        qemu = ["qemu-system-aarch64", "-machine", "virt,accel=kvm", "-cpu", "host"]
    else:
        qemu = ["qemu-system-x86_64", "-machine", "q35,accel=kvm", "-cpu", "host"]
    with tempfile.TemporaryDirectory() as tmp:
        sock = os.path.join(tmp, "qmp.sock")
        cmd = qemu + ["-nodefaults", "-display", "none", "-S", "-qmp", f"unix:{sock},server=on,wait=off"]
        report["qemu_command"] = " ".join(cmd)
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        except FileNotFoundError as e:
            report["error"] = str(e)
            proc = None
        if proc:
            time.sleep(2)
            if proc.poll() is not None:
                report["qemu_exit"] = proc.returncode
                report["qemu_output"] = proc.stdout.read().strip()[-1000:]
                report["kvm"] = False
            else:
                q = QMP(sock).connect(wait=10)
                report["query_kvm"] = q.command("query-kvm")
                report["kvm"] = bool(report["query_kvm"].get("enabled"))
                q.quit()
                q.close()
                proc.wait(timeout=10)
    report.setdefault("kvm", False)

    Path(args.out).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    sys.exit(0 if report["kvm"] else 1)


if __name__ == "__main__":
    main()
