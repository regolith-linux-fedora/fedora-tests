# Boot Test spike (Fedora Task 01-09): result

**Status: go on x86_64; aarch64 not available.** 5 consecutive runs on 2026-11-04 passed every step on
GitHub's standard `ubuntu-24.04` runner with KVM, Fedora 44 (GDM 50.3, sway 1.11-3). GitHub's `ubuntu-24.04-arm`
runner has no `/dev/kvm`.

| Architecture | Outcome | Evidence |
|---|---|---|
| x86_64 (`ubuntu-24.04`, KVM) | **go** | 5 of 5 runs passed, Boot Test 42.8–43.6 s, boot job 7.8–8.9 min |
| aarch64 (`ubuntu-24.04-arm`) | **not-available** | `kvm-probe-aarch64`: `"dev_kvm": false`, qemu "Could not access KVM kernel module: No such file or directory" |

Go means: 5 runs in a row pass every step (boot, gdm-greeter, gdm-login, sway-session, foot-via-ipc,
foot-via-super-return) in under 30 minutes of Boot Test time, with screenshots attached.

## Runs

All five are attempts of [run 41751642734](https://github.com/regolith-linux-fedora/fedora-tests/actions/runs/41751642734) (PR 2, commit 8e04150, Fedora 44, image restored
from the cache built on 2026-11-04 in run 41747443838: provisioned in 3.6 min).

| # | Date (UTC) | Run | Arch | Image | Result | Boot Test time | Boot job |
|---|---|---|---|---|---|---|---|
| 1 | 2026-11-04 01:07 | [attempt 1](https://github.com/regolith-linux-fedora/fedora-tests/actions/runs/41751642734/attempts/1) | x86_64 | cached | PASSED | 43.5 s | 7.9 min |
| 2 | 2026-11-04 01:18 | [attempt 2](https://github.com/regolith-linux-fedora/fedora-tests/actions/runs/41751642734/attempts/2) | x86_64 | cached | PASSED | 42.8 s | 7.8 min |
| 3 | 2026-11-04 01:36 | [attempt 3](https://github.com/regolith-linux-fedora/fedora-tests/actions/runs/41751642734/attempts/3) | x86_64 | cached | PASSED | 43.6 s | 8.0 min |
| 4 | 2026-11-04 01:45 | [attempt 4](https://github.com/regolith-linux-fedora/fedora-tests/actions/runs/41751642734/attempts/4) | x86_64 | cached | PASSED | 43.5 s | 7.9 min |
| 5 | 2026-11-04 01:54 | [attempt 5](https://github.com/regolith-linux-fedora/fedora-tests/actions/runs/41751642734/attempts/5) | x86_64 | cached | PASSED | 43.5 s | 8.9 min |

Fedora 45 (PR 3, the default since then):

| # | Date (UTC) | Run | Arch | Image | Result | Boot Test time | Boot job |
|---|---|---|---|---|---|---|---|
| 6 | 2026-11-04 08:21 | [41798738128](https://github.com/regolith-linux-fedora/fedora-tests/actions/runs/41798738128) | x86_64 | built (provisioned in 3.6 min) | PASSED | 44.3 s | 9.1 min |

Run 6 used gdm-51.0-1.fc45, gnome-shell-51.1-1.fc45, sway-1.12-2.fc45 and foot-1.28.0-1.fc45, with no harness change.

No flaky step in the five runs. Most of the boot job is freeing disk space, installing QEMU and restoring the
cached image; the Boot Test itself is under a minute.

## First-run fixes (2026-11-04)

- [Run 41747443838](https://github.com/regolith-linux-fedora/fedora-tests/actions/runs/41747443838): gdm-greeter timed out after 300 s. GDM 49 and later run the greeter as
  the dynamic user `gdm-greeter`, not `gdm`, so `pgrep -u gdm -x gnome-shell` never matched although session
  `c1` (class greeter) was active. Fixed in f2b58b1: use the greeter session's user.
- [Run 41750206513](https://github.com/regolith-linux-fedora/fedora-tests/actions/runs/41750206513): sway-session failed with "session desktop is '', expected sway" although
  sway was running (screenshot shows the sway desktop). On GDM 50 logind reports `Desktop=` empty for every
  session. Fixed in 8e04150: when `Desktop` isn't `sway`, require a sway process in `session-<Id>.scope`.

## What is already known (local, 2026-10-22)

- Unit tests (`python3 -m unittest discover -s boot/tests`): 8 pass. cloud-init `schema --config-file` on
  the rendered user-data: valid.
- TCG plumbing smoke (`boot/tests/smoke_tcg.py`) in an `ubuntu:24.04` container on an Apple M1 Max (no KVM):
  the Fedora 44 Cloud CHECKSUM signature and image SHA256 verify; the stock image boots to SSH in 117 to 132 s
  under emulation (2 runs); the `loginctl` parser, QMP `screendump` (PNG) and `send-key` typing work (the
  typed username shows in full at the console login prompt 5 s later; a screenshot taken immediately showed
  3 of 6 characters, because TCG redraws slowly).
- `kvm_probe.py` in that container: `dev_kvm: false`, `kvm: false` (expected).
- Not exercised yet: Workstation provisioning, GDM, the sway login, aarch64 UEFI boot.

## Manual fallback

[`MANUAL-CHECKLIST.md`](MANUAL-CHECKLIST.md) (aarch64 Fedora Workstation in Parallels on Apple Silicon).
Dry-run: _not yet_ (needs a human at a VM; the automated test covers the same steps on x86_64).

## Recommendation

Run the Boot Test on x86_64 standard runners (KVM works; about 8 minutes per run with the cached image). Keep
the nightly schedule once this is on `main`. aarch64 needs a runner with KVM (larger or self-hosted arm64);
until then aarch64 stays covered by the Session Test (containers, native arm64) and the manual checklist. The
default release is 45, the newest blocking Target; move it when a newer release becomes `current`.
