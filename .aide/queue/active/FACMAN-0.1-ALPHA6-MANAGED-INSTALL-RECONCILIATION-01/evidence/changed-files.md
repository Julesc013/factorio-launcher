# Managed repair planning slice — changed-file classification

Base source: `dev@17df4e68959e4d7a5ba2c77f9e28c0f5fa67fd28`

- `runtime/factorio/application/**` moves `installs.repair.plan` from the
  generic setup refusal route to the installation application module and keeps
  the existing command identity.
- `runtime/factorio/installation/**` lets the existing reconciliation serializer
  emit the invoking command identity, binds lifecycle status into current
  evidence and treats selected source evidence as requiring inspection only
  for explicit repair intent. Ordinary reconcile source-only behavior remains
  unchanged.
- `contracts/**`, generated runtime/frontend catalogs, CLI completions and
  `docs/reference/generated-command-catalog.md` record the implemented,
  read-only contract and optional archive syntax.
- `tests/test_cli.py` and the repair success/refusal goldens cover managed
  success, selected-unverified source blocking, no-write behavior, command
  identity, compatibility with reconcile planning, lifecycle admission,
  malformed CLI options and refusal cases.
- `tools/codegen/generate_metadata.py` and its focused test retain optional
  `--archive <path>` in the structured CLI grammar.
- `tools/alpha_vertical_slice_check.py` and `tools/setup_workflow_check.py`
  preserve the narrow source-truth assertions affected by the new route.
- Canonical plan, generated roadmap/TODO/project-state files and AIDE queue
  records activate this existing WorkUnit without closing it or changing the
  product version.

No SetupGateway repair API, apply implementation, filesystem mutation, package
publication, game execution or human-verdict artifact is introduced.

The active task allowed-path record names the metadata generator explicitly;
the amendment grants no general `tools/**` scope.
