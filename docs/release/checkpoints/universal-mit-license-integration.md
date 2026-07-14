<!-- SPDX-FileCopyrightText: 2026 Jules C -->
<!-- SPDX-License-Identifier: MIT -->

# Universal MIT license integration

This immutable checkpoint accepts the operator-authorized MIT decision for
Universal Launcher and Universal Setup and binds it into FacMan package,
SBOM, provenance, redistribution-notice, and machine-truth surfaces.

## Exact source identities

| Repository | Accepted revision | Exact-main CI |
| --- | --- | --- |
| Universal Launcher | `6d41e07b76cd19b2a7630835e05ac3aa125d57b8` | `29311615251` |
| Universal Setup | `264bb1939a67231878313155157abd0f83d24c13` | `29311599523` |
| FacMan license task | `c253e05d882c0822bb33da1ae92e7d047ee92f68` | local clean proof |

The canonical MIT license blob in both Universal repositories has SHA-256
`fb32a9968f4a0e33e1e2f367ebe81f0d1703fd38b2e473d9e300f4efd8292b53`.
The FacMan task tree is `023f24e8b380d1e44bc835a3ee56e9388cd47920`.

The frozen M1 implementation and public-integration identities remain
unchanged. This checkpoint records a subsequent license/compliance integration;
it does not rewrite those implementation proofs.

## Clean reconstruction and reproducibility

The exact FacMan task revision was reconstructed with clean pinned checkouts of
both Universal providers. Configure, build, native tests, strict validation,
AIDE validation, and the Python corpus passed across all three repositories.
FacMan recorded 35/35 native tests passing.

Two independent selected-package builds produced identical outputs:

| Evidence | Identity |
| --- | --- |
| archive | 1,912,841 bytes; SHA-256 `993bf60ddd4332abdab1950d3df4220235314dac959806a1c2fa3dbf80267706` |
| package tree | 383 files; SHA-256 `81eab95e8cf0731932723e8a96ea75ad80c9a6f72502a78c54a60f8227031f44` |
| SPDX 2.3 SBOM | 6,220 bytes; SHA-256 `9b1939cb56f3e735c0bba733190f7f4dea827c8e95dd5868b7bf6eb26c53c872` |
| adjacent provenance | 2,088 bytes; SHA-256 `52a2e9fd637d78609671cff2baba3adbb7f063068c9a0b8d2e355ff39d58f03d` |

The clean proof exposed and remediated one Windows transaction-journal failure
beyond legacy `MAX_PATH`. A direct greater-than-260-character native I/O test
and the original long-root clean reconstruction both pass at the accepted task
revision.

## Authority boundary

This checkpoint resolves license identity and redistribution notice truth. It
does not authorize signing or publication. It does not promote live-target
setup apply, Factorio archive acceptance, `run.execute`, H1, Safe beta, Steam
mutation, registry mutation, elevation, networking, or credentials.

Artifacts remain unpublished and publisher authenticity remains unproven.
