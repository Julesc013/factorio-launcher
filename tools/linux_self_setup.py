#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Build the self-contained per-user Linux FacMan setup executable."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MARKER = "__FACMAN_PAYLOAD_BELOW__"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def version_truth() -> str:
    with (ROOT / "release/index/version.v2.toml").open("rb") as stream:
        return str(tomllib.load(stream)["semver"])


def git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def header(version: str, payload_sha256: str) -> bytes:
    script = r'''#!/bin/sh
set -eu

version='@VERSION@'
payload_sha256='@PAYLOAD_SHA256@'
operation='install'
apply='false'
quiet='false'
install_root="${HOME}/.local/opt/facman"

if [ "$#" -gt 0 ]; then
  case "$1" in
    install|verify|repair|uninstall) operation="$1"; shift ;;
    --help|-h|help)
      echo "FacMan setup @VERSION@"
      echo "Usage: $0 [install|verify|repair|uninstall] [--yes] [--root PATH] [--quiet]"
      exit 0 ;;
    --version) echo '@VERSION@'; exit 0 ;;
  esac
fi
while [ "$#" -gt 0 ]; do
  case "$1" in
    --yes) apply='true' ;;
    --quiet) quiet='true'; apply='true' ;;
    --root) shift; [ "$#" -gt 0 ] || { echo 'missing --root value' >&2; exit 2; }; install_root="$1" ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

case "$install_root" in
  ''|'/'|"$HOME") echo 'refusing unsafe install root' >&2; exit 3 ;;
esac

generation="$install_root/generations/$version"
current="$install_root/current"
state="$install_root/state"
maintenance="$install_root/maintenance"
user_bin="${HOME}/.local/bin"
desktop_root="${HOME}/.local/share/applications"

payload_line=$(awk '/^__FACMAN_PAYLOAD_BELOW__$/ { print NR + 1; exit }' "$0")
[ -n "$payload_line" ] || { echo 'embedded payload marker is missing' >&2; exit 4; }

verify_generation() {
  target="$1"
  manifest="$target/share/facman/manifest/MANIFEST.sha256"
  [ -f "$manifest" ] || { echo 'FacMan manifest is missing' >&2; return 1; }
  (cd "$target" && sha256sum -c 'share/facman/manifest/MANIFEST.sha256' >/dev/null)
  [ -x "$target/FacMan" ] && [ -x "$target/facman" ]
}

assert_owned_generation() {
  target="$1"
  [ -f "$state/installed-state.v1.json" ] || {
    echo 'refusing to replace or remove a generation without FacMan installed state' >&2
    return 1
  }
  [ -f "$target/share/facman/manifest/MANIFEST.sha256" ] || {
    echo 'refusing to replace or remove a generation without its ownership manifest' >&2
    return 1
  }
  actual=$(mktemp "${TMPDIR:-/tmp}/facman-actual.XXXXXX")
  expected=$(mktemp "${TMPDIR:-/tmp}/facman-expected.XXXXXX")
  find "$target" \( -type f -o -type l \) -printf '%P\n' | sort > "$actual"
  {
    sed -n 's/^[0-9a-fA-F][0-9a-fA-F]*  //p' \
      "$target/share/facman/manifest/MANIFEST.sha256"
    echo 'share/facman/manifest/MANIFEST.sha256'
  } | sort > "$expected"
  if ! cmp -s "$actual" "$expected"; then
    rm -f "$actual" "$expected"
    echo 'refusing to replace or remove a generation containing foreign files' >&2
    return 1
  fi
  rm -f "$actual" "$expected"
}

if [ "$operation" = 'verify' ]; then
  [ -d "$generation" ] && verify_generation "$generation"
  echo "FacMan $version verified"
  exit 0
fi

if [ "$operation" = 'uninstall' ]; then
  if [ "$apply" != 'true' ]; then
    echo "Plan: remove FacMan $version application files from $install_root; preserve all workspaces."
    exit 0
  fi
  if [ -e "$generation" ]; then
    assert_owned_generation "$generation"
  fi
  for link in "$user_bin/facman" "$user_bin/FacMan"; do
    if [ -L "$link" ]; then
      target=$(readlink "$link" || true)
      case "$target" in "$install_root"/*) rm -f "$link" ;; esac
    fi
  done
  desktop="$desktop_root/facman.desktop"
  if [ -f "$desktop" ] && grep -Fq "$install_root" "$desktop"; then rm -f "$desktop"; fi
  rm -f "$current"
  if [ -e "$generation" ]; then
    rm -rf "$generation"
  fi
  rm -f "$maintenance/FacManSetup.run" "$state/installed-state.v1.json"
  rmdir "$maintenance" "$state" "$install_root/generations" "$install_root" 2>/dev/null || true
  echo "FacMan $version uninstalled; workspaces were not touched"
  exit 0
fi

if [ "$apply" != 'true' ] && [ -t 0 ]; then
  printf 'Install FacMan %s for this user at %s? [y/N] ' "$version" "$install_root"
  read answer
  case "$answer" in y|Y|yes|YES) apply='true' ;; *) echo 'Cancelled'; exit 0 ;; esac
fi
if [ "$apply" != 'true' ]; then
  echo "Plan: install FacMan $version for the current user at $install_root"
  echo "Repeat with --yes to apply non-interactively."
  exit 0
fi

temporary=$(mktemp -d "${TMPDIR:-/tmp}/facman-setup.XXXXXX")
trap 'rm -rf "$temporary"' EXIT HUP INT TERM
payload="$temporary/payload.tar.zst"
tail -n "+$payload_line" "$0" > "$payload"
printf '%s  %s\n' "$payload_sha256" "$payload" | sha256sum -c - >/dev/null
tar --zstd -xf "$payload" -C "$temporary"
source_root="$temporary/FacMan-$version"
verify_generation "$source_root"

if [ -e "$generation" ]; then
  assert_owned_generation "$generation"
fi
mkdir -p "$install_root/generations" "$maintenance" "$state" "$user_bin" "$desktop_root"
staging="$install_root/generations/.install-$version-$$"
rm -rf "$staging"
cp -a "$source_root" "$staging"
verify_generation "$staging"
if [ -e "$generation" ]; then
  rm -rf "$generation"
fi
mv "$staging" "$generation"
ln -sfn "$generation" "$current"
ln -sfn "$current/facman" "$user_bin/facman"
ln -sfn "$current/FacMan" "$user_bin/FacMan"
cp "$0" "$maintenance/FacManSetup.run"
chmod 0755 "$maintenance/FacManSetup.run"
cat > "$desktop_root/facman.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=FacMan
Comment=Manage Factorio installations and isolated instances
Exec=$current/FacMan
Terminal=false
Categories=Game;Utility;
EOF
cat > "$state/installed-state.v1.json" <<EOF
{"schema":"facman.installed_state.v1","version":"$version","generation":"$generation","workspace_preserved":true}
EOF
verify_generation "$generation"
[ "$quiet" = 'true' ] || echo "FacMan $version installed for the current user"
exit 0

__FACMAN_PAYLOAD_BELOW__
'''
    return script.replace("@VERSION@", version).replace("@PAYLOAD_SHA256@", payload_sha256).encode()


