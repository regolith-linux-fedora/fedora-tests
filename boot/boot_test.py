#!/usr/bin/env python3
"""Boot Test: boot the Workstation image, log in at GDM with injected keys, assert the sway session.

    boot/boot_test.py --image cache/boot-45-x86_64.qcow2 --arch x86_64 --ssh-key key --artifacts artifacts/

Steps (a screenshot after each): boot and wait for SSH; wait for the GDM greeter; type the username and
password over QMP; wait for tester's Wayland session; check sway, its outputs and IPC; open foot with
swaymsg and with an injected Super+Return, and find both windows in the sway tree. Writes results.json
and junit.xml; exits 1 if any step fails.
"""

import argparse
import json
import sys
import time
import traceback
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vmtest.vm import VM, make_overlay  # noqa: E402

SESSIONS = r"""for s in $(loginctl list-sessions --no-legend | awk '{print $1}'); do
  loginctl show-session "$s" -p Id -p Name -p Class -p Type -p Desktop -p State -p Active; echo; done"""


class StepFailed(Exception):
    pass


def parse_sessions(text):
    sessions = []
    for block in text.strip().split("\n\n"):
        props = dict(line.split("=", 1) for line in block.splitlines() if "=" in line)
        if props:
            sessions.append(props)
    return sessions


def count_app(tree, app_id):
    found = 1 if tree.get("app_id") == app_id else 0
    for child in tree.get("nodes", []) + tree.get("floating_nodes", []):
        found += count_app(child, app_id)
    return found


