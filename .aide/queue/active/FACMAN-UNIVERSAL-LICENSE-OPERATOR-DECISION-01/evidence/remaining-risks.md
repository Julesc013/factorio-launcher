<!-- SPDX-FileCopyrightText: 2026 Jules C -->
<!-- SPDX-License-Identifier: MIT -->

# Remaining risks and boundaries

- Artifacts remain unsigned and unpublished; package integrity and provenance
  do not prove publisher authenticity.
- No live-target setup authority, Factorio archive acceptance, `run.execute`,
  H1 Pass, Steam mutation, registry mutation, elevation, network behavior, or
  credential storage is inferred.
- The Windows adapter retains already device-prefixed paths. Higher-level
  target classification must continue to refuse device and otherwise unowned
  targets before native I/O.
- M2 still requires a separate human Pass, Fail, or Inconclusive verdict before
  ordinary live-target apply can be promoted.
