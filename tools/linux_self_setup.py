#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Build the self-contained per-user Linux FacMan setup executable."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MARKER = "__FACMAN_PAYLOAD_BELOW__"
PREDECESSORS = ROOT / "tools/package/linux_setup_predecessors.v1.toml"
VERSION_PATTERN = re.compile(
    r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


def admitted_predecessors(version: str, catalog: Path = PREDECESSORS) -> tuple[tuple[str, str], ...]:
    if VERSION_PATTERN.fullmatch(version) is None:
        raise ValueError(f"unsupported Linux Setup version: {version!r}")
    with catalog.open("rb") as stream:
        document = tomllib.load(stream)
    if set(document) != {"schema", "predecessor"} or document["schema"] != "facman.linux_setup_predecessors.v1":
        raise ValueError("invalid Linux Setup predecessor catalog schema")
    rows = document["predecessor"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("Linux Setup predecessor catalog is empty")
    entries: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"target_version", "version", "sha256", "qualification"}:
            raise ValueError("invalid Linux Setup predecessor record")
        target, old_version = row["target_version"], row["version"]
        digest, qualification = row["sha256"], row["qualification"]
        if (not isinstance(target, str) or not isinstance(old_version, str) or
                not isinstance(digest, str) or
                not isinstance(qualification, str) or not qualification.strip() or
                SHA256_PATTERN.fullmatch(digest) is None or
                VERSION_PATTERN.fullmatch(target) is None or
                VERSION_PATTERN.fullmatch(old_version) is None or
                target == old_version or (target, digest) in seen):
            raise ValueError("unqualified or duplicate Linux Setup predecessor record")
        seen.add((target, digest))
        if target == version:
            entries.append((old_version, digest))
    return tuple(entries)


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


def header(version: str, payload_sha256: str,
           test_predecessor_sha256: str | None = None,
           predecessor_catalog: Path = PREDECESSORS) -> bytes:
    if SHA256_PATTERN.fullmatch(payload_sha256) is None:
        raise ValueError("invalid Linux Setup payload SHA-256")
    predecessors = admitted_predecessors(version, predecessor_catalog)
    if test_predecessor_sha256 is not None:
        if SHA256_PATTERN.fullmatch(test_predecessor_sha256) is None:
            raise ValueError("invalid test predecessor SHA-256")
        predecessors += (("0.1.0-alpha.5", test_predecessor_sha256),)
    predecessor_cases = "|\\\n      ".join(
        f"'{old_version}:{digest}'" for old_version, digest in predecessors
    ) or "'__no_admitted_predecessor__'"
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
case "$install_root" in
  *[!A-Za-z0-9_./+-]*)
    echo 'refusing unsupported characters in install root' >&2
    exit 3 ;;
esac
canonical_install_root=$(realpath -m -- "$install_root")
normalized_install_root=$(realpath -ms -- "$install_root")
canonical_home=$(realpath -m -- "$HOME")
if [ "$canonical_install_root" = '/' ] ||
   [ "$canonical_install_root" = "$canonical_home" ]; then
  echo 'refusing unsafe resolved install root' >&2
  exit 3
fi
if [ "$canonical_install_root" != "$normalized_install_root" ]; then
  echo 'refusing install root through a linked ancestor' >&2
  exit 3
fi

generation="$install_root/generations/$version"
current="$install_root/current"
state="$install_root/state"
maintenance="$install_root/maintenance"
user_bin="${HOME}/.local/bin"
desktop_root="${HOME}/.local/share/applications"
pending="$state/update-pending.v1"
first_pending="$state/first-install-pending.v1"
repair_pending="$state/repair-pending.v1"
rollback_record="$state/rollback.v1"
setup_authority="$state/installed-setup.sha256"

assert_admitted_predecessor() {
  case "$1:$2" in
      @ADMITTED_PREDECESSOR_CASES@) return 0 ;;
      *) echo 'refusing an unadmitted previous Setup package' >&2; return 1 ;;
  esac
}

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
  if [ ! -d "$target" ] || [ -L "$target" ]; then
    echo 'refusing a linked or absent FacMan generation' >&2
    return 1
  fi
  [ "${2:-}" = 'first-install-pending' ] || [ -f "$state/installed-state.v1.json" ] || {
    echo 'refusing to replace or remove a generation without FacMan installed state' >&2
    return 1
  }
  [ -f "$target/share/facman/manifest/MANIFEST.sha256" ] || {
    echo 'refusing to replace or remove a generation without its ownership manifest' >&2
    return 1
  }
  actual=$(mktemp "${TMPDIR:-/tmp}/facman-actual.XXXXXX")
  expected=$(mktemp "${TMPDIR:-/tmp}/facman-expected.XXXXXX")
  if [ -n "$(find "$target" -mindepth 1 ! -type f ! -type d -print -quit)" ]; then
    rm -f "$actual" "$expected"
    echo 'refusing a linked or special entry in FacMan generation' >&2
    return 1
  fi
  find "$target" -type f -printf '%P\n' | sort > "$actual"
  {
    sed -n 's/^[0-9a-fA-F][0-9a-fA-F]*  //p' \
      "$target/share/facman/manifest/MANIFEST.sha256"
    echo 'share/facman/manifest/MANIFEST.sha256'
  } | sort > "$expected"
  if [ "${2:-}" = 'repair-damaged' ]; then
    unexpected=$(comm -23 "$actual" "$expected")
  else
    unexpected=$(cmp -s "$actual" "$expected" || echo changed)
  fi
  if [ -n "$unexpected" ]; then
    rm -f "$actual" "$expected"
    echo 'refusing to replace or remove a generation containing foreign files' >&2
    return 1
  fi
  find "$target" -mindepth 1 -type d -printf '%P\n' | sort > "$actual"
  sed -n 's/^[0-9a-fA-F][0-9a-fA-F]*  //p' \
    "$target/share/facman/manifest/MANIFEST.sha256" |
  { cat; echo 'share/facman/manifest/MANIFEST.sha256'; } |
  while IFS= read -r owned_path; do
    owned_directory=${owned_path%/*}
    while [ "$owned_directory" != "$owned_path" ] && [ "$owned_directory" != '.' ]; do
      printf '%s\n' "$owned_directory"
      owned_path="$owned_directory"
      owned_directory=${owned_path%/*}
    done
  done | sort -u > "$expected"
  if [ "${2:-}" = 'repair-damaged' ]; then
    unexpected=$(comm -23 "$actual" "$expected")
  else
    unexpected=$(cmp -s "$actual" "$expected" || echo changed)
  fi
  if [ -n "$unexpected" ]; then
    rm -f "$actual" "$expected"
    echo 'refusing to remove a generation containing foreign directories' >&2
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
    old_target=''
    old_version=''
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
  case "$old_version" in
    ''|*[!A-Za-z0-9.+-]*)
      echo 'refusing install over an invalid active version' >&2
      return 1 ;;
  esac
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

assert_setup_authority_safe() {
  if [ -e "$setup_authority" ] || [ -L "$setup_authority" ]; then
    if [ ! -f "$setup_authority" ] || [ -L "$setup_authority" ] ||
       [ ! -f "$maintenance/FacManSetup.run" ] ||
       [ -L "$maintenance/FacManSetup.run" ] ||
       [ "$(cat "$setup_authority")" != "$(sha256sum "$maintenance/FacManSetup.run" | cut -d ' ' -f 1)" ]; then
      echo 'refusing changed installed Setup authority' >&2
      return 1
    fi
  fi
}

assert_previous_setup_source() {
  predecessor_source="$1"
  predecessor_version="$2"
  if [ ! -f "$predecessor_source" ] || [ -L "$predecessor_source" ]; then
    echo 'refusing a missing or linked previous Setup source' >&2
    return 1
  fi
  predecessor_sha=$(sha256sum "$predecessor_source" | cut -d ' ' -f 1)
  if [ -e "$setup_authority" ] || [ -L "$setup_authority" ]; then
    if [ ! -f "$setup_authority" ] || [ -L "$setup_authority" ] ||
       [ "$(cat "$setup_authority")" != "$predecessor_sha" ]; then
      echo 'refusing previous Setup source outside recorded package authority' >&2
      return 1
    fi
    predecessor_authority_mode='recorded'
  else
    predecessor_authority_mode='legacy-pinned'
  fi
  assert_admitted_predecessor "$predecessor_version" "$predecessor_sha"
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
  entry_handoff="$history_root/entry-handoff.v1"
  invoked_setup_sha=$(sha256sum "$0" | cut -d ' ' -f 1)
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
  # On the ordinary same-filesystem layout, retire the journal with one
  # rename. A process loss then leaves either the live record or its exact
  # history entry, rather than a partially removed live record.
  if [ "$(stat -c %d "$record")" = "$(stat -c %d "$history_root")" ]; then
    record_identity=$(stat -c '%d:%i' "$record")
    mv --no-copy -nT "$record" "$history_target"
    if [ -e "$record" ] || [ -L "$record" ] ||
       [ ! -d "$history_target" ] || [ -L "$history_target" ] ||
       [ "$(stat -c '%d:%i' "$history_target")" != "$record_identity" ]; then
      echo 'refusing incomplete Linux Setup history retirement' >&2
      return 1
    fi
    return 0
  fi
  # A separately mounted history root retains the older checked-copy path.
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
  for directory in "$state" "$install_root/generations" "$maintenance" "$desktop_root"; do
    [ -d "$directory" ] || continue
    if [ "$directory" = "$state" ]; then
      orphan=$(find "$directory" -mindepth 1 -maxdepth 1 \( \
        -name '.update-prepared-*' -o -name '.first-install-prepared-*' -o \
        -name '.repair-prepared-*' -o -name '.installed-state.v1.json.*' -o \
        -name '.installed-setup.sha256.*' -o -name '.repair-receipt-*' -o \
        -name '.repair-authority-*' \) -print -quit)
    elif [ "$directory" = "$install_root/generations" ]; then
      orphan=$(find "$directory" -mindepth 1 -maxdepth 1 \( -name '.install-*' -o -name '.repair-previous-*' \) -print -quit)
    elif [ "$directory" = "$maintenance" ]; then
      orphan=$(find "$directory" -mindepth 1 -maxdepth 1 \( -name '.FacManSetup.run.*' -o -name '.repair-setup-*' \) -print -quit)
    else
      orphan=$(find "$directory" -mindepth 1 -maxdepth 1 \( -name '.facman.desktop.*' -o -name '.repair-desktop-*' \) -print -quit)
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
  active_staging=$(mktemp "${destination%/*}/.${destination##*/}.XXXXXX")
  cp "$source" "$active_staging"
  chmod "$mode" "$active_staging"
  mv -fT "$active_staging" "$destination"
  active_staging=''
}

