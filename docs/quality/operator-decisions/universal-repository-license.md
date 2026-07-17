# Universal Repository License Decision

- WorkUnit: `FACMAN-UNIVERSAL-LICENSE-OPERATOR-DECISION-01`
- Status: accepted
- Decision: MIT for Universal Launcher and Universal Setup
- Operator authorization date: 2026-07-14
- Publication authority: not granted

The operator explicitly selected MIT for both Universal repositories. FacMan
therefore replaces the former `NOASSERTION` provider values only at the exact
licensed revisions below:

| Repository | Canonical revision | Exact-main CI | License digest |
| --- | --- | --- | --- |
| Universal Launcher | `6d41e07b76cd19b2a7630835e05ac3aa125d57b8` | `29311615251` | `fb32a9968f4a0e33e1e2f367ebe81f0d1703fd38b2e473d9e300f4efd8292b53` |
| Universal Setup | `264bb1939a67231878313155157abd0f83d24c13` | `29311599523` | `fb32a9968f4a0e33e1e2f367ebe81f0d1703fd38b2e473d9e300f4efd8292b53` |

Each provider contains a repository-root MIT `LICENSE`, machine-readable
`release/license.v1.toml`, strict SPDX coverage, and LF normalization for the
extensionless license file. FacMan packages retain exact provider notices in
`LICENSES/UniversalLauncher.txt` and `LICENSES/UniversalSetup.txt`.

This resolves license identity and redistribution notice truth. It does not
authorize signing, publication, publisher-authenticity claims, network access,
setup mutation beyond separately authorized roots, or execution.
