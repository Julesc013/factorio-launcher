#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Build the self-contained per-user Linux FacMan setup executable."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
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
    install|verify|repair|uninstall|recover|rollback) operation="$1"; shift ;;
    --help|-h|help)
      echo "FacMan setup @VERSION@"
      echo "Usage: $0 [install|verify|repair|uninstall|recover|rollback] [--yes] [--root PATH] [--quiet]"
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
  /*) ;;
  *) echo 'install root must be an absolute path' >&2; exit 3 ;;
esac

generation="$install_root/generations/$version"
current="$install_root/current"
state="$install_root/state"
maintenance="$install_root/maintenance"
user_bin="${HOME}/.local/bin"
desktop_root="${HOME}/.local/share/applications"
pending="$state/update-pending.v1"
rollback_record="$state/rollback.v1"

for protected_root in "$install_root" "$install_root/generations" "$state" "$maintenance" "$user_bin" "$desktop_root"; do
  if [ -L "$protected_root" ]; then
    echo 'refusing setup through a linked FacMan effect root' >&2
    exit 3
  fi
done

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

assert_active_generation() {
  receipt="$state/installed-state.v1.json"
  expected_receipt=$(printf '{"schema":"facman.installed_state.v1","version":"%s","generation":"%s","workspace_preserved":true}' "$version" "$generation")
  if [ ! -f "$receipt" ] || [ -L "$receipt" ] ||
     [ "$(cat "$receipt")" != "$expected_receipt" ]; then
    echo 'refusing maintenance without this exact FacMan installed state' >&2
    return 1
  fi
  if [ ! -L "$current" ] || [ "$(readlink "$current")" != "$generation" ]; then
    echo 'refusing maintenance when the active generation is foreign or changed' >&2
    return 1
  fi
}

assert_existing_install_owner() {
  receipt="$state/installed-state.v1.json"
  if [ ! -e "$current" ] && [ ! -L "$current" ] &&
     [ ! -e "$receipt" ] && [ ! -L "$receipt" ]; then
    return 0
  fi
  if [ ! -L "$current" ] || [ ! -f "$receipt" ] || [ -L "$receipt" ]; then
    echo 'refusing install over incomplete or foreign FacMan state' >&2
    return 1
  fi
  old_target=$(readlink "$current")
  case "$old_target" in
    "$install_root/generations/"*) ;;
    *) echo 'refusing install over foreign active generation' >&2; return 1 ;;
  esac
  old_version=${old_target##*/}
  if [ -z "$old_version" ] ||
     [ "$old_target" != "$install_root/generations/$old_version" ] ||
     [ ! -d "$old_target" ] || [ -L "$old_target" ]; then
    echo 'refusing install over ambiguous active generation' >&2
    return 1
  fi
  expected_receipt=$(printf '{"schema":"facman.installed_state.v1","version":"%s","generation":"%s","workspace_preserved":true}' "$old_version" "$old_target")
  if [ "$(cat "$receipt")" != "$expected_receipt" ]; then
    echo 'refusing install over changed FacMan installed state' >&2
    return 1
  fi
  assert_owned_generation "$old_target"
}

assert_native_integration_owned() {
  for name in facman FacMan; do
    link="$user_bin/$name"
    if [ -e "$link" ] || [ -L "$link" ]; then
      if { [ "$operation" = 'install' ] && [ ! -L "$current" ]; } ||
         [ ! -L "$link" ] || [ "$(readlink "$link")" != "$current/$name" ]; then
        echo 'refusing foreign FacMan terminal link' >&2
        return 1
      fi
    fi
  done
  desktop="$desktop_root/facman.desktop"
  if [ -e "$desktop" ] || [ -L "$desktop" ]; then
    expected_desktop=$(printf '[Desktop Entry]\nType=Application\nName=FacMan\nComment=Manage Factorio installations and isolated instances\nExec=%s/FacMan\nTerminal=false\nCategories=Game;Utility;\n' "$current")
    if { [ "$operation" = 'install' ] && [ ! -L "$current" ]; } ||
       [ ! -f "$desktop" ] || [ -L "$desktop" ] ||
       [ "$(cat "$desktop")" != "$expected_desktop" ]; then
      echo 'refusing foreign FacMan desktop entry' >&2
      return 1
    fi
  fi
}