def build(portable: Path, output: Path, evidence: Path) -> dict[str, object]:
    portable = portable.resolve(strict=True)
    version = version_truth()
    expected = f"FacMan-{version}-linux-x64-portable.tar.zst"
    if portable.name != expected:
        raise ValueError(f"unexpected Linux portable input: {portable.name}")
    output.mkdir(parents=True, exist_ok=True)
    setup = output / f"FacMan-{version}-linux-x64-setup.run"
    setup.write_bytes(header(version, sha256(portable)) + portable.read_bytes())
    setup.chmod(0o755)
    record = {
        "schema": "facman.linux_self_setup.v1",
        "status": "pass",
        "version": version,
        "platform": "linux",
        "architecture": "x64",
        "source_revision": git("rev-parse", "HEAD"),
        "source_tree": git("rev-parse", "HEAD^{tree}"),
        "portable_input": {"filename": portable.name, "sha256": sha256(portable)},
        "setup": {
            "filename": setup.name,
            "bytes": setup.stat().st_size,
            "sha256": sha256(setup),
            "self_contained": True,
            "offline": True,
            "default_scope": "per_user_non_administrator",
            "install_root": "~/.local/opt/facman",
        },
        "authority": {"signed": False, "support": False, "system_install": False},
    }
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--portable", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    if git("status", "--porcelain") and not args.allow_dirty:
        raise SystemExit("refusing Linux setup from a dirty source tree")
    record = build(args.portable, args.out.resolve(), args.evidence.resolve())
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
