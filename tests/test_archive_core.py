from __future__ import annotations

import io
import os
import random
import shutil
import struct
import subprocess
import tempfile
import unittest
import unicodedata
import zipfile
from pathlib import Path

from tools import archive_core_check

ROOT = Path(__file__).resolve().parents[1]


def native_executable(name: str) -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    explicit = os.environ.get(f"FACMAN_{name.upper()}_EXE")
    if explicit:
        path = Path(explicit)
        if path.is_file():
            return path
        raise AssertionError(f"configured native executable is missing: {path}")
    matches = sorted(
        ROOT.glob(f"build/**/{name}{suffix}"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if matches:
        return matches[0]
    raise unittest.SkipTest(f"{name} has not been built")


def inspect(path: Path, *limits: str) -> tuple[int, str, str]:
    completed = subprocess.run(
        [str(native_executable("fl_archive_probe")), "inspect", str(path), *limits],
        cwd=ROOT,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
    )
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def verify(path: Path, *limits: str) -> tuple[int, str, str]:
    completed = subprocess.run(
        [str(native_executable("fl_archive_probe")), "verify", str(path), *limits],
        cwd=ROOT,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def write_zip(path: Path, entries: list[tuple[zipfile.ZipInfo | str, bytes]], compression: int) -> None:
    with zipfile.ZipFile(path, "w", compression=compression, allowZip64=True) as archive:
        for name, payload in entries:
            archive.writestr(name, payload)


def mutate_first(data: bytes, signature: bytes, relative_offset: int, replacement: bytes) -> bytes:
    offset = data.find(signature)
    if offset < 0:
        raise AssertionError(f"signature not found: {signature!r}")
    output = bytearray(data)
    output[offset + relative_offset : offset + relative_offset + len(replacement)] = replacement
    return bytes(output)


class NonSeekableBuffer(io.BytesIO):
    def seekable(self) -> bool:
        return False

    def seek(self, *_args: object, **_kwargs: object) -> int:
        raise io.UnsupportedOperation("non-seekable")


class ArchiveCoreTests(unittest.TestCase):
    def test_archive_core_structure_and_legacy_boundary(self) -> None:
        self.assertEqual(archive_core_check.validate(), [])

    def test_valid_stored_deflate_descriptor_and_path_forms(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for compression in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                archive = root / f"valid-{compression}.zip"
                write_zip(
                    archive,
                    [
                        ("empty/", b""),
                        ("empty/zero.txt", b""),
                        ("spaces and unicode/caf\N{LATIN SMALL LETTER E WITH ACUTE}.txt", b"payload"),
                        ("deep/one/two/three.txt", b"nested"),
                    ],
                    compression,
                )
                code, status, detail = inspect(archive)
                self.assertEqual((code, status), (0, "ok"), detail)

            stream = NonSeekableBuffer()
            with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("descriptor/payload.txt", b"descriptor" * 100)
            descriptor = root / "descriptor.zip"
            descriptor.write_bytes(stream.getvalue())
            code, status, detail = inspect(descriptor)
            self.assertEqual((code, status), (0, "ok"), detail)

    def test_path_collision_and_file_type_corpus_refuses(self) -> None:
        cases: dict[str, list[tuple[zipfile.ZipInfo | str, bytes]]] = {
            "absolute": [("/escape.txt", b"x")],
            "parent": [("../escape.txt", b"x")],
            "backslash": [("a\\escape.txt", b"x")],
            "ads": [("a/stream:name", b"x")],
            "reserved": [("NUL.txt", b"x")],
            "dot": [("a/./x.txt", b"x")],
            "empty-segment": [("a//x.txt", b"x")],
            "duplicate": [("same.txt", b"a"), ("same.txt", b"b")],
            "case": [("Case.txt", b"a"), ("case.txt", b"b")],
            "normalization": [
                (unicodedata.normalize("NFC", "cafe\N{COMBINING ACUTE ACCENT}.txt"), b"a"),
                (unicodedata.normalize("NFD", "cafe\N{COMBINING ACUTE ACCENT}.txt"), b"b"),
            ],
            "file-directory": [("node", b"a"), ("node/child.txt", b"b")],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, entries in cases.items():
                with self.subTest(name=name):
                    archive = root / f"{name}.zip"
                    with self.assertWarns(UserWarning) if name == "duplicate" else _null_context():
                        write_zip(archive, entries, zipfile.ZIP_STORED)
                    if name == "backslash":
                        archive.write_bytes(archive.read_bytes().replace(b"a/escape.txt", b"a\\escape.txt"))
                    code, status, _detail = inspect(archive)
                    self.assertEqual(code, 2)
                    self.assertNotEqual(status, "ok")

            symlink = zipfile.ZipInfo("linked-entry")
            symlink.create_system = 3
            symlink.external_attr = 0o120777 << 16
            archive = root / "symlink.zip"
            write_zip(archive, [(symlink, b"outside")], zipfile.ZIP_STORED)
            self.assertEqual(inspect(archive)[1], "archive_entry_symlink")

            for name, mode in {"fifo": 0o010644, "device": 0o020644, "socket": 0o140644}.items():
                special = zipfile.ZipInfo(name)
                special.create_system = 3
                special.external_attr = mode << 16
                archive = root / f"{name}.zip"
                write_zip(archive, [(special, b"x")], zipfile.ZIP_STORED)
                self.assertEqual(inspect(archive)[1], "archive_entry_unsupported_file_type")

    def test_crc_truncation_encryption_multidisk_and_extra_corpus_refuses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "base.zip"
            write_zip(base, [("payload.txt", b"payload" * 100)], zipfile.ZIP_DEFLATED)
            data = base.read_bytes()

            local_name_size = struct.unpack_from("<H", data, 26)[0]
            local_extra_size = struct.unpack_from("<H", data, 28)[0]
            payload_offset = 30 + local_name_size + local_extra_size
            bad_crc = bytearray(data)
            bad_crc[payload_offset] ^= 0x40
            (root / "bad-crc.zip").write_bytes(bad_crc)

            encrypted = mutate_first(data, b"PK\x03\x04", 6, struct.pack("<H", 1))
            encrypted = mutate_first(encrypted, b"PK\x01\x02", 8, struct.pack("<H", 1))
            (root / "encrypted.zip").write_bytes(encrypted)

            multidisk = bytearray(data)
            eocd = multidisk.rfind(b"PK\x05\x06")
            struct.pack_into("<H", multidisk, eocd + 4, 1)
            (root / "multidisk.zip").write_bytes(multidisk)

            malformed = zipfile.ZipInfo("malformed.txt")
            malformed.extra = b"\x34\x12\x08\x00x"
            malformed_archive = root / "malformed-extra.zip"
            write_zip(malformed_archive, [(malformed, b"x")], zipfile.ZIP_STORED)

            corpus = {
                "bad-crc.zip": None,
                "encrypted.zip": "archive_entry_encrypted",
                "multidisk.zip": "archive_multidisk_unsupported",
                "malformed-extra.zip": "archive_extra_malformed",
            }
            for name, expected in corpus.items():
                with self.subTest(name=name):
                    operation = verify if name == "bad-crc.zip" else inspect
                    code, status, _detail = operation(root / name)
                    self.assertEqual(code, 2)
                    if expected:
                        self.assertEqual(status, expected)

            for name, payload in {
                "truncated-local.zip": data[:20],
                "truncated-central.zip": data[:-10],
            }.items():
                (root / name).write_bytes(payload)
                self.assertEqual(inspect(root / name)[0], 2)

            mismatch = bytearray(data)
            mismatch[30] ^= 0x01
            (root / "local-name-mismatch.zip").write_bytes(mismatch)
            self.assertEqual(inspect(root / "local-name-mismatch.zip")[1], "archive_local_name_mismatch")

            overlap = root / "overlap.zip"
            write_zip(overlap, [("one.txt", b"a"), ("two.txt", b"b")], zipfile.ZIP_STORED)
            overlap_data = bytearray(overlap.read_bytes())
            second_local = overlap_data.find(b"PK\x03\x04", 4)
            first_central = overlap_data.find(b"PK\x01\x02")
            first_data = 30 + struct.unpack_from("<H", overlap_data, 26)[0] + struct.unpack_from(
                "<H", overlap_data, 28
            )[0]
            overlapping_size = second_local - first_data + 1
            struct.pack_into("<I", overlap_data, 18, overlapping_size)
            struct.pack_into("<I", overlap_data, 22, overlapping_size)
            struct.pack_into("<I", overlap_data, first_central + 20, overlapping_size)
            struct.pack_into("<I", overlap_data, first_central + 24, overlapping_size)
            overlap.write_bytes(overlap_data)
            self.assertEqual(inspect(overlap)[1], "archive_entry_ranges_overlap")

    def test_resource_limits_and_compression_ratio_refuse_before_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "limits.zip"
            write_zip(
                archive,
                [
                    (f"entry-{index}.txt" if index else "nested/entry-0.txt", b"0" * 20000)
                    for index in range(4)
                ],
                zipfile.ZIP_DEFLATED,
            )
            self.assertEqual(inspect(archive, "--entries", "2")[1], "archive_entry_count_limit")
            self.assertEqual(inspect(archive, "--archive", "100")[1], "archive_size_limit")
            self.assertEqual(inspect(archive, "--entry-compressed", "1")[1], "archive_entry_compressed_limit")
            self.assertEqual(inspect(archive, "--expanded", "100")[1], "archive_total_expanded_limit")
            self.assertEqual(inspect(archive, "--entry-expanded", "100")[1], "archive_entry_expanded_limit")
            self.assertEqual(inspect(archive, "--ratio", "2")[1], "archive_compression_ratio_limit")
            self.assertEqual(inspect(archive, "--path", "4")[1], "archive_path_too_long")
            self.assertEqual(inspect(archive, "--depth", "0")[1], "archive_path_depth_exceeded")
            self.assertEqual(verify(archive, "--milliseconds", "0")[1], "archive_read_limit_or_sink_failed")

    def test_property_generated_safe_paths_and_payloads_validate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "property.zip"
            source = random.Random(42003)
            entries: list[tuple[str, bytes]] = []
            for index in range(80):
                depth = 1 + source.randrange(5)
                segments = [f"segment-{index}-{part}-{source.randrange(10000)}" for part in range(depth)]
                entries.append(("/".join(segments) + ".txt", source.randbytes(source.randrange(2048))))
            write_zip(archive, entries, zipfile.ZIP_DEFLATED)
            code, status, detail = inspect(archive)
            self.assertEqual((code, status), (0, "ok"), detail)

    def test_metadata_mutations_and_fuzz_harnesses_never_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "seed.zip"
            write_zip(seed, [("seed.txt", b"seed" * 100)], zipfile.ZIP_DEFLATED)
            original = seed.read_bytes()
            mutations: list[Path] = []
            random_source = random.Random(1337)
            for index in range(48):
                payload = bytearray(original)
                for _ in range(1 + index % 4):
                    offset = random_source.randrange(len(payload))
                    payload[offset] ^= 1 << random_source.randrange(8)
                mutation = root / f"mutation-{index:02d}.zip"
                mutation.write_bytes(payload)
                mutations.append(mutation)
                code, _status, _detail = inspect(mutation)
                self.assertIn(code, (0, 2))

            for harness_name in ("fl_archive_metadata_fuzz", "fl_archive_plan_fuzz"):
                completed = subprocess.run(
                    [str(native_executable(harness_name)), *map(str, mutations)],
                    cwd=ROOT,
                    check=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=30,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr.decode(errors="replace"))


class _null_context:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *_args: object) -> None:
        return None


if __name__ == "__main__":
    unittest.main()
