# Boot Test

Fedora Track Task 01-09 (spike) and the base for 06-03: boot a full **Fedora Workstation** VM in QEMU,
log in at **GDM** by injected keystrokes into a **sway** session, and assert on that session. Stock
Fedora packages only; 06-03 adds Regolith.

| File | What it does |
|---|---|
| [`build_image.py`](build_image.py) | Downloads the Fedora Cloud Base Generic qcow2, verifies its SHA256 against Fedora's CHECKSUM (and the CHECKSUM's OpenPGP signature with `gpgv`), grows it to 20 GB, boots it once with a cloud-init seed that runs [`image/provision.sh`](image/provision.sh), and saves the powered-off result. |
| [`image/provision.sh`](image/provision.sh) | Installs `@workstation-product-environment`, `sway`, `foot`; graphical target and GDM; no initial setup; GDM asks for a username (no user list); `tester`'s AccountsService session is `sway`; `WLR_RENDERER=pixman` (no GPU). |
| [`boot_test.py`](boot_test.py) | Boots a copy-on-write overlay of the image and runs the steps below. Writes screenshots, `results.json`, `junit.xml`, the journal and the serial log. |
| [`kvm_probe.py`](kvm_probe.py) | Reports whether QEMU gets working KVM on this machine (`/dev/kvm` plus QMP `query-kvm`). |
| [`vmtest/`](vmtest/) | QEMU launcher (x86_64 q35 + virtio VGA; aarch64 virt + UEFI + virtio-gpu + USB keyboard) and a stdlib QMP client (`screendump`, `send-key`, typing). |
| [`tests/`](tests/) | Unit tests (`python3 -m unittest discover -s boot/tests`) and `smoke_tcg.py`, a no-KVM plumbing check. |

## Steps and assertions

1. **boot**: QEMU with KVM, 4 GB, 2 vCPUs, no display, QMP socket, SSH forwarded; wait for SSH as `tester`.
2. **gdm-greeter**: a `loginctl` session with `Class=greeter`, `Active=yes`, and `gnome-shell` running as `gdm`.
3. **gdm-login**: over QMP, type `tester`, Enter, the password, Enter (retried once). Pass when `tester` has an active `Type=wayland` user session.
4. **sway-session**: that session's `Desktop` is `sway`; `sway` runs as `tester`; `swaymsg -t get_outputs` over the session's IPC socket lists an active output.
5. **foot-via-ipc**: `swaymsg exec foot` adds a `foot` window to `get_tree`.
6. **foot-via-super-return**: an injected Super+Return (Fedora's default `$mod+Return` → `$term` = foot) adds another.

A screenshot (`NN-<step>.png`) is taken after every step, pass or fail.

## Running it

GitHub Actions: [`.github/workflows/boot-test.yml`](../.github/workflows/boot-test.yml) runs nightly, on
`workflow_dispatch`, and on pull requests that touch `boot/`. It probes KVM on `ubuntu-24.04-arm`, builds
or restores the cached image (rebuilt weekly or when `boot/image`, `build_image.py` or `vmtest/` change),
runs the test for x86_64, and for aarch64 only when the ARM runner has KVM.

Locally, on Linux with `/dev/kvm`:

```bash
sudo apt-get install qemu-system-x86 qemu-utils cloud-image-utils gpgv   # or the Fedora equivalents
ssh-keygen -q -t ed25519 -N '' -f cache/id_ed25519
python3 boot/build_image.py --release 44 --arch x86_64 --ssh-pubkey cache/id_ed25519.pub --out cache/boot-44-x86_64.qcow2
python3 boot/boot_test.py --image cache/boot-44-x86_64.qcow2 --arch x86_64 --ssh-key cache/id_ed25519
```

Without KVM (a Mac, Docker), only the plumbing can be checked: `python3 boot/tests/smoke_tcg.py` boots the
stock Cloud image under TCG and exercises SSH and QMP. A Workstation boot under TCG is too slow to be useful.

The release gate on hardware CI can't cover (aarch64 if the ARM runner has no KVM) is
[`MANUAL-CHECKLIST.md`](MANUAL-CHECKLIST.md). The spike's outcome is in [`RESULT.md`](RESULT.md).
