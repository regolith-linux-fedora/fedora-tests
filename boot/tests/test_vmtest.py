import base64
import json
import os
import socket
import sys
import tempfile
import threading
import unittest
from pathlib import Path

BOOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BOOT))

import boot_test  # noqa: E402
import build_image  # noqa: E402
from vmtest import qmp  # noqa: E402


class KeysTest(unittest.TestCase):
    def test_letters_digits_and_symbols(self):
        self.assertEqual(qmp.keys_for_char("a"), ["a"])
        self.assertEqual(qmp.keys_for_char("T"), ["shift", "t"])
        self.assertEqual(qmp.keys_for_char("7"), ["7"])
        self.assertEqual(qmp.keys_for_char("-"), ["minus"])
        self.assertEqual(qmp.keys_for_char("!"), ["shift", "1"])
        self.assertEqual(qmp.keys_for_char(" "), ["spc"])

    def test_default_password_is_typeable(self):
        for ch in "boot-test-123":
            qmp.keys_for_char(ch)

    def test_unknown_character(self):
        with self.assertRaises(ValueError):
            qmp.keys_for_char("é")


class FakeQMP(threading.Thread):
    """A QMP server that records commands and answers {"return": {}}."""

    def __init__(self, path):
        super().__init__(daemon=True)
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(path)
        self.server.listen(1)
        self.commands = []

    def run(self):
        conn, _ = self.server.accept()
        conn.sendall(b'{"QMP": {"version": {}, "capabilities": []}}\n')
        buf = b""
        while True:
            data = conn.recv(4096)
            if not data:
                return
            buf += data
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                msg = json.loads(line)
                self.commands.append(msg)
                conn.sendall(b'{"event": "NOISE"}\n{"return": {}}\n')
                if msg["execute"] == "quit":
                    conn.close()
                    self.server.close()
                    return


class QMPTest(unittest.TestCase):
    def test_handshake_typing_and_screendump(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "q.sock")
            server = FakeQMP(path)
            server.start()
            q = qmp.QMP(path).connect(wait=5)
            q.type_text("Ab", delay=0)
            q.send_keys(["meta_l", "ret"])
            q.screendump("/tmp/x.png")
            q.quit()
            server.join(5)
        names = [c["execute"] for c in server.commands]
        self.assertEqual(names, ["qmp_capabilities", "send-key", "send-key", "send-key", "screendump", "quit"])
        self.assertEqual([k["data"] for k in server.commands[1]["arguments"]["keys"]], ["shift", "a"])
        self.assertEqual([k["data"] for k in server.commands[3]["arguments"]["keys"]], ["meta_l", "ret"])
        self.assertEqual(server.commands[4]["arguments"], {"filename": "/tmp/x.png", "format": "png"})


class BootTestHelpers(unittest.TestCase):
    def test_parse_sessions(self):
        text = "Id=c1\nName=gdm\nClass=greeter\nType=wayland\nActive=yes\n\nId=2\nName=tester\nClass=user\nType=wayland\nDesktop=sway\nActive=yes\n\n"
        sessions = boot_test.parse_sessions(text)
        self.assertEqual([s["Name"] for s in sessions], ["gdm", "tester"])
        self.assertEqual(sessions[1]["Desktop"], "sway")

    def test_count_app(self):
        tree = {"nodes": [{"nodes": [{"app_id": "foot", "nodes": []}, {"app_id": "x", "nodes": []}]}],
                "floating_nodes": [{"app_id": "foot", "nodes": []}]}
        self.assertEqual(boot_test.count_app(tree, "foot"), 2)


class ImageTest(unittest.TestCase):
    def test_user_data_fills_every_placeholder(self):
        text = build_image.user_data("pw", "ssh-ed25519 AAAA test\n")
        self.assertTrue(text.startswith("#cloud-config"))
        for placeholder in ("@PASSWORD@", "@SSH_PUBKEY@", "@PROVISION@"):
            self.assertNotIn(placeholder, text)
        encoded = text.split('content: "', 1)[1].split('"', 1)[0]
        self.assertEqual(base64.b64decode(encoded), (BOOT / "image" / "provision.sh").read_bytes())
        self.assertIn('"ssh-ed25519 AAAA test"', text)

    def test_images_url(self):
        self.assertTrue(build_image.images_url("44", "x86_64").endswith("/releases/44/Cloud/x86_64/images/"))
        self.assertIn("/development/rawhide/", build_image.images_url("rawhide", "aarch64"))


if __name__ == "__main__":
    unittest.main()