point_current() {
  target="$1"
  expected_current="${2:-}"
  pointer_staging="${3:-$install_root/.current-$$}"
  if [ "$pointer_staging" = "$install_root/.restoration-current" ] &&
     { [ -e "$pointer_staging" ] || [ -L "$pointer_staging" ]; }; then
    if [ ! -L "$pointer_staging" ] || [ "$(readlink "$pointer_staging")" != "$target" ]; then
      echo 'refusing foreign Linux Setup restoration pointer staging' >&2
      return 1
    fi
    rm -f "$pointer_staging"
  fi
  if [ -e "$pointer_staging" ] || [ -L "$pointer_staging" ]; then
    echo 'refusing a preexisting current staging path' >&2
    return 1
  fi
  ln -s "$target" "$pointer_staging"
  current_staging="$pointer_staging"
  if [ -n "$expected_current" ] &&
     { [ ! -L "$current" ] || [ "$(readlink "$current")" != "$expected_current" ]; }; then
    echo 'refusing a changed current pointer at cutover' >&2
    return 1
  fi
  mv -fT "$current_staging" "$current"
  current_staging=''
}

assert_restoration_rename_domain() {
  # Device numbers alone do not identify Linux bind-mount rename domains.
  # Refuse before application effects if the required mount query is absent.
  command -v findmnt >/dev/null 2>&1 || {
    echo 'restoration requires findmnt to validate mount boundaries' >&2
    return 1
  }
  rename_domain=$(findmnt -n -o ID -T "$1") || return 1
  case "$rename_domain" in
    ''|*[!0-9]*) echo 'refusing ambiguous restoration mount identity' >&2; return 1 ;;
  esac
  shift
  for rename_path do
    path_domain=$(findmnt -n -o ID -T "$rename_path") || return 1
    if [ "$path_domain" != "$rename_domain" ]; then
      echo 'refusing separately mounted Linux Setup restoration roots' >&2
      return 1
    fi
  done
}

assert_manifest_binding_stage() {
  binding_stage_file="$1"
  binding_stage_digest="$2"
  if [ -e "$binding_stage_file" ] || [ -L "$binding_stage_file" ]; then
    if [ ! -f "$binding_stage_file" ] || [ -L "$binding_stage_file" ] ||
       [ "$(stat -c %h "$binding_stage_file")" != 1 ]; then
      echo 'refusing foreign restoration manifest staging' >&2
      return 1
    fi
    binding_stage_bytes=$(wc -c < "$binding_stage_file")
    if [ "$binding_stage_bytes" -gt 65 ] ||
       ! printf '%s\n' "$binding_stage_digest" |
         cmp -s -n "$binding_stage_bytes" - "$binding_stage_file"; then
      echo 'refusing changed restoration manifest staging bytes' >&2
      return 1
    fi
  fi
}