class BootTest:
    def __init__(self, args):
        self.args = args
        self.art = Path(args.artifacts)
        self.art.mkdir(parents=True, exist_ok=True)
        self.steps = []
        self.shot = 0
        self.vm = None
        self.sock = None

    def screenshot(self, name):
        self.shot += 1
        path = self.art / f"{self.shot:02d}-{name}.png"
        try:
            self.vm.qmp.screendump(str(path))
        except Exception as e:                                   # evidence only, never fail on it
            print(f"screendump {name} failed: {e}")

    def step(self, name, fn):
        start = time.monotonic()
        print(f"== {name}", flush=True)
        try:
            detail = fn() or ""
            ok, error = True, ""
        except Exception as e:
            ok, error, detail = False, f"{type(e).__name__}: {e}", traceback.format_exc()
        seconds = round(time.monotonic() - start, 1)
        self.screenshot(name)
        self.steps.append({"name": name, "ok": ok, "seconds": seconds, "error": error, "detail": str(detail)[-2000:]})
        print(f"   {'ok' if ok else 'FAIL'} ({seconds}s) {error or str(detail)[:200]}", flush=True)
        if not ok:
            raise StepFailed(name)

    def poll(self, what, fn, timeout, interval=3):
        deadline = time.monotonic() + timeout
        last = None
        while time.monotonic() < deadline:
            last = fn()
            if last:
                return last
            if not self.vm.alive():
                raise RuntimeError("QEMU exited")
            time.sleep(interval)
        raise TimeoutError(f"{what} not seen within {timeout}s (last: {last!r})")

    def sessions(self):
        r = self.vm.ssh(SESSIONS, timeout=30)
        return parse_sessions(r.stdout) if r.returncode == 0 else []

    # ---- steps

    def boot(self):
        if not self.vm.wait_ssh(self.args.boot_timeout):
            raise TimeoutError(f"no SSH within {self.args.boot_timeout}s")
        return self.vm.ssh("cat /etc/fedora-release; uname -r", check=True).stdout.strip()

    def greeter(self):
        def ready():
            for s in self.sessions():
                if s.get("Class") == "greeter" and s.get("Active") == "yes":
                    # GDM 49+ runs the greeter as the dynamic user gdm-greeter, older GDM as gdm
                    user = s.get("Name") or "gdm"
                    shell = self.vm.ssh(f"pgrep -u {user} -x gnome-shell", timeout=15)
                    return s if shell.returncode == 0 else None
            return None
        s = self.poll("active GDM greeter session", ready, self.args.gdm_timeout)
        time.sleep(self.args.settle)                              # let the greeter draw and take focus
        return s

    def login(self):
        qmp = self.vm.qmp
        for attempt in (1, 2):
            qmp.type_text(self.args.user)
            qmp.send_keys(["ret"])
            time.sleep(3)
            self.screenshot(f"username-attempt{attempt}")
            qmp.type_text(self.args.password)
            qmp.send_keys(["ret"])
            try:
                return self.poll("tester's Wayland session", self.user_session, self.args.login_timeout)
            except TimeoutError:
                if attempt == 2:
                    raise
                print("   no session yet, pressing Escape and typing again")
                qmp.send_keys(["esc"])
                time.sleep(3)

    def user_session(self):
        for s in self.sessions():
            if s.get("Name") == self.args.user and s.get("Class") == "user" and s.get("Type") == "wayland" \
                    and s.get("Active") == "yes":
                return s
        return None

    def sway(self):
        s = self.user_session()
        if not s:
            raise StepFailed("no active Wayland session for the user")
        procs = self.vm.ssh(f"pgrep -u {self.args.user} -x sway", check=True).stdout.split()
        if s.get("Desktop", "").lower() != "sway":
            # GDM 50 (Fedora 44) leaves logind's Desktop empty: accept sway running
            # in this session's scope instead.
            scope = f"session-{s.get('Id')}.scope"
            cgroups = self.vm.ssh(" ".join(f"cat /proc/{p}/cgroup;" for p in procs)).stdout
            if scope not in cgroups:
                raise StepFailed(f"session desktop is {s.get('Desktop')!r} and no sway runs in {scope}")
        self.sock = self.poll("sway IPC socket",
                              lambda: self.vm.ssh("ls /run/user/$(id -u)/sway-ipc.*.sock 2>/dev/null | head -n1")
                              .stdout.strip(), 60)
        outputs = json.loads(self.swaymsg("-t get_outputs"))
        active = [o["name"] for o in outputs if o.get("active")]
        if not active:
            raise StepFailed(f"no active output: {outputs}")
        version = json.loads(self.swaymsg("-t get_version")).get("human_readable")
        return f"sway {version} pids {procs} outputs {active} session {s}"

    def swaymsg(self, args):
        return self.vm.ssh(f"swaymsg -s {self.sock} {args}", check=True).stdout

    def foots(self):
        return count_app(json.loads(self.swaymsg("-t get_tree")), "foot")

    def foot_by_ipc(self):
        before = self.foots()
        self.swaymsg("exec foot")
        n = self.poll("foot window after swaymsg exec", lambda: self.foots() > before and self.foots(), 30, 1)
        return f"foot windows: {before} -> {n}"

    def foot_by_keys(self):
        before = self.foots()
        self.vm.qmp.send_keys(["meta_l", "ret"])
        n = self.poll("foot window after Super+Return", lambda: self.foots() > before and self.foots(), 30, 1)
        return f"foot windows: {before} -> {n}"

    # ---- run

    def collect(self):
        if not self.vm or not self.vm.alive():
            return
        for name, cmd in [("journal.txt", "sudo journalctl -b --no-pager -o short-monotonic"),
                          ("sessions.txt", SESSIONS),
                          ("rpm-versions.txt", "rpm -q gdm gnome-shell sway foot mesa-dri-drivers kernel")]:
            try:
                (self.art / name).write_text(self.vm.ssh(cmd, timeout=120).stdout)
            except Exception as e:
                print(f"collect {name} failed: {e}")

    def run(self):
        a = self.args
        overlay = str(self.art.parent / f"overlay-{a.arch}.qcow2")
        make_overlay(a.image, overlay)
        self.vm = VM(a.arch, overlay, self.art / "vm", accel=a.accel, memory=a.memory, cpus=a.cpus,
                     ssh_key=a.ssh_key, ssh_user=a.user)
        start = time.monotonic()
        try:
            self.vm.start()
            self.step("boot", self.boot)
            self.step("gdm-greeter", self.greeter)
            self.step("gdm-login", self.login)
            self.step("sway-session", self.sway)
            self.step("foot-via-ipc", self.foot_by_ipc)
            self.step("foot-via-super-return", self.foot_by_keys)
        except StepFailed:
            pass
        except Exception as e:
            self.steps.append({"name": "harness", "ok": False, "seconds": 0, "error": repr(e),
                               "detail": traceback.format_exc()})
        finally:
            self.collect()
            self.vm.stop()
        total = round(time.monotonic() - start, 1)
        ok = bool(self.steps) and all(s["ok"] for s in self.steps) and len(self.steps) == 6
        result = {"ok": ok, "arch": a.arch, "accel": a.accel, "image": a.image, "seconds": total, "steps": self.steps}
        meta = Path(a.image + ".json")
        if meta.exists():
            result["image_meta"] = json.loads(meta.read_text())
        (self.art / "results.json").write_text(json.dumps(result, indent=2) + "\n")
        self.junit(result)
        print(f"Boot Test {'PASSED' if ok else 'FAILED'} in {total}s")
        return ok

    def junit(self, result):
        cases = []
        for s in result["steps"]:
            body = "" if s["ok"] else f'<failure message="{escape(s["error"], {chr(34): "&quot;"})}">{escape(s["detail"])}</failure>'
            cases.append(f'  <testcase classname="boot.{result["arch"]}" name="{s["name"]}" time="{s["seconds"]}">{body}</testcase>')
        failures = sum(1 for s in result["steps"] if not s["ok"])
        (self.art / "junit.xml").write_text(
            f'<?xml version="1.0" encoding="UTF-8"?>\n<testsuite name="boot-test-{result["arch"]}" tests="{len(cases)}" '
            f'failures="{failures}" time="{result["seconds"]}">\n' + "\n".join(cases) + "\n</testsuite>\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--image", required=True)
    ap.add_argument("--arch", default="x86_64", choices=["x86_64", "aarch64"])
    ap.add_argument("--ssh-key", required=True, help="private key matching the image's tester key")
    ap.add_argument("--user", default="tester")
    ap.add_argument("--password", default="boot-test-123")
    ap.add_argument("--artifacts", default="artifacts/boot")
    ap.add_argument("--accel", default="kvm")
    ap.add_argument("--memory", default="4096")
    ap.add_argument("--cpus", default="2")
    ap.add_argument("--boot-timeout", type=int, default=600)
    ap.add_argument("--gdm-timeout", type=int, default=300)
    ap.add_argument("--login-timeout", type=int, default=120)
    ap.add_argument("--settle", type=int, default=10, help="seconds to wait after the greeter appears")
    sys.exit(0 if BootTest(ap.parse_args()).run() else 1)


if __name__ == "__main__":
    main()