assert_setup_copy_safe() {
  setup_copy="$maintenance/FacManSetup.run"
  if [ -e "$setup_copy" ] || [ -L "$setup_copy" ]; then
    if [ ! -f "$setup_copy" ] || [ -L "$setup_copy" ] ||
       { [ "$operation" = 'install' ] && [ ! -L "$current" ]; } ||
       { [ "$operation" = 'repair' ] && ! cmp -s "$0" "$setup_copy"; }; then
      echo 'refusing a foreign or changed FacMan setup copy' >&2
      return 1
    fi
  fi
}

temporary=''
active_staging=''
current_staging=''
journal_staging=''
archive_staging=''
trap 'if [ -n "$temporary" ]; then rm -rf "$temporary"; fi
      if [ -n "$active_staging" ]; then rm -f "$active_staging"; fi
      if [ -n "$current_staging" ]; then rm -f "$current_staging"; fi
      if [ -n "$journal_staging" ]; then rm -rf "$journal_staging"; fi
      if [ -n "$archive_staging" ]; then rm -rf "$archive_staging"; fi' EXIT HUP INT TERM

lock_setup() {
  lock_root="${HOME}/.local/state/facman-setup"
  for protected_root in "${HOME}/.local" "${HOME}/.local/state" "$lock_root"; do
    if [ -L "$protected_root" ]; then
      echo 'refusing setup through a linked lock root' >&2
      return 1
    fi
  done
  mkdir -p "$lock_root"
  # Path aliases for the same install must contend on the same lock.
  lock_identity=$(realpath -m -- "$install_root")
  lock_key=$(printf '%s' "$lock_identity" | sha256sum | cut -c 1-32)
  lock_file="$lock_root/$lock_key.lock"
  if [ -L "$lock_file" ]; then
    echo 'refusing a linked setup lock file' >&2
    return 1
  fi
  exec 9>> "$lock_file"
  flock -x 9
  history_root="$lock_root/history/$lock_key"
}

archive_record() {
  record="$1"
  event="$2"
  if [ ! -d "$record" ] || [ -L "$record" ]; then
    echo 'refusing to archive a changed Linux Setup record' >&2
    return 1
  fi
  for protected_root in "$lock_root/history" "$history_root"; do
    if [ -L "$protected_root" ]; then
      echo 'refusing linked Linux Setup history' >&2
      return 1
    fi
  done
  mkdir -p "$history_root"
  history_target="$history_root/$event-$(date +%s%N)-$$"
  if [ -e "$history_target" ] || [ -L "$history_target" ]; then
    echo 'refusing existing Linux Setup history identity' >&2
    return 1
  fi
  archive_staging=$(mktemp -d "$history_root/.archive-XXXXXX")
  cp -a "$record/." "$archive_staging/"
  diff -qr "$record" "$archive_staging" >/dev/null
  mv -T "$archive_staging" "$history_target"
  archive_staging=''
  if [ ! -d "$record" ] || [ -L "$record" ]; then
    echo 'refusing to remove a changed Linux Setup record' >&2
    return 1
  fi
  rm -rf "$record"
}

assert_no_orphan_staging() {
  for directory in "$state" "$install_root/generations"; do
    [ -d "$directory" ] || continue
    if [ "$directory" = "$state" ]; then
      orphan=$(find "$directory" -mindepth 1 -maxdepth 1 -name '.update-prepared-*' -print -quit)
    else
      orphan=$(find "$directory" -mindepth 1 -maxdepth 1 -name '.install-*' -print -quit)
    fi
    if [ -n "$orphan" ]; then
      echo "refusing incomplete Linux Setup staging at $orphan" >&2
      return 1
    fi
  done
}

