from __future__ import annotations

import hashlib
import json
import tomllib
import unittest
from pathlib import Path

from tools.validators.release import check_dependency_lock

ROOT = Path(__file__).resolve().parents[1]
PICOJSON = ROOT / "external/picojson"


class JsonDependencyAdmissionTests(unittest.TestCase):
    def test_picojson_pin_license_and_hashes_are_exact(self) -> None:
        self.assertEqual(check_dependency_lock.validate(), [])
        with (ROOT / "release/index/dependency_lock.v1.toml").open("rb") as handle:
            lock = tomllib.load(handle)
        component = next(item for item in lock["component"] if item["id"] == "picojson")
        self.assertEqual(component["license"], "BSD-2-Clause")
        self.assertFalse(component["runtime_network"])
        self.assertEqual(component["transitive_runtime_dependencies"], [])
        self.assertEqual(
            hashlib.sha256((PICOJSON / "picojson.h").read_bytes()).hexdigest(),
            component["source_file_sha256"],
        )
        self.assertEqual(
            hashlib.sha256((PICOJSON / "LICENSE").read_bytes()).hexdigest(),
            component["license_file_sha256"],
        )

    def test_sbom_and_notices_close_over_picojson(self) -> None:
        sbom = json.loads((ROOT / "release/index/sbom.components.v1.json").read_text(encoding="utf-8"))
        component = next(item for item in sbom["components"] if item["id"] == "picojson")
        self.assertEqual(component["license"], "BSD-2-Clause")
        notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        self.assertIn("PicoJSON 1.3.0+git.111c9be", notices)
        self.assertIn("external/picojson/LICENSE", notices)

    def test_domain_code_cannot_include_upstream_header(self) -> None:
        offenders = []
        for path in (ROOT / "runtime").rglob("*"):
            if not path.is_file() or path.suffix not in {".c", ".cpp", ".h", ".hpp"}:
                continue
            if path == ROOT / "runtime/core/json/fl_json.cpp":
                continue
            if "picojson.h" in path.read_text(encoding="utf-8", errors="replace"):
                offenders.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
