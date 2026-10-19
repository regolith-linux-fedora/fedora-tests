"""Pure helpers for the Session Test harness: no sway, no subprocesses, stdlib only.
Kept separate from session.py so they can be unit-tested anywhere (tests/unit/)."""
import math
import xml.etree.ElementTree as ET

# wtype modifier names (wtype -M/-m) for the spellings tests use
MODIFIERS = {
    "super": "logo", "mod4": "logo", "logo": "logo", "win": "logo",
    "ctrl": "ctrl", "control": "ctrl",
    "alt": "alt", "mod1": "alt",
    "shift": "shift",
}


def wtype_args(combo):
    """'super+shift+Return' -> ['-M', 'logo', '-M', 'shift', '-k', 'Return', '-m', 'shift', '-m', 'logo'].

    The last element is the key (an XKB keysym name, case-sensitive); everything before
    it must be a modifier. Modifiers are released in reverse order."""
    parts = [p.strip() for p in combo.split("+")]
    if not parts or not parts[-1]:
        raise ValueError(f"empty key in combo {combo!r}")
    *mods, key = parts
    names = []
    for m in mods:
        name = MODIFIERS.get(m.lower())
        if name is None:
            raise ValueError(f"unknown modifier {m!r} in combo {combo!r}")
        names.append(name)
    args = []
    for n in names:
        args += ["-M", n]
    args += ["-k", key]
    for n in reversed(names):
        args += ["-m", n]
    return args


def iter_nodes(node):
    """Every node of a sway get_tree result, tiling and floating, depth first."""
    yield node
    for child in node.get("nodes", []) + node.get("floating_nodes", []):
        yield from iter_nodes(child)


def find_windows(tree, app_id=None, window_class=None):
    """Views (windows) matching app_id (Wayland) and/or window class (Xwayland)."""
    found = []
    for n in iter_nodes(tree):
        if n.get("type") not in ("con", "floating_con") or not n.get("pid"):
            continue                      # containers without a client are not windows
        if app_id is not None and n.get("app_id") != app_id:
            continue
        if window_class is not None and (n.get("window_properties") or {}).get("class") != window_class:
            continue
        found.append(n)
    return found


def variance(values):
    """Population variance of a sequence of numbers (e.g. grayscale pixel values)."""
    values = list(values)
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    return sum((v - mean) ** 2 for v in values) / len(values)


def is_blank(values, threshold=1.0):
    """True if the pixels are (almost) a single colour: a blank or failed screenshot."""
    return variance(values) < threshold


def junit_summary(xml_text, title="Session Test"):
    """Markdown table from a pytest --junitxml report, for $GITHUB_STEP_SUMMARY."""
    root = ET.fromstring(xml_text)
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    rows, totals = [], {"passed": 0, "failed": 0, "skipped": 0, "error": 0}
    for suite in suites:
        for case in suite.findall("testcase"):
            name = f"{case.get('classname', '')}::{case.get('name', '')}".strip(":")
            if case.find("failure") is not None:
                outcome, detail = "failed", case.find("failure").get("message", "")
            elif case.find("error") is not None:
                outcome, detail = "error", case.find("error").get("message", "")
            elif case.find("skipped") is not None:
                outcome, detail = "skipped", case.find("skipped").get("message", "")
            else:
                outcome, detail = "passed", ""
            totals[outcome] += 1
            seconds = float(case.get("time", 0) or 0)
            detail = detail.replace("|", "\\|").replace("\n", " ")[:120]
            rows.append(f"| {name} | {outcome} | {seconds:.1f}s | {detail} |")
    head = [f"### {title}", "",
            "  ".join(f"**{k}** {v}" for k, v in totals.items()), "",
            "| Test | Result | Time | Detail |", "|---|---|---|---|"]
    return "\n".join(head + rows) + "\n"


def wait_until(predicate, timeout, interval=0.1, clock=None, sleep=None):
    """Poll predicate() until it returns a truthy value or timeout seconds pass.
    Returns the truthy value, or None on timeout. clock/sleep are injectable for tests."""
    import time
    clock = clock or time.monotonic
    sleep = sleep or time.sleep
    deadline = clock() + timeout
    while True:
        value = predicate()
        if value:
            return value
        if clock() >= deadline:
            return None
        sleep(interval)


def stddev(values):
    return math.sqrt(variance(values))
