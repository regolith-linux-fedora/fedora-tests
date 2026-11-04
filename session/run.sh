#!/usr/bin/env bash
# Session Test runner: build a fedora:<release> test image and run pytest in it.
#
#   session/run.sh --release 43 --profile stock
#   session/run.sh --release 44 --profile regolith --packages "regolith-session-sway" \
#                  --repo copr:@regolith/regolith-unstable
#   session/run.sh --release 43 -k reload          # one test (Local Loop)
#
# Options:
#   --release N        Fedora release or "rawhide" (default 43)
#   --profile P        stock | regolith (default stock) -> runs tests/<P>
#   --packages "..."   packages under test (default for stock: "sway swaybg foot")
#   --repo R           extra repo: copr:<owner>/<project>, a .repo URL, or a baseurl
#   --artifacts DIR    where logs, screenshots and junit.xml go (default ./artifacts)
#   --engine E         podman | docker (default: podman if installed, else docker)
#   --invert-negative  flip the negative test (it must then fail)
#   -k EXPR            pytest -k expression
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
release=43 profile=stock packages="" repo="" artifacts="$PWD/artifacts" engine="" kexpr="" invert=""

while [ $# -gt 0 ]; do
  case "$1" in
    --release)   release="$2"; shift 2 ;;
    --profile)   profile="$2"; shift 2 ;;
    --packages)  packages="$2"; shift 2 ;;
    --repo)      repo="$2"; shift 2 ;;
    --artifacts) artifacts="$2"; shift 2 ;;
    --engine)    engine="$2"; shift 2 ;;
    --invert-negative) invert="--invert-negative"; shift ;;
    -k)          kexpr="$2"; shift 2 ;;
    -h|--help)   sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

case "$profile" in
  stock)    packages="${packages:-sway swaybg foot}" ;;
  regolith) [ -n "$packages" ] || { echo "--profile regolith needs --packages" >&2; exit 2; } ;;
  *) echo "unknown profile: $profile (stock | regolith)" >&2; exit 2 ;;
esac
[ -d "$here/tests/$profile" ] || { echo "no tests for profile $profile" >&2; exit 2; }

if [ -z "$engine" ]; then
  if command -v podman >/dev/null; then engine=podman; else engine=docker; fi
fi

image="fedora-session-test:${release}-${profile}"
echo "== building $image (packages: $packages${repo:+, repo: $repo})"
"$engine" build -t "$image" -f "$here/Containerfile" \
  --build-arg "RELEASE=$release" \
  --build-arg "PACKAGES=$packages" \
  --build-arg "EXTRA_REPO=$repo" \
  "$here"

mkdir -p "$artifacts"
chmod a+rwx "$artifacts"            # the container runs as an unprivileged user

args=("tests/$profile" "--artifacts=/artifacts" "--junitxml=/artifacts/junit.xml")
[ -n "$kexpr" ] && args+=(-k "$kexpr")
[ -n "$invert" ] && args+=("$invert")

echo "== running tests/$profile on fedora:$release ($(uname -m))"
status=0
# Fedora's /usr/bin/sway has the file capability cap_sys_nice=ep; exec fails
# with EPERM unless the container's bounding set includes it.
"$engine" run --rm --security-opt label=disable --cap-add SYS_NICE \
  -v "$artifacts:/artifacts" "$image" "${args[@]}" || status=$?

"$engine" run --rm --entrypoint cat "$image" /etc/session-test-packages.txt > "$artifacts/packages.txt" 2>/dev/null || true
exit $status