publish_manifest_binding() {
  binding_path="$1/new-generation-manifest-sha256"
  binding_stage_path="$1/.restoration-manifest-binding"
  binding_digest="$2"
  [ ! -e "$binding_path" ] && [ ! -L "$binding_path" ] || return 1
  assert_manifest_binding_stage "$binding_stage_path" "$binding_digest"
  if [ -e "$binding_stage_path" ]; then rm -f "$binding_stage_path"; fi
  (umask 077; set -C; printf '%s\n' "$binding_digest" > "$binding_stage_path")
  if [ ! -f "$binding_stage_path" ] || [ -L "$binding_stage_path" ] ||
     [ "$(wc -c < "$binding_stage_path")" != 65 ] ||
     [ "$(cat "$binding_stage_path")" != "$binding_digest" ]; then
    echo 'refusing incomplete restoration manifest staging' >&2
    return 1
  fi
  binding_identity=$(stat -c '%d:%i' "$binding_stage_path")
  mv --no-copy -nT "$binding_stage_path" "$binding_path"
  if [ -e "$binding_stage_path" ] || [ -L "$binding_stage_path" ] ||
     [ ! -f "$binding_path" ] || [ -L "$binding_path" ] ||
     [ "$(stat -c '%d:%i' "$binding_path")" != "$binding_identity" ] ||
     [ "$(cat "$binding_path")" != "$binding_digest" ]; then
    echo 'refusing incomplete restoration manifest publication' >&2
    return 1
  fi
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
  record_entries=$(find "$record" -mindepth 1 -maxdepth 1 \
    ! -name retired-generation ! -name new-generation-manifest-sha256 \
    ! -name .restoration-manifest-binding -printf '%f\n' | sort)
  expected_entries=$(printf '%s\n' new-setup-sha256 new-target old-authority-mode old-receipt old-setup old-setup-sha256 old-target)
  legacy_entries=$(printf '%s\n' new-setup-sha256 new-target old-receipt old-setup old-target)
  if [ "$record_entries" = "$expected_entries" ]; then
    record_schema='current'
  elif [ "$record_entries" = "$legacy_entries" ]; then
    record_schema='legacy'
  else
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
  if [ "$record_schema" = 'current' ]; then
    for name in old-setup-sha256 old-authority-mode; do
      [ -f "$record/$name" ] && [ ! -L "$record/$name" ] || return 1
    done
    if [ "$previous_setup_sha" != "$(cat "$record/old-setup-sha256")" ]; then
      echo 'refusing changed previous Setup source in update record' >&2
      return 1
    fi
    authority_mode=$(cat "$record/old-authority-mode")
  else
    authority_mode='legacy-pinned'
  fi
  case "$authority_mode" in
    recorded|legacy-pinned) ;;
    *) echo 'refusing changed previous Setup authority' >&2; return 1 ;;
  esac
  assert_admitted_predecessor "$old_version" "$previous_setup_sha"
  new_setup_sha=$(cat "$record/new-setup-sha256")
   if [ "$new_setup_sha" != "$invoked_setup_sha" ] ||
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
  if [ -e "$setup_authority" ] || [ -L "$setup_authority" ]; then
    if [ ! -f "$setup_authority" ] || [ -L "$setup_authority" ]; then
      echo 'refusing changed installed Setup authority' >&2
      return 1
    fi
    authority_now=$(cat "$setup_authority")
    if [ "$authority_now" != "$previous_setup_sha" ] &&
       [ "$authority_now" != "$new_setup_sha" ]; then
      echo 'refusing ambiguous installed Setup authority' >&2
      return 1
    fi
  elif [ "$authority_mode" = 'recorded' ]; then
    echo 'refusing missing recorded Setup authority' >&2
    return 1
  fi
  assert_owned_generation "$old_target"
  verify_generation "$old_target"
  assert_native_integration_owned
  if [ -e "$new_target" ] || [ -L "$new_target" ]; then
    [ -d "$new_target" ] && [ ! -L "$new_target" ] || return 1
    assert_owned_generation "$new_target"
    verify_generation "$new_target"
  fi
  retired_generation="$record/retired-generation"
  manifest_binding="$record/new-generation-manifest-sha256"
  if [ -e "$manifest_binding" ] || [ -L "$manifest_binding" ]; then
    if [ ! -f "$manifest_binding" ] || [ -L "$manifest_binding" ] ||
       ! grep -Eq '^[0-9a-f]{64}$' "$manifest_binding"; then
      echo 'refusing changed retired generation manifest binding' >&2
      return 1
    fi
    manifest_sha=$(cat "$manifest_binding")
  else
    manifest_sha=''
  fi
  binding_stage="$record/.restoration-manifest-binding"
  if [ -e "$binding_stage" ] || [ -L "$binding_stage" ]; then
    if [ -e "$manifest_binding" ] || [ -L "$manifest_binding" ] ||
       [ ! -d "$new_target" ] || [ "$mode" = 'handoff' ] ||
       [ -e "$retired_generation" ] || [ -L "$retired_generation" ]; then
      echo 'refusing unexpected restoration manifest staging' >&2
      return 1
    fi
    manifest_sha=$(sha256sum "$new_target/share/facman/manifest/MANIFEST.sha256" | cut -d ' ' -f 1)
    assert_manifest_binding_stage "$binding_stage" "$manifest_sha"
  fi
  if [ -e "$retired_generation" ] || [ -L "$retired_generation" ]; then
    if [ -e "$new_target" ] || [ -L "$new_target" ] || [ -z "$manifest_sha" ]; then
      echo 'refusing duplicate or unbound retired generation custody' >&2
      return 1
    fi
    assert_owned_generation "$retired_generation"
    verify_generation "$retired_generation"
    [ "$(sha256sum "$retired_generation/share/facman/manifest/MANIFEST.sha256" | cut -d ' ' -f 1)" = "$manifest_sha" ] || {
      echo 'refusing changed retired generation manifest' >&2; return 1;
    }
  elif [ "$mode" = 'handoff' ] || [ ! -d "$new_target" ]; then
    echo 'refusing missing retired generation custody' >&2
    return 1
  elif [ -n "$manifest_sha" ]; then
    [ "$(sha256sum "$new_target/share/facman/manifest/MANIFEST.sha256" | cut -d ' ' -f 1)" = "$manifest_sha" ] || {
      echo 'refusing changed outgoing generation manifest' >&2; return 1;
    }
  fi
  if [ "$mode" = 'check' ]; then
    return 0
  fi
  for protected_root in "$lock_root/history" "$history_root"; do
    [ ! -L "$protected_root" ] || {
      echo 'refusing linked Linux Setup history' >&2; return 1;
    }
  done
  mkdir -p "$history_root"
  if [ "$(stat -c %d "$record")" != "$(stat -c %d "$history_root")" ] ||
     { [ -d "$new_target" ] &&
       [ "$(stat -c %d "$new_target")" != "$(stat -c %d "$record")" ]; }; then
    echo 'restoration requires one filesystem for generation, journal and history' >&2
    return 1
  fi
  assert_restoration_rename_domain "$record" "$history_root"
  if [ -d "$new_target" ]; then
    assert_restoration_rename_domain "$record" "$new_target"
  else
    assert_restoration_rename_domain "$record" "$retired_generation"
  fi
  if [ "$mode" = 'handoff' ]; then
    if [ "$record" != "$entry_handoff" ] || [ "$current_now" != "$old_target" ] ||
       [ "$receipt_now" != "$expected_old" ] || [ -e "$new_target" ] || [ -L "$new_target" ] ||
       [ -e "$state/.restoration-receipt" ] || [ -L "$state/.restoration-receipt" ] ||
       [ -e "$state/.restoration-authority" ] || [ -L "$state/.restoration-authority" ] ||
       [ -e "$install_root/.restoration-current" ] || [ -L "$install_root/.restoration-current" ]; then
      echo 'refusing incomplete Linux Setup entry handoff' >&2
      return 1
    fi
    if { [ "$authority_mode" = 'recorded' ] &&
         [ "$(cat "$setup_authority")" != "$previous_setup_sha" ]; } ||
       { [ "$authority_mode" = 'legacy-pinned' ] &&
         { [ -e "$setup_authority" ] || [ -L "$setup_authority" ]; }; }; then
      echo 'refusing changed restored Setup authority' >&2
      return 1
    fi
    repair_replace_file "$record/old-setup" "$maintenance/FacManSetup.run" "$maintenance/.restoration-setup" 0755
    archive_record "$record" "restored-${old_version}-to-${version}"
    return 0
  fi
  if [ -e "$entry_handoff" ] || [ -L "$entry_handoff" ]; then
    echo 'recover the preceding Linux Setup entry handoff first' >&2
    return 1
  fi
  restoration_pointer="$install_root/.restoration-current"
  if [ -e "$restoration_pointer" ] || [ -L "$restoration_pointer" ]; then
    [ -L "$restoration_pointer" ] && [ "$(readlink "$restoration_pointer")" = "$old_target" ] || {
      echo 'refusing foreign Linux Setup restoration pointer staging' >&2; return 1;
    }
  fi
  repair_cleanup_stage "$state/.restoration-receipt" "$record/old-receipt" check
  repair_cleanup_stage "$maintenance/.restoration-setup" "$record/old-setup" check
  if [ "$authority_mode" = 'recorded' ]; then
    repair_cleanup_stage "$state/.restoration-authority" "$record/old-setup-sha256" check
  elif [ -e "$state/.restoration-authority" ] || [ -L "$state/.restoration-authority" ]; then
    echo 'refusing unexpected restoration authority staging' >&2
    return 1
  fi
  if [ "$mode" = 'preflight' ]; then
    return 0
  fi
  if [ -d "$new_target" ] && [ ! -e "$manifest_binding" ]; then
    manifest_sha=$(sha256sum "$new_target/share/facman/manifest/MANIFEST.sha256" | cut -d ' ' -f 1)
    publish_manifest_binding "$record" "$manifest_sha"
  fi
  if [ ! -L "$current" ] || [ "$(readlink "$current")" != "$current_now" ]; then
    echo 'refusing a changed update current pointer at restoration' >&2
    return 1
  fi
  assert_native_integration_owned
  point_current "$old_target" "$current_now" "$install_root/.restoration-current"
  repair_replace_file "$record/old-receipt" "$state/installed-state.v1.json" "$state/.restoration-receipt" 0600
  if [ "$authority_mode" = 'recorded' ]; then
    repair_replace_file "$record/old-setup-sha256" "$setup_authority" "$state/.restoration-authority" 0600
  elif [ -e "$setup_authority" ] || [ -L "$setup_authority" ]; then
    [ ! -L "$setup_authority" ] && [ "$(cat "$setup_authority")" = "$new_setup_sha" ] || return 1
    rm -f "$setup_authority"
  fi
  if [ -e "$new_target" ] || [ -L "$new_target" ]; then
    assert_owned_generation "$new_target"
    assert_native_integration_owned
    verify_generation "$new_target"
    retiring_identity=$(stat -c '%d:%i' "$new_target")
    mv --no-copy -nT "$new_target" "$retired_generation"
    if [ -e "$new_target" ] || [ -L "$new_target" ] ||
       [ ! -d "$retired_generation" ] || [ -L "$retired_generation" ] ||
       [ "$(stat -c '%d:%i' "$retired_generation")" != "$retiring_identity" ]; then
      echo 'refusing incomplete restored generation retirement' >&2
      return 1
    fi
  fi
  record_identity=$(stat -c '%d:%i' "$record")
  mv --no-copy -nT "$record" "$entry_handoff"
  if [ -e "$record" ] || [ -L "$record" ] ||
     [ ! -d "$entry_handoff" ] || [ -L "$entry_handoff" ] ||
     [ "$(stat -c '%d:%i' "$entry_handoff")" != "$record_identity" ]; then
    echo 'refusing incomplete Linux Setup entry handoff admission' >&2
    return 1
  fi
  # All application/native effects are restored before the last entry swap.
  # A loss after the swap leaves only history outside the application root.
  repair_replace_file "$entry_handoff/old-setup" "$maintenance/FacManSetup.run" "$maintenance/.restoration-setup" 0755
  archive_record "$entry_handoff" "restored-${old_version}-to-${version}"
}

