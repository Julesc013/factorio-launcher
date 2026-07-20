<!-- SPDX-FileCopyrightText: 2026 Jules C -->
<!-- SPDX-License-Identifier: MIT -->

# Changed files

- provider locks, notices, SBOM, and runtime diagnostics pin Universal Setup
  canonical M2-WU4 main;
- canonical/generated project state records the retained live run without
  promoting the pending human verdict;
- the WU4 checkpoint binds exact provider, run, packet, journal, audit, state,
  and ownership identities;
- validators and tests preserve historical WU3 identity while requiring WU4
  to match the current provider pin and authority boundary.