replace_file() {
  source="$1"
  destination="$2"
  mode="$3"
  active_staging=$(mktemp "${destination}.XXXXXX")
  cp "$source" "$active_staging"
  chmod "$mode" "$active_staging"
  mv -fT "$active_staging" "$destination"
  active_staging=''
}

point_current() {
  target="$1"
  current_staging="$install_root/.current-$$"
  if [ -e "$current_staging" ] || [ -L "$current_staging" ]; then
    echo 'refusing a preexisting current staging path' >&2
    return 1
  fi
  ln -s "$target" "$current_staging"
  mv -fT "$current_staging" "$current"
  current_staging=''
}

restore_update_record() {
  record="$1"
  mode="${2:-apply}"
  if [ ! -d "$record" ] || [ -L "$record" ]; then
    echo 'refusing an invalid Linux Setup update record' >&2
    return 1
  fi
  for name in old-target new-target old-receipt old-setup new-setup-sha256; do
    if [ ! -f "$record/$name" ] || [ -L "$record/$name" ]; then
      echo 'refusing an incomplete Linux Setup update record' >&2
      return 1
    fi
  done
  record_entries=$(find "$record" -mindepth 1 -maxdepth 1 -printf '%f\n' | sort)
  expected_entries=$(printf '%s\n' new-setup-sha256 new-target old-receipt old-setup old-target)
  if [ "$record_entries" != "$expected_entries" ]; then
    echo 'refusing foreign content in Linux Setup update record' >&2
    return 1
  fi
  old_target=$(cat "$record/old-target")
  new_target=$(cat "$record/new-target")
  old_version=${old_target##*/}
  case "$old_target" in
    "$install_root/generations/$old_version") ;;
    *) echo 'refusing a foreign previous generation' >&2; return 1 ;;
  esac
  case "$old_version" in
    ''|*[!A-Za-z0-9.+-]*) echo 'refusing an invalid previous version' >&2; return 1 ;;
  esac
  if [ "$new_target" != "$generation" ] || [ "$old_target" = "$new_target" ]; then
    echo 'refusing a changed update target' >&2
    return 1
  fi
  expected_old=$(printf '{"schema":"facman.installed_state.v1","version":"%s","generation":"%s","workspace_preserved":true}' "$old_version" "$old_target")
  expected_new=$(printf '{"schema":"facman.installed_state.v1","version":"%s","generation":"%s","workspace_preserved":true}' "$version" "$new_target")
  if [ "$(cat "$record/old-receipt")" != "$expected_old" ] ||
     [ ! -f "$state/installed-state.v1.json" ] ||
     [ -L "$state/installed-state.v1.json" ]; then
    echo 'refusing a changed update receipt' >&2
    return 1
  fi
  receipt_now=$(cat "$state/installed-state.v1.json")
  if [ "$receipt_now" != "$expected_old" ] && [ "$receipt_now" != "$expected_new" ]; then
    echo 'refusing an ambiguous update receipt' >&2
    return 1
  fi
  if [ ! -L "$current" ]; then
    echo 'refusing an absent update current pointer' >&2
    return 1
  fi
  current_now=$(readlink "$current")
  if [ "$current_now" != "$old_target" ] && [ "$current_now" != "$new_target" ]; then
    echo 'refusing a foreign update current pointer' >&2
    return 1
  fi
  previous_setup_sha=$(sha256sum "$record/old-setup" | cut -d ' ' -f 1)
  new_setup_sha=$(cat "$record/new-setup-sha256")
  if [ "$new_setup_sha" != "$(sha256sum "$0" | cut -d ' ' -f 1)" ] ||
     [ ! -f "$maintenance/FacManSetup.run" ] ||
     [ -L "$maintenance/FacManSetup.run" ]; then
    echo 'refusing a changed update source' >&2
    return 1
  fi
  installed_setup_sha=$(sha256sum "$maintenance/FacManSetup.run" | cut -d ' ' -f 1)
  if [ "$installed_setup_sha" != "$previous_setup_sha" ] &&
     [ "$installed_setup_sha" != "$new_setup_sha" ]; then
    echo 'refusing a foreign installed setup source' >&2
    return 1
  fi
  verify_generation "$old_target"
  assert_native_integration_owned
  if [ -e "$new_target" ] || [ -L "$new_target" ]; then
    [ -d "$new_target" ] && [ ! -L "$new_target" ] || return 1
    assert_owned_generation "$new_target"
  fi
  if [ "$mode" = 'check' ]; then
    return 0
  fi
  point_current "$old_target"
  replace_file "$record/old-receipt" "$state/installed-state.v1.json" 0600
  replace_file "$record/old-setup" "$maintenance/FacManSetup.run" 0755
  if [ -e "$new_target" ] || [ -L "$new_target" ]; then
    assert_owned_generation "$new_target"
    rm -rf "$new_target"
  fi
  archive_record "$record" "restored-${old_version}-to-${version}"
}

