<!-- SPDX-FileCopyrightText: 2026 Jules C -->
<!-- SPDX-License-Identifier: MIT -->

# Changed files

The accepted implementation is the four-commit range
`cc4d79fec9d0b9790034fde0e698495dcf3b7407..c253e05d882c0822bb33da1ae92e7d047ee92f68`
with tree `023f24e8b380d1e44bc835a3ee56e9388cd47920`.

- `b1fd720`: binds final Universal provider pins, MIT identities, retained notices,
  SPDX/SBOM/provenance truth, operator decision, and project state.
- `71dacb2`: installs both provider license texts and requires them in all eleven
  package profiles.
- `724246e`: aligns runtime status and routing assertions with the licensed pins.
- `c253e05`: remediates the Windows long-path transaction defect discovered by
  the clean reconstruction and adds native regression coverage.

The range changes 44 tracked paths. All changes are within the reconciled
task scope; no command authority, network behavior, execution behavior,
registry behavior, signing, or publication path was added.
