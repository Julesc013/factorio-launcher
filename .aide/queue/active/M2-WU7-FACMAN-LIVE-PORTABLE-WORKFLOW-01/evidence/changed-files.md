<!-- SPDX-FileCopyrightText: 2026 Jules C -->
<!-- SPDX-License-Identifier: MIT -->

# Changed Files

- Routed the Factorio portable recipe through Universal Setup's public
  `install_local.plan` descriptor.
- Added explicit candidate planning configuration and fail-closed partial or
  unsupported activation handling.
- Replaced pre-M2 apply wording with the exact pending human-verdict refusal.
- Added native and CLI plan/no-write proof, success/refusal goldens, regenerated
  command surfaces, checkpoint, claim ledger, and project state.

No apply handler invokes a provider mutation command.
