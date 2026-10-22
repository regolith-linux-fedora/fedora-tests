#!/bin/bash
# Runs once inside the Fedora Cloud Base VM (cloud-init runcmd) and turns it into a
# Fedora Workstation that boots to GDM, with user "tester" defaulting to the sway session.
# Stock Fedora packages only. Ends with a marker on the console that build_image.py checks.
set -euxo pipefail

marker() { echo "BOOT-TEST-PROVISION: $*" | tee /dev/console; }
trap 'marker FAILED at line $LINENO' ERR

dnf -y install @workstation-product-environment sway foot swaybg jq
dnf -y remove gnome-initial-setup || true

systemctl set-default graphical.target
systemctl enable gdm

# No first-run wizard, Wayland on.
cat > /etc/gdm/custom.conf <<'EOF'
[daemon]
InitialSetupEnable=false
WaylandEnable=true

[security]

[xdmcp]

[chooser]

[debug]
EOF

# Keyboard-only login: GDM asks for a username instead of showing a user list,
# so the test types "tester", Enter, password, Enter.
mkdir -p /etc/dconf/profile /etc/dconf/db/gdm.d
cat > /etc/dconf/profile/gdm <<'EOF'
user-db:user
system-db:gdm
file-db:/usr/share/gdm/greeter-dconf-defaults
EOF
cat > /etc/dconf/db/gdm.d/00-boot-test <<'EOF'
[org/gnome/login-screen]
disable-user-list=true
EOF
dconf update

# The login still goes through GDM's password prompt; AccountsService picks the session.
mkdir -p /var/lib/AccountsService/users
cat > /var/lib/AccountsService/users/tester <<'EOF'
[User]
Session=sway
SystemAccount=false
EOF
chmod 0600 /var/lib/AccountsService/users/tester

# No GPU in the VM: wlroots renders with pixman.
cat >> /etc/environment <<'EOF'
WLR_RENDERER=pixman
WLR_NO_HARDWARE_CURSORS=1
EOF

install -d -o tester -g tester /home/tester/.config
echo yes > /home/tester/.config/gnome-initial-setup-done
chown tester:tester /home/tester/.config/gnome-initial-setup-done
restorecon -RF /etc/gdm /etc/dconf /var/lib/AccountsService /home/tester || true

# Later boots have no seed: don't let cloud-init search for one.
touch /etc/cloud/cloud-init.disabled

dnf clean all
fstrim -av || true

marker "OK $(rpm -q --qf '%{name}-%{version}-%{release} ' gdm gnome-shell sway foot)"
