"""A headless sway session driven like a user: IPC, injected keys, screenshots, D-Bus.

Runs inside the test container (see Containerfile), as a normal user, under the
D-Bus session bus that run.sh starts with dbus-run-session.
"""
import glob
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from .util import find_windows, wait_until, wtype_args


class SessionError(RuntimeError):
    pass


class Session:
    """Start sway headless with a config; tear it down and keep the evidence.

    Environment per the Fedora Track's Session Test technique:
    WLR_BACKENDS=headless, WLR_RENDERER=pixman, WLR_LIBINPUT_NO_DEVICES=1 and a
    private XDG_RUNTIME_DIR (mode 0700)."""

    def __init__(self, config, artifacts_dir, start_timeout=30):
        self.config = Path(config)
        self.artifacts = Path(artifacts_dir)
        self.start_timeout = start_timeout
        self.runtime_dir = None
        self.proc = None
        self.socket = None
        self.wayland_display = None
        self.screenshots = []
        self._log = None

    # ---- lifecycle -------------------------------------------------------
    def start(self):
        self.artifacts.mkdir(parents=True, exist_ok=True)
        self.runtime_dir = tempfile.mkdtemp(prefix="session-xdg-")
        os.chmod(self.runtime_dir, 0o700)
        env = dict(os.environ,
                   XDG_RUNTIME_DIR=self.runtime_dir,
                   XDG_SESSION_TYPE="wayland",
                   WLR_BACKENDS="headless",
                   WLR_RENDERER="pixman",
                   WLR_LIBINPUT_NO_DEVICES="1")
        env.pop("WAYLAND_DISPLAY", None)
        env.pop("SWAYSOCK", None)
        self._log = open(self.artifacts / "sway.log", "w")
        self.proc = subprocess.Popen(["sway", "--debug", "--config", str(self.config)],
                                     env=env, stdout=self._log, stderr=subprocess.STDOUT)

        def ready():
            if self.proc.poll() is not None:
                raise SessionError(f"sway exited with {self.proc.returncode}; see {self.artifacts / 'sway.log'}")
            for sock in glob.glob(os.path.join(self.runtime_dir, "sway-ipc.*.sock")):
                self.socket = sock
                try:
                    if self.outputs():
                        return True
                except subprocess.CalledProcessError:
                    pass
            return False

        if not wait_until(ready, self.start_timeout):
            self.stop()
            raise SessionError(f"sway did not provide an IPC socket and an output within {self.start_timeout}s")
        displays = [p for p in glob.glob(os.path.join(self.runtime_dir, "wayland-*")) if not p.endswith(".lock")]
        if not displays:
            raise SessionError("sway is up but no wayland-* socket exists in XDG_RUNTIME_DIR")
        self.wayland_display = os.path.basename(sorted(displays)[0])
        return self

    def stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.swaymsg("exit")
            except Exception:
                pass
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        if self._log:
            self._log.close()
            self._log = None
        self._collect()
        if self.runtime_dir:
            shutil.rmtree(self.runtime_dir, ignore_errors=True)

    def _collect(self):
        """Evidence next to the screenshots: tree, outputs, journal if one exists."""
        if shutil.which("journalctl"):
            with open(self.artifacts / "journal.txt", "w") as f:
                subprocess.run(["journalctl", "--user", "--no-pager", "-b"], stdout=f,
                               stderr=subprocess.STDOUT, check=False)

    # ---- environment for clients ------------------------------------------
    def client_env(self):
        # start() polls swaymsg before WAYLAND_DISPLAY is known: leave unset values out
        extra = dict(XDG_RUNTIME_DIR=self.runtime_dir,
                     WAYLAND_DISPLAY=self.wayland_display, SWAYSOCK=self.socket)
        return dict(os.environ, **{k: v for k, v in extra.items() if v is not None})

    def _run(self, argv, check=True, capture=True):
        return subprocess.run(argv, env=self.client_env(), check=check, text=True,
                              stdout=subprocess.PIPE if capture else None,
                              stderr=subprocess.PIPE if capture else None)

    # ---- helpers the tests use --------------------------------------------
    def swaymsg(self, *args):
        """swaymsg -s <socket> -r <args>; returns parsed JSON."""
        out = self._run(["swaymsg", "-s", self.socket, "-r", *args]).stdout
        return json.loads(out) if out.strip() else None

    def tree(self):
        return self.swaymsg("-t", "get_tree")

    def outputs(self):
        return self.swaymsg("-t", "get_outputs")

    def keys(self, combo):
        """Inject a key combination through the virtual-keyboard protocol, e.g. 'super+Return'."""
        self._run(["wtype", *wtype_args(combo)])

    def windows(self, app_id=None, window_class=None):
        return find_windows(self.tree(), app_id=app_id, window_class=window_class)

    def wait_for_window(self, app_id=None, window_class=None, timeout=10):
        """The first matching window, or None after timeout seconds."""
        found = wait_until(lambda: self.windows(app_id=app_id, window_class=window_class), timeout)
        return found[0] if found else None

    def wait_for_process(self, name, timeout=10):
        def running():
            return subprocess.run(["pgrep", "-x", name], stdout=subprocess.DEVNULL).returncode == 0
        return bool(wait_until(running, timeout))

    def screenshot(self, label):
        """Save <artifacts>/<n>-<label>.png with grim; returns the path."""
        path = self.artifacts / f"{len(self.screenshots) + 1:02d}-{label}.png"
        self._run(["grim", str(path)])
        self.screenshots.append(path)
        return path

    def dbus_has_name(self, name):
        """True if `name` is owned on the session bus."""
        out = self._run(["gdbus", "call", "--session", "--dest", "org.freedesktop.DBus",
                         "--object-path", "/org/freedesktop/DBus",
                         "--method", "org.freedesktop.DBus.ListNames"]).stdout
        return f"'{name}'" in out

    def settle(self, seconds=0.5):
        """Give the compositor a moment to render before a screenshot."""
        time.sleep(seconds)
