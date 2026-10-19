# Session Test

Starts sway headlessly inside a `fedora:<release>` container, drives it like a user and asserts on what happens. Fedora Track Task 01-08 built the harness and proves it against **stock Fedora sway**; 03-02 and 06-02 add Regolith checks in the `regolith` profile.

## How it works

- `run.sh` builds an image from `Containerfile`: `registry.fedoraproject.org/fedora:<release>`, the packages under test, the harness tools (`wtype grim jq python3-pytest python3-pillow`, D-Bus tools) and an unprivileged user `tester`. It then runs pytest in the container under `dbus-run-session`.
- The `session` fixture (`conftest.py`, `harness/session.py`) starts a fresh sway per test with
  `WLR_BACKENDS=headless`, `WLR_RENDERER=pixman`, `WLR_LIBINPUT_NO_DEVICES=1` and a private `XDG_RUNTIME_DIR`. It waits for the IPC socket and an output (`HEADLESS-1`).
- Helpers on the fixture:

  | Helper | Does |
  |---|---|
  | `keys("super+Return")` | injects a key combo through the virtual-keyboard protocol (`wtype`) |
  | `swaymsg(...)`, `tree()`, `outputs()` | sway IPC, parsed JSON |
  | `windows(app_id=…, window_class=…)` | current views |
  | `wait_for_window(app_id=…, timeout=…)` | first matching window, or `None` |
  | `wait_for_process(name)` | `pgrep -x` until it appears |
  | `screenshot(label)` | PNG via `grim`, numbered, in the test's artifacts folder |
  | `dbus_has_name(name)` | is the name owned on the session bus |

- Teardown keeps `sway.log`, the screenshots and (where a journal exists) `journal.txt` in `artifacts/<test id>/`. `artifacts/junit.xml` has the results; `artifacts/packages.txt` lists the exact package versions tested.

## Profiles

| Profile | Tests | Packages |
|---|---|---|
| `stock` | `tests/stock/`: sway starts with one headless output; `super+Return` opens `foot`; a screenshot is not blank (pixel variance); `swaymsg reload` succeeds; an unbound key opens nothing (negative test) | `sway swaybg foot` (default) |
| `regolith` | `tests/regolith/`: placeholders, all skipped, each naming its Task: trawl resource read (03-02); launcher, bar, notifications, lock screen, look switch, settings app (06-02) | required: `--packages`, usually with `--repo copr:@regolith/regolith-unstable` |

To fill a Regolith placeholder: remove its `skip`, write the assertions with the helpers above, and if it needs the installed Regolith sway config, override the `session_config` fixture in `tests/regolith/conftest.py`.

## Local Loop (agent workstation)

Requirements: podman (rootless is fine) or docker, and network access to `registry.fedoraproject.org` and the Fedora mirrors.

```bash
# one test, about 1–3 minutes the first time (image build), seconds after that
session/run.sh --release 43 --profile stock -k test_super_return_opens_a_terminal

# the whole stock profile on another release
session/run.sh --release 44 --profile stock

# Regolith packages from COPR (once they exist)
session/run.sh --release 44 --profile regolith --packages "regolith-session-sway" \
  --repo copr:@regolith/regolith-unstable
```

Look in `artifacts/` for `junit.xml`, `sway.log` and screenshots. A failing run exits non-zero.

Harness unit tests (no container, no sway):

```bash
cd session && python3 -m unittest discover -s tests/unit -v
```

## Proving the assertions assert

The negative test (`test_unbound_key_opens_no_window`) presses an unbound key and asserts no window opens. Run it inverted and it must **fail**:

```bash
session/run.sh --release 43 --profile stock -k unbound --invert-negative   # expected: 1 failed
```

## In GitHub Actions

`.github/workflows/session-test.yml` is reusable (`workflow_call`, also `workflow_dispatch`). Inputs: `packages`, `profile`, `extra_repo`, `releases` (space-separated, default `43 44 rawhide`), `harness_ref`. The matrix is releases × `ubuntu-24.04` (x86_64) / `ubuntu-24.04-arm` (aarch64), so arm64 runs natively, not under emulation. Rawhide jobs are `continue-on-error`. Each job writes a results table to the job summary and uploads `artifacts/` as `session-<profile>-fedora<release>-<arch>`.

Until Task 01-07 publishes `docs/fedora/targets.json` in voulage, the `releases` input is the Target list.
