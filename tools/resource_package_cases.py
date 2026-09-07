# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
"""Independent bounded package/ZIP observations and private resource proof cases."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import time
import zipfile

MAX_FILE = 512 * 1024 * 1024
MAX_TOTAL = 2 * 1024 * 1024 * 1024
MAX_FILES = 65536
MAX_NODES = 131072
MAX_MEMBER = 32 * 1024 * 1024
MAX_EXPANDED = 512 * 1024 * 1024
MAX_ENTRIES = 20001
MANIFEST = "manifest/resource-pack.v1.json"
MARKER = ".facman-archive-staging.v1"
PROFILES = {
    "windows_product_x64": ("bin/facman.exe", "facman.resources", "manifest/package.v1.toml"),
    "linux_product_x64": ("facman", "share/facman/facman.resources", "share/facman/manifest/product-stage.v1.json"),
    "macos_product_x64": ("Contents/Helpers/facman", "Contents/Resources/facman.resources",
                          "Contents/Resources/manifest/product-stage.v1.json"),
}
CASE_IDS = (
    "original_identity", "relocated_identity", "export_members",
    "existing_output_refusal", "missing_resource_refusal",
    "truncated_resource_refusal", "foreign_resource_refusal",
    "no_display_terminal", "original_unchanged",
)


def require(condition: bool, detail: str) -> None:
    if not condition:
        raise ValueError(detail)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encoded(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode()


def plain_path(path: Path) -> Path:
    """Observe every existing component before resolving; never accept links."""
    path = path.absolute()
    require(".." not in path.parts, "dot-parent path refused")
    for part in (path, *path.parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        require(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
                f"linked/reparse path refused: {part}")
    return path



def require_package_path(reported: str, expected: Path) -> None:
    """Compare canonical spellings after link refusal, not equal-content aliases."""
    actual = Path(reported)
    require(actual.is_absolute(), "CLI package path must be absolute")
    canonical = []
    for path in (actual, expected):
        observed = plain_path(path)
        resolved = observed.resolve(strict=True)
        plain_path(observed)
        plain_path(resolved)
        require(observed.samefile(resolved), "package path identity changed")
        canonical.append(resolved)
    require(canonical[0] == canonical[1], "CLI did not identify its actual relocated package")
    require(canonical[0].samefile(canonical[1]), "CLI package path names a different object")


def file_bytes(path: Path, limit: int = MAX_FILE, output=None) -> tuple[dict, bytes]:
    plain_path(path)
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_size <= limit, f"file bound/type refused: {path}")
    identity = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)
    h = hashlib.sha256()
    chunks = [] if output is None and limit <= MAX_MEMBER else None
    count = 0
    started = time.monotonic()
    with path.open("rb") as stream:
        require(identity(os.fstat(stream.fileno())) == identity(before), f"file changed before read: {path}")
        while block := stream.read(1024 * 1024):
            count += len(block)
            require(count <= limit and time.monotonic() - started < 30, f"file read budget: {path}")
            h.update(block)
            if output is not None:
                output.write(block)
            if chunks is not None:
                chunks.append(block)
        require(identity(os.fstat(stream.fileno())) == identity(before), f"file changed while reading: {path}")
    require(identity(path.lstat()) == identity(before), f"file pathname changed: {path}")
    return {"size": count, "sha256": h.hexdigest(), "mode": stat.S_IMODE(before.st_mode)}, b"".join(chunks or [])


def snapshot(root: Path) -> dict:
    root = plain_path(root)
    require(root.is_dir(), "package root is not a directory")
    pending = [root]
    files, directories = [], []
    total = nodes = 0
    started = time.monotonic()
    while pending:
        parent = pending.pop()
        plain_path(parent)
        for path in sorted(parent.iterdir()):
            nodes += 1
            require(nodes <= MAX_NODES and time.monotonic() - started < 60, "inventory traversal budget")
            plain_path(path)
            info = path.lstat()
            relative = path.relative_to(root).as_posix()
            if stat.S_ISDIR(info.st_mode):
                directories.append({"path": relative, "mode": stat.S_IMODE(info.st_mode)})
                pending.append(path)
            else:
                record, _ = file_bytes(path)
                record["path"] = relative
                files.append(record)
                total += record["size"]
                require(len(files) <= MAX_FILES and total <= MAX_TOTAL, "package inventory budget")
    return {"files": sorted(files, key=lambda row: row["path"]),
            "directories": sorted(directories, key=lambda row: row["path"])}


def layout(executable: Path, profile: str) -> tuple[Path, tuple[str, str, str]]:
    require(profile in PROFILES, "unknown resource package profile")
    names = PROFILES[profile]
    executable = plain_path(executable)
    suffix = Path(names[0]).parts
    require(executable.parts[-len(suffix):] == suffix, "executable does not match declared product layout")
    root = executable.parents[len(suffix) - 1]
    for name in names:
        require(plain_path(root / name).is_file(), f"required package member missing: {name}")
    return root, names


def copy_package(source: Path, target: Path, before: dict) -> None:
    require(not target.exists(), "private relocation already exists")
    target.mkdir()
    for row in sorted(before["directories"], key=lambda item: item["path"].count("/")):
        path = target / row["path"]
        path.mkdir()
        os.chmod(path, row["mode"])
    for row in before["files"]:
        path = target / row["path"]
        with path.open("xb") as output:
            observed, _ = file_bytes(source / row["path"], output=output)
        require(observed == {k: v for k, v in row.items() if k != "path"}, "source changed during relocation")
        os.chmod(path, row["mode"])
    require(snapshot(target) == before, "relocation differs from original package inventory")


def safe_member(info: zipfile.ZipInfo) -> None:
    name = info.filename
    pieces = name.split("/")
    require(name and not name.startswith("/") and "\\" not in name and ":" not in name and
            all(part and part not in (".", "..") for part in pieces), "unsafe ZIP member")
    require(len(name.encode()) <= 1024 and len(pieces) <= 65, "ZIP member path budget")
    require(not info.is_dir() and not info.flag_bits & 1 and
            stat.S_IFMT(info.external_attr >> 16) in (0, stat.S_IFREG), "non-file ZIP member")
    require(info.file_size <= MAX_MEMBER and info.compress_size <= MAX_MEMBER, "ZIP member byte budget")


def zip_oracle(path: Path) -> dict:
    plain_path(path)
    require(path.stat().st_size <= MAX_FILE, "resource archive byte budget")
    members = {}
    manifest_bytes = b""
    total = 0
    started = time.monotonic()
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        require(0 < len(infos) <= MAX_ENTRIES, "resource entry-count budget")
        folded = set()
        for info in infos:
            safe_member(info)
            require(info.filename.casefold() not in folded, "duplicate/colliding ZIP member")
            folded.add(info.filename.casefold())
            total += info.file_size
            require(total <= MAX_EXPANDED, "resource expansion budget")
            h, consumed, captured = hashlib.sha256(), 0, []
            with archive.open(info) as stream:
                while block := stream.read(65536):
                    consumed += len(block)
                    require(consumed <= info.file_size and time.monotonic() - started < 60,
                            "resource stream budget")
                    h.update(block)
                    if info.filename == MANIFEST:
                        captured.append(block)
            require(consumed == info.file_size, "ZIP member size mismatch")
            members[info.filename] = {"size": consumed, "sha256": h.hexdigest()}
            if info.filename == MANIFEST:
                manifest_bytes = b"".join(captured)
    require(MANIFEST in members, "resource internal manifest missing")
    manifest = json.loads(manifest_bytes)
    require(manifest.get("schema") == "facman.runtime_resource_pack.v1", "unknown resource manifest")
    declared = manifest.get("entries")
    require(isinstance(declared, list), "resource entries are not an array")
    names = [item["path"] for item in declared]
    require(len(names) == len(set(names)) and set(names) == set(members) - {MANIFEST},
            "resource manifest inventory mismatch")
    aggregate = hashlib.sha256()
    for row in declared:
        expected = members[row["path"]]
        require(type(row["bytes"]) is int and row["bytes"] == expected["size"] and
                row["sha256"] == expected["sha256"], "resource manifest member mismatch")
        aggregate.update(row["path"].encode() + b"\0" + str(row["bytes"]).encode() + b"\0" +
                         row["sha256"].encode() + b"\n")
    require(manifest["content_sha256"] == aggregate.hexdigest() and
            manifest["entry_count"] == len(names) and
            manifest["expanded_bytes"] == total - len(manifest_bytes), "resource aggregate mismatch")
    return {"members": members, "entries": names, "content_sha256": aggregate.hexdigest(),
            "expanded_bytes": manifest["expanded_bytes"], "version": manifest["version"]}


def foreign_pack(path: Path) -> None:
    name, data = "content/proof-foreign.txt", b"Foreign resource qualification fixture\n"
    member = {"path": name, "bytes": len(data), "sha256": digest(data)}
    aggregate = digest(name.encode() + b"\0" + str(len(data)).encode() + b"\0" +
                       member["sha256"].encode() + b"\n")
    manifest = {"schema": "facman.runtime_resource_pack.v1", "version": "foreign-proof",
                "content_sha256": aggregate, "entry_count": 1, "expanded_bytes": len(data),
                "entries": [member]}
    with zipfile.ZipFile(path, "x", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr(MANIFEST, encoded(manifest))
        archive.writestr(name, data)


def identity_cases(driver, executable: Path, names: tuple, profile: str, root: Path,
                   oracle: dict, package: dict, label: str) -> None:
    indexed = {row["path"]: row for row in package["files"]}
    for verb in ("list", "verify"):
        result = driver.json(label + "_" + verb, executable, ["resources", verb, "--json"])
        expected = {"schema": "facman.runtime_resource_pack_inventory.v1", "status": "pass",
                    "package_profile": profile, "package_manifest_sha256": indexed[names[2]]["sha256"],
                    "pack_sha256": indexed[names[1]]["sha256"], "entries": oracle["entries"],
                    "expanded_bytes": oracle["expanded_bytes"], "content_sha256": oracle["content_sha256"],
                    "entry_count": len(oracle["entries"]), "version": oracle["version"]}
        require(all(result.get(k) == v for k, v in expected.items()), "CLI differs from independent resource identity")
        require_package_path(result["path"], root / names[1])


def exported_inventory(root: Path, oracle: dict) -> dict:
    observed = snapshot(root)
    files = {row["path"]: {"size": row["size"], "sha256": row["sha256"]} for row in observed["files"]}
    expected = dict(oracle["members"])
    marker = b"schema=facman.archive_staging.v1\n"
    expected[MARKER] = {"size": len(marker), "sha256": digest(marker)}
    require(files == expected, "exported files/marker differ from independent ZIP bytes")
    directories = {str(parent) for name in expected for parent in PurePosixPath(name).parents if str(parent) != "."}
    require({row["path"] for row in observed["directories"]} == directories, "export directory inventory differs")
    return observed


def run_cases(driver, root: Path, names: tuple, profile: str, before: dict, oracle: dict,
              work: Path, complete) -> None:
    identity_cases(driver, root / names[0], names, profile, root, oracle, before, "original")
    complete("original_identity")
    relocated = work / "Relocated package \u00e9 \u03b2"
    if profile == "macos_product_x64":
        relocated.mkdir()
        relocated /= "FacMan.app"
    copy_package(root, relocated, before)
    executable, resource = relocated / names[0], relocated / names[1]
    identity_cases(driver, executable, names, profile, relocated, oracle, before, "relocated")
    complete("relocated_identity")
    for label, image in (("original", root / names[0]), ("relocated", executable)):
        for option in ("--help", "--version"):
            driver.raw(label + "_" + option[2:], image, [option])
    destination = work / "Exported resources"
    result = driver.json("export", executable, ["resources", "export", str(destination), "--json"])
    require(result.get("schema") == "facman.runtime_resource_pack_export.v1" and
            result.get("status") == "pass" and result.get("entry_count") == len(oracle["entries"]) and
            "source" in result and "destination" in result,
            "unexpected resource export response")
    require_package_path(result["source"], resource)
    require_package_path(result["destination"], destination)
    exported = exported_inventory(destination, oracle)
    complete("export_members")
    driver.refusal("existing_output", executable, ["resources", "export", str(destination), "--json"],
                   prefixes=("archive_",))
    require(snapshot(destination) == exported, "existing-output refusal changed export")
    complete("existing_output_refusal")
    resource.rename(work / "retained-original.resources")
    for kind in ("missing", "truncated", "foreign"):
        if kind == "truncated":
            with resource.open("xb") as stream:
                stream.write(b"PK\x03\x04")
        if kind == "foreign":
            foreign_pack(resource)
            zip_oracle(resource)
            driver.json("standalone_foreign", executable,
                        ["resources", "verify", "--pack", str(resource), "--json"])
        driver.refusal(kind, executable, ["resources", "verify", "--json"])
        for option in ("--help", "--version"):
            driver.raw(kind + "_" + option[2:], executable, [option])
        complete(kind + "_resource_refusal")
        if resource.exists():
            resource.rename(work / (kind + ".resources"))
    (work / "retained-original.resources").rename(resource)
    require(snapshot(relocated) == before, "private package not restored after refusal cases")
    complete("no_display_terminal")