finish_completed_entry_handoff() {
  if [ -e "$install_root" ] || [ -L "$install_root" ]; then
    restore_update_record "$entry_handoff" handoff
    return
  fi
  # An older Setup may have removed the fully restored application after the
  # final entry swap. Validate the retained record without requiring live A5
  # files, then retire only history; application absence remains unchanged.
  record="$entry_handoff"
  [ -d "$record" ] && [ ! -L "$record" ] || return 1
  record_entries=$(find "$record" -mindepth 1 -maxdepth 1 \
    ! -name retired-generation ! -name new-generation-manifest-sha256 -printf '%f\n' | sort)
  expected_entries=$(printf '%s\n' new-setup-sha256 new-target old-authority-mode old-receipt old-setup old-setup-sha256 old-target)
  legacy_entries=$(printf '%s\n' new-setup-sha256 new-target old-receipt old-setup old-target)
  if [ "$record_entries" != "$expected_entries" ] && [ "$record_entries" != "$legacy_entries" ]; then
    echo 'refusing foreign completed Linux Setup handoff content' >&2
    return 1
  fi
  for name in $record_entries; do
    [ -f "$record/$name" ] && [ ! -L "$record/$name" ] || return 1
  done
  old_target=$(cat "$record/old-target")
  old_version=${old_target##*/}
  case "$old_version" in
    ''|*[!A-Za-z0-9.+-]*) return 1 ;;
  esac
  if [ "$old_target" != "$install_root/generations/$old_version" ] ||
     [ "$old_version" = "$version" ] || [ "$(cat "$record/new-target")" != "$generation" ] ||
     [ "$(cat "$record/new-setup-sha256")" != "$invoked_setup_sha" ]; then
    echo 'refusing changed completed Linux Setup handoff identity' >&2
    return 1
  fi
  expected_old=$(printf '{"schema":"facman.installed_state.v1","version":"%s","generation":"%s","workspace_preserved":true}' "$old_version" "$old_target")
  [ "$(cat "$record/old-receipt")" = "$expected_old" ] || return 1
  previous_setup_sha=$(sha256sum "$record/old-setup" | cut -d ' ' -f 1)
  assert_admitted_predecessor "$old_version" "$previous_setup_sha"
  if [ "$record_entries" = "$expected_entries" ]; then
    [ "$(cat "$record/old-setup-sha256")" = "$previous_setup_sha" ] || return 1
    case "$(cat "$record/old-authority-mode")" in
      recorded|legacy-pinned) ;;
      *) return 1 ;;
    esac
  fi
  manifest_binding="$record/new-generation-manifest-sha256"
  retired_generation="$record/retired-generation"
  if [ ! -f "$manifest_binding" ] || [ -L "$manifest_binding" ] ||
     ! grep -Eq '^[0-9a-f]{64}$' "$manifest_binding" ||
     [ ! -d "$retired_generation" ] || [ -L "$retired_generation" ]; then
    echo 'refusing missing or changed completed handoff custody' >&2
    return 1
  fi
  assert_owned_generation "$retired_generation" first-install-pending
  verify_generation "$retired_generation"
  [ "$(sha256sum "$retired_generation/share/facman/manifest/MANIFEST.sha256" | cut -d ' ' -f 1)" = "$(cat "$manifest_binding")" ] || return 1
  for protected_root in "$lock_root/history" "$history_root"; do
    [ ! -L "$protected_root" ] || return 1
  done
  [ "$(stat -c %d "$record")" = "$(stat -c %d "$history_root")" ] || {
    echo 'completed handoff retirement requires one filesystem' >&2; return 1;
  }
  assert_restoration_rename_domain "$record" "$history_root" "$retired_generation"
  archive_record "$record" "restored-${old_version}-to-${version}"
}

