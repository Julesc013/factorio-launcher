<!-- SPDX-FileCopyrightText: 2026 Jules C -->
<!-- SPDX-License-Identifier: MIT -->

# M2-WU6 Universal Launcher Live Setup Handoff

Status: accepted `dev` integration proof passed; human verdict `pending`.

This checkpoint binds Universal Launcher task `43115d50822ac5a3ab0c51801873ff9a230408dd`
and canonical main `7bd4425f0c35414f738159b45d8bec42edf70235`, whose exact-main CI run
`29337737777` passed.

FacMan task head `f0b27c2e7f2117f9df0a98edb2264608ab75b664` and PR #20 dev
merge `8c1ed53511332da2d9c2fbf04abb2d5e91c4df6c` have the identical Git tree
`12160f23f78095ab09f8b5fe91960bad87a967c7`. The exact-dev workflow set passed:

| Workflow | Run |
| --- | --- |
| CI | `29344174316` |
| CodeQL | `29344174402` |
| security policy | `29344174517` |

The additive Launcher and FacMan binding ABI is 1.3. The FacMan-owned consumer
proof confirms that an interrupted install with no install reference still
projects:

- no fabricated install reference;
- dependent instance status `managed_install_recovery_required`;
- a stale launch plan;
- setup mutation owner `universal-setup`; and
- `launcher_can_mutate_setup = false`.

Focused exact-pin validation passed 6/6 tests. The complete proof passed 41/41
native tests, 339 Python cases plus one unchanged opt-in skip, strict and AIDE
validation, and the required Windows package profile at 14/14 with zero skips.

The complete selected package is byte-reproducible across 390 files:

| Evidence | SHA-256 |
| --- | --- |
| archive | `3a50263dde4871efc042d9289bef78b7abd6c364719b74ef18c91b8247c62fa8` |
| package tree | `c71458a16c201bf03fcd988795d44cc18564c63e7ef9c35b79dda108dcdaf470` |
| SBOM | `0f35b6be81e81fedcc2e12268c8192f752eca4f283d54856d604e3a916ffa722` |
| provenance | `0a5f36d9c637d20d9cb9139d94438a4d73efff27cc969f4b88829c7a15bd78c1` |

This is not a human setup verdict. It does not enable ordinary live apply,
accept a Factorio archive, authorize product execution, infer H1, or add
registry, elevation, network, signing, or publication authority.
