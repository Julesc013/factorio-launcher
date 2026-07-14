# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

from tools import m2_wu9_adversarial_check


class M2Wu9AdversarialProofTests(unittest.TestCase):
    def test_provider_manifest_identity_is_checkout_line_ending_invariant(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lf = root / "lf.json"
            crlf = root / "crlf.json"
            lf.write_bytes(b'{\n  "status": "pass"\n}\n')
            crlf.write_bytes(b'{\r\n  "status": "pass"\r\n}\r\n')
            self.assertEqual(
                m2_wu9_adversarial_check.canonical_text_sha256(lf),
                m2_wu9_adversarial_check.canonical_text_sha256(crlf),
            )

    def test_complete_cross_repository_corpus_is_bound_and_fail_closed(self) -> None:
        self.assertEqual(0, m2_wu9_adversarial_check.main())


if __name__ == "__main__":
    unittest.main()
