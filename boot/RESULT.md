# Boot Test spike (Fedora Task 01-09): result

**Status: pending.** The harness and workflow exist; no GitHub Actions run has happened yet because the
repository isn't on GitHub yet. Fill in this page from the first 5 consecutive runs of
[`boot-test.yml`](../.github/workflows/boot-test.yml).

| Architecture | Outcome | Evidence |
|---|---|---|
| x86_64 (`ubuntu-24.04`, KVM) | _pending_ (go / no-go) | 5 run links, durations |
| aarch64 (`ubuntu-24.04-arm`) | _pending_ (go / no-go / not-available) | `kvm-probe-aarch64` artifact; if KVM works, 5 run links |

Go means: 5 runs in a row pass every step (boot, gdm-greeter, gdm-login, sway-session, foot-via-ipc,
foot-via-super-return) in under 30 minutes of Boot Test time, with screenshots attached.

## Runs

| # | Date | Run | Arch | Image | Result | Boot Test time | Notes |
|---|---|---|---|---|---|---|---|
| 1 | | | | built / cached | | | |
| 2 | | | | | | | |
| 3 | | | | | | | |
| 4 | | | | | | | |
| 5 | | | | | | | |

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
Dry-run: _not yet_.

## Recommendation

_To write after the runs._ If x86_64 is no-go on standard runners, compare larger runners or a self-hosted
KVM machine here for a human to decide (out of scope for the agent).
