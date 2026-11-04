import os
import unittest

from harness.session import Session


class ClientEnv(unittest.TestCase):
    def test_unset_values_are_left_out_while_sway_starts(self):
        s = Session("config", "artifacts")
        s.runtime_dir, s.socket = "/tmp/xdg", "/tmp/xdg/sway-ipc.sock"
        env = s.client_env()
        self.assertEqual(env["XDG_RUNTIME_DIR"], "/tmp/xdg")
        self.assertEqual(env["SWAYSOCK"], "/tmp/xdg/sway-ipc.sock")
        self.assertEqual(env.get("WAYLAND_DISPLAY"), os.environ.get("WAYLAND_DISPLAY"))
        self.assertTrue(all(isinstance(v, str) for v in env.values()))

    def test_all_values_once_started(self):
        s = Session("config", "artifacts")
        s.runtime_dir, s.socket, s.wayland_display = "/tmp/xdg", "/tmp/xdg/sway-ipc.sock", "wayland-1"
        self.assertEqual(s.client_env()["WAYLAND_DISPLAY"], "wayland-1")


if __name__ == "__main__":
    unittest.main()
