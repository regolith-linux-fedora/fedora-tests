"""Stock profile: the harness proves itself against stock Fedora sway + foot (Task 01-08)."""
from PIL import Image

from harness.util import is_blank, variance


def grayscale_sample(path, step=7):
    """Every step-th grayscale pixel: enough to tell a real frame from a flat one."""
    with Image.open(path) as im:
        data = im.convert("L").getdata()
        return [data[i] for i in range(0, len(data), step)]


def test_sway_starts_with_one_headless_output(session):
    outputs = session.outputs()
    assert len(outputs) == 1, outputs
    assert outputs[0]["name"].startswith("HEADLESS-"), outputs[0]["name"]
    assert outputs[0]["active"]


def test_super_return_opens_a_terminal(session):
    session.keys("super+Return")
    window = session.wait_for_window(app_id="foot", timeout=15)
    assert window is not None, "super+Return did not open a foot window"
    assert session.wait_for_process("foot")
    session.settle()
    session.screenshot("terminal")


def test_screenshot_is_not_blank(session):
    session.swaymsg("exec", "foot")
    assert session.wait_for_window(app_id="foot", timeout=15) is not None
    session.settle(1)
    shot = session.screenshot("terminal-variance")
    pixels = grayscale_sample(shot)
    assert not is_blank(pixels), f"screenshot looks blank (variance {variance(pixels):.2f})"


def test_reload_succeeds(session):
    result = session.swaymsg("reload")
    assert result and all(r.get("success") for r in result), result
    assert len(session.outputs()) == 1


def test_unbound_key_opens_no_window(session, invert_negative):
    """Negative test. With --invert-negative it asserts the opposite and must FAIL,
    which shows that wait_for_window and the assertions really check something."""
    before = len(session.windows())
    session.keys("super+F12")                      # not bound in configs/stock.conf
    window = session.wait_for_window(app_id="foot", timeout=3)
    session.screenshot("after-unbound-key")
    if invert_negative:
        assert window is not None, "inverted negative test: expected a window (this failure is the point)"
    else:
        assert window is None, "an unbound key opened a window"
        assert len(session.windows()) == before