if [ "$operation" = 'verify' ]; then
  if [ -e "$pending" ] || [ -L "$pending" ]; then
    echo 'Linux Setup update recovery is required before verification' >&2
    exit 1
  fi
  assert_active_generation
  [ -d "$generation" ] && [ ! -L "$generation" ] && verify_generation "$generation" || {
    echo 'FacMan active generation is missing or damaged' >&2
    exit 1
  }
  echo "FacMan $version verified"
  exit 0
fi

if [ "$operation" = 'recover' ] || [ "$operation" = 'rollback' ]; then
  if [ "$apply" != 'true' ]; then
    echo "Plan: restore the preceding FacMan generation at $install_root"
    exit 0
  fi
  lock_setup
  assert_no_orphan_staging
  if [ "$operation" = 'recover' ]; then
    restore_update_record "$pending"
    echo 'Interrupted Linux Setup update restored the preceding generation'
  else
    if [ -e "$pending" ] || [ -L "$pending" ]; then
      echo 'recover the interrupted update before rollback' >&2
      exit 1
    fi
    restore_update_record "$rollback_record"
    echo 'Linux Setup restored the preceding generation'
  fi
  exit 0
fi

if [ "$operation" = 'uninstall' ]; then
  if [ "$apply" != 'true' ]; then
    echo "Plan: remove FacMan $version application files from $install_root; preserve all workspaces."
    exit 0
  fi
  lock_setup
  assert_no_orphan_staging
  if [ -e "$pending" ] || [ -L "$pending" ]; then
    echo 'recover the interrupted update before uninstall' >&2
    exit 1
  fi
  assert_active_generation
  assert_native_integration_owned
  if [ -e "$generation" ] || [ -L "$generation" ]; then
    assert_owned_generation "$generation"
  fi
  if [ -e "$rollback_record" ] || [ -L "$rollback_record" ]; then
    restore_update_record "$rollback_record" check
  fi
  if [ -d "$install_root/generations" ]; then
    hidden_generation=$(find "$install_root/generations" -mindepth 1 -maxdepth 1 -name '.*' -print -quit)
    if [ -n "$hidden_generation" ]; then
      echo 'refusing hidden or interrupted generation during uninstall' >&2
      exit 1
    fi
    for owned_generation in "$install_root/generations/"*; do
      if [ -e "$owned_generation" ] || [ -L "$owned_generation" ]; then
        [ -d "$owned_generation" ] && [ ! -L "$owned_generation" ] || exit 1
        assert_owned_generation "$owned_generation"
      fi
    done
  fi
  setup_copy="$maintenance/FacManSetup.run"
  if [ -e "$setup_copy" ] || [ -L "$setup_copy" ]; then
    if [ ! -f "$setup_copy" ] || [ -L "$setup_copy" ] ||
       ! cmp -s "$0" "$setup_copy"; then
      echo 'refusing to remove a changed FacMan setup copy' >&2
      exit 1
    fi
  fi
  if [ -d "$rollback_record" ]; then
    for protected_root in "$lock_root/history" "$history_root"; do
      if [ -L "$protected_root" ]; then
        echo 'refusing linked Linux Setup history' >&2
        exit 1
      fi
    done
    mkdir -p "$history_root"
    journal_staging=$(mktemp -d "$history_root/.retired-XXXXXX")
    cp -a "$rollback_record/." "$journal_staging"
    archive_record "$journal_staging" "retired-${version}"
    journal_staging=''
  fi
  for name in facman FacMan; do
    link="$user_bin/$name"
    if [ -L "$link" ]; then
      rm -f "$link"
    fi
  done
  desktop="$desktop_root/facman.desktop"
  if [ -f "$desktop" ]; then rm -f "$desktop"; fi
  rm -f "$current"
  for owned_generation in "$install_root/generations/"*; do
    if [ -e "$owned_generation" ] || [ -L "$owned_generation" ]; then
      assert_owned_generation "$owned_generation"
      rm -rf "$owned_generation"
    fi
  done
  if [ -d "$rollback_record" ]; then rm -rf "$rollback_record"; fi
  rm -f "$setup_copy" "$state/installed-state.v1.json"
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

