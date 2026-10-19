"""Unit tests for harness.util. No sway needed: runs anywhere with
`python3 -m unittest discover -s session/tests/unit -t session` or under pytest."""
import unittest

from harness.util import find_windows, is_blank, junit_summary, variance, wait_until, wtype_args


class WtypeArgs(unittest.TestCase):
    def test_super_return(self):
        self.assertEqual(wtype_args("super+Return"), ["-M", "logo", "-k", "Return", "-m", "logo"])

    def test_two_modifiers_released_in_reverse(self):
        self.assertEqual(wtype_args("ctrl+shift+t"),
                         ["-M", "ctrl", "-M", "shift", "-k", "t", "-m", "shift", "-m", "ctrl"])

    def test_plain_key_and_aliases(self):
        self.assertEqual(wtype_args("Escape"), ["-k", "Escape"])
        self.assertEqual(wtype_args("Mod4+d"), wtype_args("super+d"))

    def test_rejects_unknown_modifier_and_empty_key(self):
        with self.assertRaises(ValueError):
            wtype_args("hyper+x")
        with self.assertRaises(ValueError):
            wtype_args("super+")


TREE = {
    "type": "root", "nodes": [
        {"type": "output", "name": "__i3", "nodes": []},
        {"type": "output", "name": "HEADLESS-1", "nodes": [
            {"type": "workspace", "name": "1", "nodes": [
                {"type": "con", "app_id": "foot", "pid": 42, "nodes": []},
                {"type": "con", "app_id": None, "pid": None, "nodes": [   # split container, no client
                    {"type": "con", "app_id": None, "pid": 43, "window_properties": {"class": "XTerm"}, "nodes": []},
                ]},
            ], "floating_nodes": [
                {"type": "floating_con", "app_id": "pavucontrol", "pid": 44, "nodes": []},
            ]},
        ]},
    ]}


class FindWindows(unittest.TestCase):
    def test_all_views_including_floating_and_nested(self):
        self.assertEqual(sorted(w["pid"] for w in find_windows(TREE)), [42, 43, 44])

    def test_by_app_id_and_class(self):
        self.assertEqual([w["pid"] for w in find_windows(TREE, app_id="foot")], [42])
        self.assertEqual([w["pid"] for w in find_windows(TREE, window_class="XTerm")], [43])
        self.assertEqual(find_windows(TREE, app_id="nope"), [])


class Blankness(unittest.TestCase):
    def test_flat_image_is_blank(self):
        self.assertEqual(variance([40] * 1000), 0.0)
        self.assertTrue(is_blank([40] * 1000))

    def test_terminal_like_image_is_not_blank(self):
        pixels = [40] * 900 + [230] * 100            # dark background, some light text
        self.assertGreater(variance(pixels), 1.0)
        self.assertFalse(is_blank(pixels))

    def test_empty(self):
        self.assertTrue(is_blank([]))


JUNIT = """<?xml version="1.0"?><testsuites><testsuite name="pytest" tests="4">
<testcase classname="tests.stock.test_stock" name="test_reload_succeeds" time="1.2"/>
<testcase classname="tests.stock.test_stock" name="test_unbound_key_opens_no_window" time="3.4">
  <failure message="an unbound key opened a window">trace</failure></testcase>
<testcase classname="tests.regolith.test_regolith" name="test_bar" time="0">
  <skipped message="06-02: bar | i3status-rust"/></testcase>
<testcase classname="x" name="y" time="0"><error message="boom"/></testcase>
</testsuite></testsuites>"""


class JunitSummary(unittest.TestCase):
    def test_counts_and_rows(self):
        md = junit_summary(JUNIT, "Session Test: stock, fedora 43, x86_64")
        self.assertIn("### Session Test: stock, fedora 43, x86_64", md)
        self.assertIn("**passed** 1  **failed** 1  **skipped** 1  **error** 1", md)
        self.assertIn("| tests.stock.test_stock::test_reload_succeeds | passed | 1.2s |  |", md)
        self.assertIn("an unbound key opened a window", md)
        self.assertIn("06-02: bar \\| i3status-rust", md)      # pipes escaped for the table


class WaitUntil(unittest.TestCase):
    def test_returns_value_or_none_on_timeout(self):
        t = [0.0]
        clock = lambda: t[0]                                          # noqa: E731
        def sleep(s): t[0] += s
        calls = iter([None, None, "ready"])
        self.assertEqual(wait_until(lambda: next(calls), 5, 1, clock, sleep), "ready")
        self.assertIsNone(wait_until(lambda: None, 2, 1, clock, sleep))


if __name__ == "__main__":
    unittest.main()
