<!-- SPDX-FileCopyrightText: 2026 Jules C -->
<!-- SPDX-License-Identifier: MIT -->

# M2-WU6 Universal Launcher Live Setup Handoff

Status: provider integrated and focused local consumer proof passed; complete
validation and `dev` integration pending; human verdict `pending`.

This checkpoint binds Universal Launcher task `43115d50822ac5a3ab0c51801873ff9a230408dd`
and canonical main `7bd4425f0c35414f738159b45d8bec42edf70235`, whose exact-main CI run
`29337737777` passed.

The additive Launcher and FacMan binding ABI is 1.3. The FacMan-owned consumer
proof confirms that an interrupted install with no install reference still
projects:

- no fabricated install reference;
- dependent instance status `managed_install_recovery_required`;
- a stale launch plan;
- setup mutation owner `universal-setup`; and
- `launcher_can_mutate_setup = false`.

Focused exact-pin validation passed 6/6 tests, including installed SDK and ABI
compatibility coverage. Complete repository/package proof is still required.

This is not a human setup verdict. It does not enable ordinary live apply,
accept a Factorio archive, authorize product execution, infer H1, or add
registry, elevation, network, signing, or publication authority.