lock_setup
assert_no_orphan_staging
if [ -e "$pending" ] || [ -L "$pending" ]; then
  echo 'recover the interrupted update before install or repair' >&2
  exit 1
fi
if [ "$operation" = 'install' ]; then
  assert_existing_install_owner
else
  assert_active_generation
fi
assert_native_integration_owned
assert_setup_copy_safe
source_distinct='false'
if [ "$operation" = 'install' ] && [ -n "${old_target:-}" ]; then
  if [ "$old_target" = "$generation" ]; then
    if ! cmp -s "$0" "$maintenance/FacManSetup.run"; then
      echo 'refusing same-version source replacement without a distinct generation' >&2
      exit 1
    fi
  else
    if [ -e "$rollback_record" ] || [ -L "$rollback_record" ]; then
      echo 'refusing another update while a rollback source is retained' >&2
      exit 1
    fi
    source_distinct='true'
    verify_generation "$old_target"
  fi
fi

if [ "$source_distinct" = 'true' ]; then
  expected_old_target="$old_target"
  expected_old_receipt=$(cat "$state/installed-state.v1.json")
  expected_old_setup_sha=$(sha256sum "$maintenance/FacManSetup.run" | cut -d ' ' -f 1)
fi

assert_update_predecessor() {
  assert_existing_install_owner
  assert_native_integration_owned
  assert_setup_copy_safe
  if [ "$old_target" != "$expected_old_target" ] ||
     [ "$(cat "$state/installed-state.v1.json")" != "$expected_old_receipt" ] ||
     [ "$(sha256sum "$maintenance/FacManSetup.run" | cut -d ' ' -f 1)" != "$expected_old_setup_sha" ]; then
    echo 'refusing a changed Linux Setup update predecessor' >&2
    return 1
  fi
  verify_generation "$old_target"
}

temporary=$(mktemp -d "${TMPDIR:-/tmp}/facman-setup.XXXXXX")
payload="$temporary/payload.tar.gz"
tail -n "+$payload_line" "$0" > "$payload"
printf '%s  %s\n' "$payload_sha256" "$payload" | sha256sum -c - >/dev/null
tar -zxf "$payload" -C "$temporary"
source_root="$temporary/FacMan-$version"
verify_generation "$source_root"
if [ "$source_distinct" = 'true' ]; then
  assert_update_predecessor
