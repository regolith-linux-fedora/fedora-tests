"""Minimal QEMU Machine Protocol client: screenshots and keyboard input.

Only the standard library, so it runs on a bare GitHub runner.
"""

import json
import socket
import time

# QEMU QKeyCode names for characters that aren't their own name.
_SHIFTED = {
    "!": "1", "@": "2", "#": "3", "$": "4", "%": "5", "^": "6", "&": "7", "*": "8",
    "(": "9", ")": "0", "_": "minus", "+": "equal", "{": "bracket_left", "}": "bracket_right",
    "|": "backslash", ":": "semicolon", '"': "apostrophe", "~": "grave_accent", "<": "comma",
    ">": "dot", "?": "slash",
}
_PLAIN = {
    " ": "spc", "-": "minus", "=": "equal", "[": "bracket_left", "]": "bracket_right",
    "\\": "backslash", ";": "semicolon", "'": "apostrophe", "`": "grave_accent", ",": "comma",
    ".": "dot", "/": "slash", "\n": "ret", "\t": "tab",
}


def keys_for_char(ch):
    """QKeyCodes to press together for one character on a US layout."""
    if ch.isascii() and ch.isalpha():
        return ["shift", ch.lower()] if ch.isupper() else [ch]
    if ch.isascii() and ch.isdigit():
        return [ch]
    if ch in _PLAIN:
        return [_PLAIN[ch]]
    if ch in _SHIFTED:
        return ["shift", _SHIFTED[ch]]
    raise ValueError(f"no key for {ch!r}")


class QMPError(RuntimeError):
    pass


class QMP:
    def __init__(self, path, timeout=30):
        self.path = path
        self.timeout = timeout
        self.sock = None
        self.buf = b""

    def connect(self, wait=60):
        deadline = time.monotonic() + wait
        while True:
            try:
                self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.sock.settimeout(self.timeout)
                self.sock.connect(self.path)
                break
            except OSError:
                self.sock.close()
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.5)
        greeting = self._read()
        if "QMP" not in greeting:
            raise QMPError(f"unexpected greeting: {greeting}")
        self.command("qmp_capabilities")
        return self

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None

    def _read(self):
        while b"\n" not in self.buf:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise QMPError("QMP connection closed")
            self.buf += chunk
        line, self.buf = self.buf.split(b"\n", 1)
        return json.loads(line)

    def command(self, name, **arguments):
        msg = {"execute": name}
        if arguments:
            msg["arguments"] = arguments
        self.sock.sendall(json.dumps(msg).encode() + b"\n")
        while True:
            reply = self._read()
            if "event" in reply:
                continue
            if "error" in reply:
                raise QMPError(f"{name}: {reply['error']}")
            return reply.get("return")

    def screendump(self, filename):
        """Save the display as PNG (QEMU >= 7.1)."""
        self.command("screendump", filename=filename, format="png")

    def send_keys(self, keys, hold_ms=60):
        """Press a chord, e.g. ["meta_l", "ret"]."""
        self.command("send-key", keys=[{"type": "qcode", "data": k} for k in keys], **{"hold-time": hold_ms})

    def type_text(self, text, delay=0.08):
        for ch in text:
            self.send_keys(keys_for_char(ch))
            time.sleep(delay)

    def quit(self):
        try:
            self.command("quit")
        except (QMPError, OSError):
            pass
