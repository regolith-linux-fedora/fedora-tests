# fedora-tests

Automated tests for the Regolith Fedora port (`regolith-linux-fedora`). Two layers:

| Layer | Directory | What it proves | Plan Tasks |
|---|---|---|---|
| **Session Test** | [`session/`](session/) | A sway session started **headlessly inside a Fedora container**, driven like a user through sway IPC, injected keystrokes (`wtype`), screenshots (`grim`) and D-Bus. Fast, no GPU, runs on GitHub-hosted runners for every Target on x86_64 and aarch64. | 01-08 (harness, stock profile), 03-02 and 06-02 (Regolith checks) |
| **Boot Test** | [`boot/`](boot/) | A full Fedora Workstation VM booted to GDM and logged in to the Regolith Wayland Session. | 01-09 (spike), 06-03 |

Both layers attach screenshots to every run. Neither is a golden-image comparison: tests assert on state (IPC, D-Bus, processes) and keep screenshots as evidence.

## Session Test in one minute

```bash
session/run.sh --release 43 --profile stock               # everything, stock sway + foot
session/run.sh --release 44 --profile stock -k reload     # one test
```

Results (sway log, screenshots, `junit.xml`) land in `./artifacts/`. Details, the Local Loop and how to add Regolith checks: [`session/README.md`](session/README.md).

In GitHub Actions, call the reusable workflow:

```yaml
jobs:
  session-test:
    uses: regolith-linux-fedora/fedora-tests/.github/workflows/session-test.yml@main
    with:
      profile: regolith
      packages: "regolith-session-sway"
      extra_repo: "copr:@regolith/regolith-unstable"
```

This repo's own [CI](.github/workflows/ci.yml) runs the harness unit tests and the stock profile on every Target and both architectures.