restore_first_install_record() {
  record="$first_pending"
  record_entries=$(find "$record" -mindepth 1 -maxdepth 1 -printf '%f\n' 2>/dev/null | sort)
  expected_entries=$(printf '%s\n' new-setup-sha256 new-target staging-target | sort)
  if [ ! -d "$record" ] || [ -L "$record" ] ||
     [ "$record_entries" != "$expected_entries" ] ||
     [ ! -f "$record/new-target" ] || [ -L "$record/new-target" ] ||
     [ ! -f "$record/new-setup-sha256" ] || [ -L "$record/new-setup-sha256" ] ||
     [ ! -f "$record/staging-target" ] || [ -L "$record/staging-target" ]; then
    echo 'refusing an invalid first-install recovery record' >&2
    return 1
  fi
  expected_setup_sha=$(sha256sum "$0" | cut -d ' ' -f 1)
  if [ "$(cat "$record/new-target")" != "$generation" ] ||
     [ "$(cat "$record/new-setup-sha256")" != "$expected_setup_sha" ] ||
     [ -e "$pending" ] || [ -L "$pending" ] ||
     [ -e "$rollback_record" ] || [ -L "$rollback_record" ]; then
    echo 'refusing changed or mixed first-install recovery state' >&2
    return 1
  fi
  staging_target=$(cat "$record/staging-target")
  staging_name=${staging_target##*/}
  staging_suffix=${staging_name#".install-$version-"}
  case "$staging_suffix" in
    ''|*[!0-9]*) echo 'refusing changed first-install staging identity' >&2; return 1 ;;
  esac
  if [ "$staging_name" != ".install-$version-$staging_suffix" ] ||
     [ "$staging_target" != "$install_root/generations/$staging_name" ]; then
    echo 'refusing foreign first-install staging path' >&2
    return 1
  fi
  for directory in "$install_root" "$install_root/generations" "$state" "$maintenance"; do
    [ -d "$directory" ] && [ ! -L "$directory" ] || return 1
  done
  foreign=$(find "$install_root" -mindepth 1 -maxdepth 1 ! -name generations ! -name state ! -name maintenance ! -name current -print -quit)
  [ -z "$foreign" ] || { echo 'refusing foreign installation content' >&2; return 1; }
  foreign=$(find "$install_root/generations" -mindepth 1 -maxdepth 1 ! -name "$version" ! -name "$staging_name" -print -quit)
  [ -z "$foreign" ] || { echo 'refusing foreign generation content' >&2; return 1; }
  if { [ -e "$staging_target" ] || [ -L "$staging_target" ]; } &&
     { [ -e "$generation" ] || [ -L "$generation" ]; }; then
    echo 'refusing simultaneous first-install staging and generation' >&2
    return 1
  fi
  foreign=$(find "$state" -mindepth 1 -maxdepth 1 ! -name first-install-pending.v1 ! -name installed-state.v1.json ! -name installed-setup.sha256 -print -quit)
  [ -z "$foreign" ] || { echo 'refusing foreign first-install state' >&2; return 1; }
  foreign=$(find "$maintenance" -mindepth 1 -maxdepth 1 ! -name FacManSetup.run -print -quit)
  [ -z "$foreign" ] || { echo 'refusing foreign maintenance content' >&2; return 1; }
  expected_receipt=$(printf '{"schema":"facman.installed_state.v1","version":"%s","generation":"%s","workspace_preserved":true}' "$version" "$generation")
  receipt="$state/installed-state.v1.json"
  if { [ -e "$current" ] || [ -L "$current" ]; } &&
     { [ ! -L "$current" ] || [ "$(readlink "$current")" != "$generation" ]; }; then
    echo 'refusing changed first-install current pointer' >&2
    return 1
  fi
  if { [ -e "$receipt" ] || [ -L "$receipt" ]; } &&
     { [ ! -f "$receipt" ] || [ -L "$receipt" ] ||
       [ "$(cat "$receipt")" != "$expected_receipt" ]; }; then
    echo 'refusing changed first-install receipt' >&2
    return 1
  fi
  setup_copy="$maintenance/FacManSetup.run"
  if { [ -e "$setup_copy" ] || [ -L "$setup_copy" ]; } &&
     { [ ! -f "$setup_copy" ] || [ -L "$setup_copy" ] ||
       [ "$(sha256sum "$setup_copy" | cut -d ' ' -f 1)" != "$expected_setup_sha" ]; }; then
    echo 'refusing changed first-install Setup source' >&2
    return 1
  fi
  if { [ -e "$setup_authority" ] || [ -L "$setup_authority" ]; } &&
     { [ ! -f "$setup_authority" ] || [ -L "$setup_authority" ] ||
       [ "$(cat "$setup_authority")" != "$expected_setup_sha" ]; }; then
    echo 'refusing changed first-install Setup authority' >&2
    return 1
  fi
  assert_native_integration_owned
  if [ -e "$staging_target" ] || [ -L "$staging_target" ]; then
    assert_owned_generation "$staging_target" first-install-pending
    verify_generation "$staging_target"
    if [ -L "$current" ] || [ -e "$receipt" ] || [ -L "$receipt" ]; then
      echo 'refusing published state with first-install staging' >&2
      return 1
    fi
  fi
  if [ -e "$generation" ] || [ -L "$generation" ]; then
    assert_owned_generation "$generation" first-install-pending
    verify_generation "$generation"
  elif [ -L "$current" ] ||
       [ -e "$user_bin/facman" ] || [ -L "$user_bin/facman" ] ||
       [ -e "$user_bin/FacMan" ] || [ -L "$user_bin/FacMan" ] ||
       [ -e "$desktop_root/facman.desktop" ] ||
       [ -L "$desktop_root/facman.desktop" ]; then
    echo 'refusing missing active first-install generation' >&2
    return 1
  fi
  for owned_name in facman FacMan; do
    if [ -L "$user_bin/$owned_name" ]; then
      assert_native_integration_owned
      rm -f "$user_bin/$owned_name"
    fi
  done
  desktop="$desktop_root/facman.desktop"
  if [ -f "$desktop" ]; then
    assert_native_integration_owned
    rm -f "$desktop"
  fi
  if [ -L "$current" ]; then
    [ "$(readlink "$current")" = "$generation" ] || return 1
    rm -f "$current"
  fi
  if [ "${FACMAN_TEST_LINUX_SETUP_INTERRUPT_FIRST_RECOVERY_AFTER_CURRENT:-}" = '1' ]; then
    echo 'injected interruption during first-install recovery' >&2
    return 75
  fi
  if [ -e "$staging_target" ] || [ -L "$staging_target" ]; then
    assert_owned_generation "$staging_target" first-install-pending
    verify_generation "$staging_target"
    rm -rf "$staging_target"
  fi
  if [ -e "$generation" ] || [ -L "$generation" ]; then
    assert_owned_generation "$generation" first-install-pending
    verify_generation "$generation"
    rm -rf "$generation"
  fi
  if [ "${FACMAN_TEST_LINUX_SETUP_INTERRUPT_FIRST_RECOVERY_AFTER_GENERATION:-}" = '1' ]; then
    echo 'injected interruption after first-install generation removal' >&2
    return 75
  fi
  if { [ -e "$receipt" ] || [ -L "$receipt" ]; } &&
     { [ ! -f "$receipt" ] || [ -L "$receipt" ] ||
       [ "$(cat "$receipt")" != "$expected_receipt" ]; }; then
    echo 'refusing changed first-install receipt at removal' >&2
    return 1
  fi
  if { [ -e "$setup_authority" ] || [ -L "$setup_authority" ]; } &&
     { [ ! -f "$setup_authority" ] || [ -L "$setup_authority" ] ||
       [ "$(cat "$setup_authority")" != "$expected_setup_sha" ]; }; then
    echo 'refusing changed first-install Setup authority at removal' >&2
    return 1
  fi
  if { [ -e "$setup_copy" ] || [ -L "$setup_copy" ]; } &&
     { [ ! -f "$setup_copy" ] || [ -L "$setup_copy" ] ||
       [ "$(sha256sum "$setup_copy" | cut -d ' ' -f 1)" != "$expected_setup_sha" ]; }; then
    echo 'refusing changed first-install Setup source at removal' >&2
    return 1
  fi
  rm -f "$receipt" "$setup_authority" "$setup_copy"
  archive_record "$record" "restored-first-install-${version}"
  rmdir "$maintenance" "$state" "$install_root/generations" "$install_root" 2>/dev/null || true
}

assert_repair_backup_owned() {
  if [ ! -d "$repair_backup" ] || [ -L "$repair_backup" ] ||
     [ -n "$(find "$repair_backup" -mindepth 1 ! -type f ! -type d -print -quit)" ]; then
    echo 'refusing foreign Linux Setup repair backup entry' >&2
    return 1
  fi
  repair_actual=$(mktemp "${TMPDIR:-/tmp}/facman-repair-actual.XXXXXX")
  repair_expected=$(mktemp "${TMPDIR:-/tmp}/facman-repair-expected.XXXXXX")
  find "$repair_backup" -type f -printf '%P\n' | sort > "$repair_actual"
  {
    sed -n 's/^[0-9a-fA-F][0-9a-fA-F]*  //p' "$repair_record/manifest-copy"
    echo 'share/facman/manifest/MANIFEST.sha256'
  } | sort > "$repair_expected"
  repair_unexpected=$(comm -23 "$repair_actual" "$repair_expected")
  if [ -n "$repair_unexpected" ]; then
    rm -f "$repair_actual" "$repair_expected"
    echo 'refusing foreign file in Linux Setup repair backup' >&2
    return 1
  fi
  find "$repair_backup" -mindepth 1 -type d -printf '%P\n' | sort > "$repair_actual"
  sed -n 's/^[0-9a-fA-F][0-9a-fA-F]*  //p' "$repair_record/manifest-copy" |
  { cat; echo 'share/facman/manifest/MANIFEST.sha256'; } |
  while IFS= read -r repair_path; do
    repair_directory=${repair_path%/*}
    while [ "$repair_directory" != "$repair_path" ] && [ "$repair_directory" != '.' ]; do
      printf '%s\n' "$repair_directory"
      repair_path="$repair_directory"
      repair_directory=${repair_path%/*}
    done
  done | sort -u > "$repair_expected"
  repair_unexpected=$(comm -23 "$repair_actual" "$repair_expected")
  rm -f "$repair_actual" "$repair_expected"
  if [ -n "$repair_unexpected" ]; then
    echo 'refusing foreign directory in Linux Setup repair backup' >&2
    return 1
  fi
}

repair_cleanup_stage() {
  repair_stage_file="$1"
  repair_expected_file="$2"
  if [ -e "$repair_stage_file" ] || [ -L "$repair_stage_file" ]; then
    if [ ! -f "$repair_stage_file" ] || [ -L "$repair_stage_file" ]; then
      echo 'refusing foreign Linux Setup repair staging entry' >&2
      return 1
    fi
    repair_stage_bytes=$(wc -c < "$repair_stage_file")
    repair_expected_bytes=$(wc -c < "$repair_expected_file")
    if [ "$repair_stage_bytes" -gt "$repair_expected_bytes" ] ||
       ! cmp -s -n "$repair_stage_bytes" "$repair_stage_file" "$repair_expected_file"; then
      echo 'refusing changed Linux Setup repair staging bytes' >&2
      return 1
    fi
    if [ "${3:-apply}" != 'check' ]; then
      rm -f "$repair_stage_file"
    fi
  fi
}

repair_replace_file() {
  repair_source="$1"
  repair_destination="$2"
  repair_stage_file="$3"
  repair_mode="$4"
  repair_cleanup_stage "$repair_stage_file" "$repair_source"
  (umask 077; set -C; cat "$repair_source" > "$repair_stage_file")
  chmod "$repair_mode" "$repair_stage_file"
  if [ ! -f "$repair_stage_file" ] || [ -L "$repair_stage_file" ] ||
     ! cmp -s "$repair_source" "$repair_stage_file"; then
    echo 'refusing changed Linux Setup repair staged file' >&2
    return 1
  fi
  mv -fT "$repair_stage_file" "$repair_destination"
}

finish_repair_record() {
  repair_record="$repair_pending"
  if [ ! -d "$repair_record" ] || [ -L "$repair_record" ]; then
    echo 'refusing an invalid Linux Setup repair record' >&2
    return 1
  fi
  repair_entries=$(find "$repair_record" -mindepth 1 -maxdepth 1 -printf '%f\n' | sort)
  repair_expected_entries=$(printf '%s\n' backup-target desktop-copy manifest-copy manifest-sha256 new-target setup-sha256 staging-target | sort)
  if [ "$repair_entries" != "$repair_expected_entries" ]; then
    echo 'refusing foreign Linux Setup repair record content' >&2
    return 1
  fi
  for repair_name in backup-target desktop-copy manifest-copy manifest-sha256 new-target setup-sha256 staging-target; do
    if [ ! -f "$repair_record/$repair_name" ] || [ -L "$repair_record/$repair_name" ]; then
      echo 'refusing incomplete Linux Setup repair record' >&2
      return 1
    fi
  done
  repair_stage=$(cat "$repair_record/staging-target")
  repair_backup=$(cat "$repair_record/backup-target")
  repair_target=$(cat "$repair_record/new-target")
  repair_manifest_sha=$(cat "$repair_record/manifest-sha256")
  repair_stage_name=${repair_stage##*/}
  repair_suffix=${repair_stage_name#".install-$version-"}
  repair_receipt_stage="$state/.repair-receipt-$repair_suffix"
  repair_setup_stage="$maintenance/.repair-setup-$repair_suffix"
  repair_authority_stage="$state/.repair-authority-$repair_suffix"
  repair_desktop_stage="$desktop_root/.repair-desktop-$repair_suffix"
  case "$repair_suffix" in
    ''|*[!0-9]*) echo 'refusing changed Linux Setup repair staging identity' >&2; return 1 ;;
  esac
  if [ "$repair_target" != "$generation" ] ||
     [ "$repair_stage" != "$install_root/generations/.install-$version-$repair_suffix" ] ||
     [ "$repair_backup" != "$install_root/generations/.repair-previous-$version-$repair_suffix" ] ||
     { ! printf '%s\n' "$repair_manifest_sha" | grep -Eq '^[0-9a-f]{64}$'; } ||
     [ "$(cat "$repair_record/setup-sha256")" != "$(sha256sum "$0" | cut -d ' ' -f 1)" ] ||
     [ -e "$pending" ] || [ -L "$pending" ] ||
     [ -e "$first_pending" ] || [ -L "$first_pending" ]; then
    echo 'refusing changed or mixed Linux Setup repair state' >&2
    return 1
  fi
  if [ "$(sha256sum "$repair_record/manifest-copy" | cut -d ' ' -f 1)" != "$repair_manifest_sha" ]; then
    echo 'refusing changed Linux Setup repair ownership manifest' >&2
    return 1
  fi
  repair_expected_desktop_sha=$(printf \
    '[Desktop Entry]\nType=Application\nName=FacMan\nComment=Manage Factorio installations and isolated instances\nExec=%s/FacMan\nTerminal=false\nCategories=Game;Utility;\n' \
    "$current" | sha256sum | cut -d ' ' -f 1)
  if [ "$(sha256sum "$repair_record/desktop-copy" | cut -d ' ' -f 1)" != "$repair_expected_desktop_sha" ]; then
    echo 'refusing changed Linux Setup repair desktop identity' >&2
    return 1
  fi
  assert_active_generation
  assert_native_integration_owned
  if [ ! -f "$maintenance/FacManSetup.run" ] ||
     [ -L "$maintenance/FacManSetup.run" ] ||
     [ "$(sha256sum "$maintenance/FacManSetup.run" | cut -d ' ' -f 1)" != \
       "$(cat "$repair_record/setup-sha256")" ]; then
    echo 'refusing changed installed Linux Setup repair source' >&2
    return 1
  fi
  assert_setup_authority_safe
  repair_cleanup_stage "$repair_receipt_stage" "$state/installed-state.v1.json"
  repair_cleanup_stage "$repair_setup_stage" "$0"
  repair_cleanup_stage "$repair_authority_stage" "$repair_record/setup-sha256"
  repair_cleanup_stage "$repair_desktop_stage" "$repair_record/desktop-copy"
  repair_hidden=$(find "$install_root/generations" -mindepth 1 -maxdepth 1 -name '.*' \
    ! -name "$repair_stage_name" ! -name ".repair-previous-$version-$repair_suffix" -print -quit)
  if [ -n "$repair_hidden" ]; then
    echo 'refusing foreign hidden Linux Setup generation during repair' >&2
    return 1
  fi
  if [ -e "$repair_stage" ] || [ -L "$repair_stage" ]; then
    assert_owned_generation "$repair_stage"
    verify_generation "$repair_stage"
    [ "$(sha256sum "$repair_stage/share/facman/manifest/MANIFEST.sha256" | cut -d ' ' -f 1)" = "$repair_manifest_sha" ] || return 1
    if [ -e "$repair_backup" ] || [ -L "$repair_backup" ]; then
      if [ -e "$generation" ] || [ -L "$generation" ]; then
        echo 'refusing ambiguous Linux Setup repair generations' >&2
        return 1
      fi
      assert_repair_backup_owned
    else
      assert_owned_generation "$generation" repair-damaged
      [ "$(sha256sum "$generation/share/facman/manifest/MANIFEST.sha256" | cut -d ' ' -f 1)" = "$repair_manifest_sha" ] || return 1
      assert_active_generation
      mv -T "$generation" "$repair_backup"
      if [ "$operation" = 'repair' ] &&
         [ "${FACMAN_TEST_LINUX_SETUP_INTERRUPT_REPAIR_AFTER_OLD_MOVE:-}" = '1' ]; then
        echo 'injected interruption after Linux Setup repair old-generation move' >&2
        return 75
      fi
    fi
    assert_owned_generation "$repair_stage"
    verify_generation "$repair_stage"
    mv -T "$repair_stage" "$generation"
    if [ "$operation" = 'repair' ] &&
       [ "${FACMAN_TEST_LINUX_SETUP_INTERRUPT_REPAIR_AFTER_NEW_MOVE:-}" = '1' ]; then
      echo 'injected interruption after Linux Setup repair new-generation move' >&2
      return 75
    fi
  fi
  if [ -e "$repair_stage" ] || [ -L "$repair_stage" ] ||
     [ ! -d "$generation" ] || [ -L "$generation" ]; then
    echo 'refusing incomplete Linux Setup repair generation' >&2
    return 1
  fi
  assert_owned_generation "$generation"
  verify_generation "$generation"
  [ "$(sha256sum "$generation/share/facman/manifest/MANIFEST.sha256" | cut -d ' ' -f 1)" = "$repair_manifest_sha" ] || return 1
  assert_active_generation
  assert_native_integration_owned
  mkdir -p "$user_bin" "$desktop_root"
  for repair_name in facman FacMan; do
    if [ ! -L "$user_bin/$repair_name" ]; then
      [ ! -e "$user_bin/$repair_name" ] || return 1
      ln -s "$current/$repair_name" "$user_bin/$repair_name"
    fi
  done
  if [ ! -e "$desktop_root/facman.desktop" ] &&
     [ ! -L "$desktop_root/facman.desktop" ]; then
    (umask 077; set -C; cat "$repair_record/desktop-copy" > "$repair_desktop_stage")
    chmod 0644 "$repair_desktop_stage"
    [ -f "$repair_desktop_stage" ] && [ ! -L "$repair_desktop_stage" ] &&
      cmp -s "$repair_record/desktop-copy" "$repair_desktop_stage" || return 1
    mv -nT "$repair_desktop_stage" "$desktop_root/facman.desktop"
    [ ! -e "$repair_desktop_stage" ] || { echo 'refusing changed desktop destination during repair' >&2; return 1; }
  fi
  assert_native_integration_owned
  repair_replace_file "$state/installed-state.v1.json" \
    "$state/installed-state.v1.json" "$repair_receipt_stage" 0600
  repair_replace_file "$0" "$maintenance/FacManSetup.run" "$repair_setup_stage" 0755
  repair_replace_file "$repair_record/setup-sha256" \
    "$setup_authority" "$repair_authority_stage" 0600
  assert_setup_authority_safe
  if [ -e "$repair_backup" ] || [ -L "$repair_backup" ]; then
    assert_repair_backup_owned
    assert_native_integration_owned
    rm -rf "$repair_backup"
    if [ "$operation" = 'repair' ] &&
       [ "${FACMAN_TEST_LINUX_SETUP_INTERRUPT_REPAIR_AFTER_BACKUP_REMOVAL:-}" = '1' ]; then
      echo 'injected interruption after Linux Setup repair backup removal' >&2
      return 75
    fi
  fi
  archive_record "$repair_record" "completed-repair-${version}"
}

if [ "$operation" = 'verify' ]; then
  if [ -e "$pending" ] || [ -L "$pending" ] ||
     [ -e "$first_pending" ] || [ -L "$first_pending" ] ||
     [ -e "$repair_pending" ] || [ -L "$repair_pending" ]; then
    echo 'Linux Setup recovery is required before verification' >&2
    exit 1
  fi
  assert_active_generation
  if [ ! -f "$setup_authority" ] || [ -L "$setup_authority" ] ||
     [ ! -f "$maintenance/FacManSetup.run" ] ||
     [ -L "$maintenance/FacManSetup.run" ] ||
     [ "$(cat "$setup_authority")" != "$(sha256sum "$maintenance/FacManSetup.run" | cut -d ' ' -f 1)" ]; then
    echo 'FacMan installed Setup authority is missing or damaged' >&2
    exit 1
  fi
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
  if { [ -e "$entry_handoff" ] || [ -L "$entry_handoff" ]; } &&
     { [ -e "$pending" ] || [ -L "$pending" ] ||
       [ -e "$first_pending" ] || [ -L "$first_pending" ] ||
       [ -e "$repair_pending" ] || [ -L "$repair_pending" ]; }; then
    echo 'refusing conflicting Linux Setup recovery records' >&2
    exit 1
  fi
  if [ "$operation" = 'recover' ]; then
    if [ -e "$repair_pending" ] || [ -L "$repair_pending" ]; then
      finish_repair_record
      echo 'Interrupted Linux Setup repair completed'
    elif [ -e "$first_pending" ] || [ -L "$first_pending" ]; then
      restore_first_install_record
      echo 'Interrupted first Linux Setup install restored the prior absence'
    elif [ -e "$entry_handoff" ] || [ -L "$entry_handoff" ]; then
      assert_no_orphan_staging
      finish_completed_entry_handoff
      echo 'Interrupted Linux Setup entry handoff completed'
    else
      assert_no_orphan_staging
      restore_update_record "$pending"
      echo 'Interrupted Linux Setup update restored the preceding generation'
    fi
  else
    assert_no_orphan_staging
    if [ -e "$pending" ] || [ -L "$pending" ] ||
       [ -e "$first_pending" ] || [ -L "$first_pending" ] ||
       [ -e "$repair_pending" ] || [ -L "$repair_pending" ]; then
      echo 'recover the interrupted Setup operation before rollback' >&2
      exit 1
    fi
    restore_update_record "$rollback_record" preflight
    rollback_identity=$(stat -c '%d:%i' "$rollback_record")
    mv --no-copy -nT "$rollback_record" "$pending"
    if [ -e "$rollback_record" ] || [ -L "$rollback_record" ] ||
       [ ! -d "$pending" ] || [ -L "$pending" ] ||
       [ "$(stat -c '%d:%i' "$pending")" != "$rollback_identity" ]; then
      echo 'refusing incomplete Linux Setup rollback admission' >&2
      exit 1
    fi
    restore_update_record "$pending"
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
  if [ -e "$pending" ] || [ -L "$pending" ] ||
     [ -e "$first_pending" ] || [ -L "$first_pending" ] ||
     [ -e "$repair_pending" ] || [ -L "$repair_pending" ]; then
    echo 'recover the interrupted Setup operation before uninstall' >&2
    exit 1
  fi
  assert_no_orphan_staging
  assert_active_generation
  assert_native_integration_owned
  if [ -e "$generation" ] || [ -L "$generation" ]; then
    assert_owned_generation "$generation"
  fi
  if [ -e "$rollback_record" ] || [ -L "$rollback_record" ]; then
    restore_update_record "$rollback_record" check
    admitted_previous=$(cat "$rollback_record/old-target")
  else
    admitted_previous=''
  fi
  if [ -e "$setup_authority" ] || [ -L "$setup_authority" ]; then
    if [ ! -f "$setup_authority" ] || [ -L "$setup_authority" ] ||
       [ "$(cat "$setup_authority")" != "$(sha256sum "$0" | cut -d ' ' -f 1)" ]; then
      echo 'refusing changed installed Setup authority during uninstall' >&2
      exit 1
    fi
  fi
  if [ -d "$install_root/generations" ]; then
    hidden_generation=$(find "$install_root/generations" -mindepth 1 -maxdepth 1 -name '.*' -print -quit)
    if [ -n "$hidden_generation" ]; then
      echo 'refusing hidden or interrupted generation during uninstall' >&2
      exit 1
    fi
    for owned_generation in "$install_root/generations/"*; do
      if [ -e "$owned_generation" ] || [ -L "$owned_generation" ]; then
        if [ "$owned_generation" != "$generation" ] &&
           [ "$owned_generation" != "$admitted_previous" ]; then
          echo 'refusing a generation outside the installed lineage' >&2
          exit 1
        fi
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
  assert_active_generation
  assert_native_integration_owned
  for owned_name in facman FacMan; do
    if [ -L "$user_bin/$owned_name" ]; then
      assert_native_integration_owned
      rm -f "$user_bin/$owned_name"
    fi
  done
  desktop="$desktop_root/facman.desktop"
  if [ -f "$desktop" ]; then
    assert_native_integration_owned
    rm -f "$desktop"
  fi
  assert_active_generation
  rm -f "$current"
  for owned_generation in "$install_root/generations/"*; do
    if [ -e "$owned_generation" ] || [ -L "$owned_generation" ]; then
      if [ "$owned_generation" != "$generation" ] &&
         [ "$owned_generation" != "$admitted_previous" ]; then
        echo 'refusing a generation outside the installed lineage' >&2
        exit 1
      fi
      assert_owned_generation "$owned_generation"
      rm -rf "$owned_generation"
    fi
  done
  if [ -d "$rollback_record" ]; then rm -rf "$rollback_record"; fi
  rm -f "$setup_copy" "$state/installed-state.v1.json" "$setup_authority"
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
if [ -e "$entry_handoff" ] || [ -L "$entry_handoff" ]; then
  if [ -e "$pending" ] || [ -L "$pending" ] ||
     [ -e "$first_pending" ] || [ -L "$first_pending" ] ||
     [ -e "$repair_pending" ] || [ -L "$repair_pending" ]; then
    echo 'refusing conflicting Linux Setup recovery records' >&2
    exit 1
  fi
  if [ "$operation" != 'install' ]; then
    echo 'recover the interrupted Linux Setup entry handoff before repair' >&2
    exit 1
  fi
  finish_completed_entry_handoff
fi
if [ -e "$pending" ] || [ -L "$pending" ] ||
   [ -e "$first_pending" ] || [ -L "$first_pending" ] ||
   [ -e "$repair_pending" ] || [ -L "$repair_pending" ]; then
  echo 'recover the interrupted Setup operation before install or repair' >&2
  exit 1
fi
assert_no_orphan_staging
if [ "$operation" = 'install' ]; then
  assert_existing_install_owner
else
  assert_active_generation
fi
assert_native_integration_owned
assert_setup_copy_safe
assert_setup_authority_safe
first_install='false'
if [ "$operation" = 'install' ] && [ -z "${old_target:-}" ]; then
  first_install='true'
  if [ -d "$install_root" ]; then
    foreign=$(find "$install_root" -mindepth 1 -maxdepth 1 ! -name generations ! -name state ! -name maintenance -print -quit)
    [ -z "$foreign" ] || { echo 'refusing foreign first-install content' >&2; exit 1; }
  fi
  for directory in "$install_root/generations" "$state" "$maintenance"; do
    if [ -d "$directory" ] &&
       [ -n "$(find "$directory" -mindepth 1 -maxdepth 1 -print -quit)" ]; then
      echo 'refusing nonempty first-install effect root' >&2
      exit 1
    fi
  done
fi
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
    assert_previous_setup_source "$maintenance/FacManSetup.run" "$old_version" "$old_target"
    if [ ! -f "$maintenance/FacManSetup.run" ] ||
       [ -L "$maintenance/FacManSetup.run" ]; then
      echo 'refusing update without the previous Setup source' >&2
      exit 1
    fi
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
  assert_setup_authority_safe
  if [ ! -f "$maintenance/FacManSetup.run" ] ||
     [ -L "$maintenance/FacManSetup.run" ]; then
    echo 'refusing a missing Linux Setup update predecessor' >&2
    return 1
  fi
  if [ "$old_target" != "$expected_old_target" ] ||
     [ "$(cat "$state/installed-state.v1.json")" != "$expected_old_receipt" ] ||
     [ "$(sha256sum "$maintenance/FacManSetup.run" | cut -d ' ' -f 1)" != "$expected_old_setup_sha" ]; then
    echo 'refusing a changed Linux Setup update predecessor' >&2
    return 1
  fi
  verify_generation "$old_target"
  assert_previous_setup_source "$maintenance/FacManSetup.run" "$old_version" "$old_target"
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

if [ "$operation" = 'repair' ]; then
  assert_owned_generation "$generation" repair-damaged
  if ! cmp -s "$generation/share/facman/manifest/MANIFEST.sha256" \
                "$source_root/share/facman/manifest/MANIFEST.sha256"; then
    echo 'refusing repair over changed generation ownership manifest' >&2
    exit 1
  fi
  mkdir -p "$maintenance" "$state" "$install_root/generations"
  if [ ! -e "$maintenance/FacManSetup.run" ] &&
     [ ! -L "$maintenance/FacManSetup.run" ]; then
    replace_file "$0" "$maintenance/FacManSetup.run" 0755
  fi
  repair_stage="$install_root/generations/.install-$version-$$"
  repair_backup="$install_root/generations/.repair-previous-$version-$$"
  if [ -e "$repair_stage" ] || [ -L "$repair_stage" ] ||
     [ -e "$repair_backup" ] || [ -L "$repair_backup" ]; then
    echo 'refusing preexisting Linux Setup repair effects' >&2
    exit 1
  fi
  cp -a "$source_root" "$repair_stage"
  assert_owned_generation "$repair_stage"
  verify_generation "$repair_stage"
  assert_active_generation
  assert_owned_generation "$generation" repair-damaged
  assert_native_integration_owned
  assert_setup_authority_safe
  journal_staging="$state/.repair-prepared-$$"
  if [ -e "$journal_staging" ] || [ -L "$journal_staging" ]; then
    echo 'refusing preexisting Linux Setup repair journal staging' >&2
    exit 1
  fi
  mkdir "$journal_staging"
  printf '%s\n' "$generation" > "$journal_staging/new-target"
  printf '%s\n' "$repair_stage" > "$journal_staging/staging-target"
  printf '%s\n' "$repair_backup" > "$journal_staging/backup-target"
  cp "$source_root/share/facman/manifest/MANIFEST.sha256" "$journal_staging/manifest-copy"
  printf '[Desktop Entry]\nType=Application\nName=FacMan\nComment=Manage Factorio installations and isolated instances\nExec=%s/FacMan\nTerminal=false\nCategories=Game;Utility;\n' "$current" > "$journal_staging/desktop-copy"
  sha256sum "$source_root/share/facman/manifest/MANIFEST.sha256" | cut -d ' ' -f 1 > "$journal_staging/manifest-sha256"
  sha256sum "$0" | cut -d ' ' -f 1 > "$journal_staging/setup-sha256"
  if [ -e "$repair_pending" ] || [ -L "$repair_pending" ]; then
    echo 'refusing changed Linux Setup repair journal destination' >&2
    exit 1
  fi
  mv -T "$journal_staging" "$repair_pending"
  journal_staging=''
  if [ "${FACMAN_TEST_LINUX_SETUP_INTERRUPT_REPAIR_AFTER_JOURNAL:-}" = '1' ]; then
    echo 'injected interruption after Linux Setup repair journal publication' >&2
    exit 75
  fi
  finish_repair_record
  [ "$quiet" = 'true' ] || echo "FacMan $version repaired for the current user"
  exit 0
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
if [ "$first_install" = 'true' ]; then
  journal_staging="$state/.first-install-prepared-$$"
  if [ -e "$journal_staging" ] || [ -L "$journal_staging" ]; then
    echo 'refusing a preexisting first-install staging record' >&2
    exit 1
  fi
  mkdir "$journal_staging"
  printf '%s\n' "$generation" > "$journal_staging/new-target"
  printf '%s\n' "$staging" > "$journal_staging/staging-target"
  sha256sum "$0" | cut -d ' ' -f 1 > "$journal_staging/new-setup-sha256"
  if [ -e "$first_pending" ] || [ -L "$first_pending" ]; then
    echo 'refusing a changed first-install recovery destination' >&2
    exit 1
  fi
  mv -T "$journal_staging" "$first_pending"
  journal_staging=''
  if [ "${FACMAN_TEST_LINUX_SETUP_INTERRUPT_FIRST_AFTER_JOURNAL:-}" = '1' ]; then
    echo 'injected interruption after first Linux Setup recovery publication' >&2
    exit 75
  fi
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
  printf '%s\n' "$predecessor_sha" > "$journal_staging/old-setup-sha256"
  printf '%s\n' "$predecessor_authority_mode" > "$journal_staging/old-authority-mode"
  sha256sum "$0" | cut -d ' ' -f 1 > "$journal_staging/new-setup-sha256"
  sha256sum "$generation/share/facman/manifest/MANIFEST.sha256" | cut -d ' ' -f 1 > "$journal_staging/new-generation-manifest-sha256"
  mv -T "$journal_staging" "$pending"
  journal_staging=''
  assert_update_predecessor
  # The installed maintenance entry point must be able to recover the cutover.
  replace_file "$0" "$maintenance/FacManSetup.run" 0755
fi
if [ "$first_install" = 'true' ]; then
  replace_file "$0" "$maintenance/FacManSetup.run" 0755
fi
if [ "$first_install" = 'true' ] &&
   { [ -e "$current" ] || [ -L "$current" ]; }; then
  echo 'refusing a changed first-install current pointer at cutover' >&2
  exit 1
fi
point_current "$generation"
if [ "$source_distinct" = 'true' ] &&
   [ "${FACMAN_TEST_LINUX_SETUP_INTERRUPT_AFTER_CURRENT:-}" = '1' ]; then
  echo 'injected interruption after Linux Setup current cutover' >&2
  exit 75
fi
if [ "$first_install" = 'true' ] &&
   [ "${FACMAN_TEST_LINUX_SETUP_INTERRUPT_FIRST_AFTER_CURRENT:-}" = '1' ]; then
  echo 'injected interruption after first Linux Setup current cutover' >&2
  exit 75
fi
assert_native_integration_owned
ln -sfn "$current/facman" "$user_bin/facman"
ln -sfn "$current/FacMan" "$user_bin/FacMan"
if [ "$source_distinct" != 'true' ] && [ "$first_install" != 'true' ]; then
  replace_file "$0" "$maintenance/FacManSetup.run" 0755
fi
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
assert_native_integration_owned
mv -fT "$active_staging" "$desktop_root/facman.desktop"
active_staging=''
if [ "$first_install" = 'true' ] &&
   { [ -e "$state/installed-state.v1.json" ] ||
     [ -L "$state/installed-state.v1.json" ]; }; then
  echo 'refusing a changed first-install receipt destination' >&2
  exit 1
fi
active_staging=$(mktemp "$state/.installed-state.v1.json.XXXXXX")
cat > "$active_staging" <<EOF
{"schema":"facman.installed_state.v1","version":"$version","generation":"$generation","workspace_preserved":true}
EOF
mv -fT "$active_staging" "$state/installed-state.v1.json"
active_staging=''
if [ "$first_install" = 'true' ] &&
   [ "${FACMAN_TEST_LINUX_SETUP_INTERRUPT_FIRST_AFTER_RECEIPT:-}" = '1' ]; then
  echo 'injected interruption after first Linux Setup receipt publication' >&2
  exit 75
fi
if [ "$first_install" = 'true' ] &&
   { [ -e "$setup_authority" ] || [ -L "$setup_authority" ]; }; then
  echo 'refusing a changed first-install Setup authority destination' >&2
  exit 1
fi
active_staging=$(mktemp "$state/.installed-setup.sha256.XXXXXX")
sha256sum "$0" | cut -d ' ' -f 1 > "$active_staging"
chmod 0600 "$active_staging"
mv -fT "$active_staging" "$setup_authority"
active_staging=''
verify_generation "$generation"
if [ "$source_distinct" = 'true' ]; then
  mv -T "$pending" "$rollback_record"
fi
if [ "$first_install" = 'true' ]; then
  archive_record "$first_pending" "completed-first-install-${version}"
fi
[ "$quiet" = 'true' ] || echo "FacMan $version installed for the current user"
exit 0

__FACMAN_PAYLOAD_BELOW__
'''
    return (script.replace("@VERSION@", version)
            .replace("@PAYLOAD_SHA256@", payload_sha256)
            .replace("@ADMITTED_PREDECESSOR_CASES@", predecessor_cases).encode())


def build(portable: Path, output: Path, evidence: Path) -> dict[str, object]:
    portable = portable.resolve(strict=True)
    version = version_truth()
    expected = f"FacMan-{version}-linux-x64-portable.tar.zst"
    if portable.name != expected:
        raise ValueError(f"unexpected Linux portable input: {portable.name}")
    output.mkdir(parents=True, exist_ok=True)
    catalog_sha256 = sha256(PREDECESSORS)
    predecessors = admitted_predecessors(version)
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
    if catalog_sha256 != sha256(PREDECESSORS) or predecessors != admitted_predecessors(version):
        setup.unlink(missing_ok=True)
        raise ValueError("Linux Setup predecessor admission changed during package build")
    setup.chmod(0o755)
    record = {
        "schema": "facman.linux_self_setup.v1",
        "status": "pass",
        "version": version,
        "platform": "linux",
        "architecture": "x64",
        "source_revision": git("rev-parse", "HEAD"),
        "source_tree": git("rev-parse", "HEAD^{tree}"),
        "admitted_predecessors": [
            {"version": old_version, "sha256": digest}
            for old_version, digest in predecessors
        ],
        "predecessor_catalog_sha256": catalog_sha256,
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