fi

if [ -e "$generation" ] || [ -L "$generation" ]; then
  assert_owned_generation "$generation"
fi
mkdir -p "$install_root/generations" "$maintenance" "$state" "$user_bin" "$desktop_root"
staging="$install_root/generations/.install-$version-$$"
if [ -e "$staging" ] || [ -L "$staging" ]; then
  echo 'refusing a preexisting Linux Setup staging path' >&2
  exit 1
fi
cp -a "$source_root" "$staging"
verify_generation "$staging"
if [ -e "$generation" ] || [ -L "$generation" ]; then
  rm -rf "$generation"
fi
mv "$staging" "$generation"
if [ "$source_distinct" = 'true' ]; then
  assert_update_predecessor
  journal_staging="$state/.update-prepared-$$"
  if [ -e "$journal_staging" ] || [ -L "$journal_staging" ]; then
    echo 'refusing a preexisting update staging record' >&2
    exit 1
  fi
  mkdir "$journal_staging"
  printf '%s\n' "$old_target" > "$journal_staging/old-target"
  printf '%s\n' "$generation" > "$journal_staging/new-target"
  cp "$state/installed-state.v1.json" "$journal_staging/old-receipt"
  cp "$maintenance/FacManSetup.run" "$journal_staging/old-setup"
  sha256sum "$0" | cut -d ' ' -f 1 > "$journal_staging/new-setup-sha256"
  mv -T "$journal_staging" "$pending"
  journal_staging=''
  assert_update_predecessor
fi
point_current "$generation"
if [ "$source_distinct" = 'true' ] &&
   [ "${FACMAN_TEST_LINUX_SETUP_INTERRUPT_AFTER_CURRENT:-}" = '1' ]; then
  echo 'injected interruption after Linux Setup current cutover' >&2
  exit 75
fi
ln -sfn "$current/facman" "$user_bin/facman"
ln -sfn "$current/FacMan" "$user_bin/FacMan"
active_staging=$(mktemp "$maintenance/.FacManSetup.run.XXXXXX")
cp "$0" "$active_staging"
chmod 0755 "$active_staging"
mv -fT "$active_staging" "$maintenance/FacManSetup.run"
active_staging=''
active_staging=$(mktemp "$desktop_root/.facman.desktop.XXXXXX")
cat > "$active_staging" <<EOF
[Desktop Entry]
Type=Application
Name=FacMan
Comment=Manage Factorio installations and isolated instances
Exec=$current/FacMan
Terminal=false
Categories=Game;Utility;
EOF
chmod 0644 "$active_staging"
mv -fT "$active_staging" "$desktop_root/facman.desktop"
active_staging=''
active_staging=$(mktemp "$state/.installed-state.v1.json.XXXXXX")
cat > "$active_staging" <<EOF
{"schema":"facman.installed_state.v1","version":"$version","generation":"$generation","workspace_preserved":true}
EOF
mv -fT "$active_staging" "$state/installed-state.v1.json"
active_staging=''
verify_generation "$generation"
if [ "$source_distinct" = 'true' ]; then
  mv -T "$pending" "$rollback_record"
fi
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
    with tempfile.TemporaryDirectory(prefix="facman-linux-setup-", dir=output) as temporary:
        raw = Path(temporary) / "payload.tar"
        compressed = Path(temporary) / "payload.tar.gz"
        with raw.open("wb") as stream:
            subprocess.run(["zstd", "-d", "--stdout", str(portable)],
                           stdout=stream, check=True)
        with raw.open("rb") as source, compressed.open("wb") as destination:
            with gzip.GzipFile(filename="", mode="wb", fileobj=destination,
                               compresslevel=9, mtime=0) as stream:
                shutil.copyfileobj(source, stream)
        setup.write_bytes(header(version, sha256(compressed)) + compressed.read_bytes())
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
            "embedded_compression": "gzip",
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
