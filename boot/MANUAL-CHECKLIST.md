# Manual Boot Test: Fedora Workstation (aarch64) in Parallels on Apple Silicon

The release-gate fallback for an architecture CI can't boot (see [`RESULT.md`](RESULT.md)). It repeats
the automated Boot Test's assertions by hand. About 45 minutes the first time, 15 after that (reuse the
VM from a snapshot).

> **Validation status:** written 2026-10-22. It has **not** been dry-run yet: the agent that wrote it can't drive a
> desktop VM application from its session. Steps marked *(unverified)* are
> taken from Fedora's and Parallels' documentation. The first person to run it should correct anything
> that differs and remove the marks.

Placeholders: `<N>` is the Fedora release under test (a blocking Target from
`regolith-linux-fedora/voulage` `docs/fedora/targets.json`), `<project>` is the COPR project being
released (`regolith-testing` for a release candidate). For the 01-09 spike, skip step 4: stock Fedora only.

## 1. Get the image

1. Download `Fedora-Workstation-Live-<N>-<compose>.aarch64.iso` and `Fedora-Workstation-<N>-<compose>-aarch64-CHECKSUM` from
   `https://dl.fedoraproject.org/pub/fedora/linux/releases/<N>/Workstation/aarch64/iso/`
   (for Fedora 44: `Fedora-Workstation-Live-44-1.7.aarch64.iso`).
2. Verify it in Terminal:
   ```bash
   curl -O https://fedoraproject.org/fedora.gpg
   gpgv --keyring ./fedora.gpg Fedora-Workstation-*-aarch64-CHECKSUM   # "Good signature from Fedora (<N>)"
   shasum -a 256 -c Fedora-Workstation-*-aarch64-CHECKSUM --ignore-missing
   ```
   *(unverified: macOS has no `gpgv` by default; install GnuPG, or skip the signature and keep the SHA256 check)*

## 2. Create the VM *(unverified)*

1. Parallels Desktop → **File → New → Install Windows, Linux or macOS from an image file** → choose the ISO.
2. Name it `fedora-<N>-boot-test`. Before the first start, **Configure**: 2 CPUs, 4096 MB memory, 64 GB disk,
   Graphics: default (no 3D needed), Network: Shared.
3. Start the VM, choose **Start Fedora-Workstation-Live**, then **Install Fedora** in the live session.
4. Install to the whole disk with defaults. In the first-boot setup create user `tester` with a password
   you write down. Reboot, log in once at GDM to GNOME, and run `sudo dnf -y upgrade --refresh`; reboot.
5. Take a Parallels snapshot named `clean-<N>`.

## 3. Install what is being tested

Stock (01-09 spike):

```bash
sudo dnf -y install sway foot swaybg jq
```

## 4. Enable the Regolith COPR and install the Regolith session (06-03 onward)

```bash
sudo dnf -y copr enable @regolith/<project>
sudo dnf -y install regolith-desktop regolith-session-sway      # package names as released
```

## 5. Log in through GDM

1. Log out (top-right menu → Power → Log Out).
2. At GDM click `tester`. Before typing the password, click the **gear** at the bottom right and choose
   **Sway** (06-03: the Regolith Wayland Session). *(unverified: the gear appears only after selecting the user)*
3. Type the password and press Enter.
4. **Expected:** a sway (Regolith) session; no GNOME Shell top bar.

## 6. Assertions

Press **Super+Return**. **Expected:** a foot terminal opens (this is the injected-key check of the automated test).
In it, run each command and compare:

| # | Command | Expected |
|---|---|---|
| 1 | `loginctl show-session $XDG_SESSION_ID -p Type -p Desktop -p Class -p Active` | `Type=wayland`, `Desktop=sway` (06-03: the Regolith session name), `Class=user`, `Active=yes` |
| 2 | `pgrep -u "$USER" -x sway` | one PID |
| 3 | `echo $SWAYSOCK && swaymsg -t get_outputs \| jq -r '.[] \| select(.active) \| .name'` | a socket path, then at least one output name (e.g. `Virtual-1`) |
| 4 | `swaymsg exec foot; sleep 2; swaymsg -t get_tree \| jq '[.. \| objects \| select(.app_id? == "foot")] \| length'` | `2` or more (this terminal plus the new one) |
| 5 | `cat /etc/fedora-release; uname -m; rpm -q sway foot gdm` | Fedora `<N>`, `aarch64`, the package versions to record |

Take a screenshot after step 5 (Parallels → **Actions → Take Screenshot**) and after the assertions.

## 7. Record the result

Add a row to the run log in [`RESULT.md`](RESULT.md) (or, for a release, to the sign-off issue of Fedora Task 07-04):

```markdown
| date | Fedora <N> aarch64 | Parallels <version> on <Mac model>, macOS <version> | pass/fail | steps that failed | screenshots link | tester |
```

A failure in any of sections 5 or 6 fails the gate. Restore the `clean-<N>` snapshot before the next run.
