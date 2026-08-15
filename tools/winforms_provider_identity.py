# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Project a strict WinForms provider resource from an exact CMake build identity."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.integration_source_observation import read_build_identity  # noqa: E402

HEX_40 = re.compile(r"^[0-9a-f]{40}$")


def project(build_root: Path, expected_ulk_revision: str) -> str:
    if HEX_40.fullmatch(expected_ulk_revision) is None:
        raise ValueError("expected ULK revision must be an exact lowercase Git id")
    _identity, values, _digest = read_build_identity(
        build_root / "facman-build-identity.v1.txt"
    )
    expected = {
        "universal_launcher": expected_ulk_revision,
        "provider_mode": "source",
        "provider_source_linkage": "shared",
        "provider_lock_kind": "sdk_candidate",
        "provider_conformance_only": "false",
        "provider_sdk_consumption_candidate": "true",
        "provider_candidate_differs_from_tracked": "true",
        "provider_consumption_classification": "sdk_candidate_source",
        "provider_release_identity_coherent": "false",
        "ulk_session_consumer_canary": "false",
        "source_dirty": "false",
    }
    for field, required in expected.items():
        if values[field] != required:
            raise ValueError(
                f"compiled build identity {field} differs from WinForms canary custody"
            )
    return (
        "classification=repaired_provider_canary;"
        f"universal_launcher={values['universal_launcher']};"
        f"universal_setup={values['universal_setup']}\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-root", type=Path, required=True)
    parser.add_argument("--expected-ulk-revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        content = project(args.build_root.resolve(), args.expected_ulk_revision)
        output = args.output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8", newline="\n")
    except (OSError, ValueError) as error:
        print(f"winforms-provider-identity: {error}", file=sys.stderr)
        return 1
    print(f"winforms-provider-identity: ok {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
