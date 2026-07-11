# Changelog

## 0.1.0 - Unreleased

- Bootstrap repository structure for a Factorio product binding.
- Add CLI-first Python package scaffold.
- Add read-only product inspection, doctor, install discovery/import, isolated
  instance creation, and dry-run launch-plan generation.
- Add bounded read-only Windows Steam and standalone discovery with deterministic
  de-duplication, foreign-ownership classification, and reparse-point refusal.
- Add schemas, policy templates, docs, tests, and GitHub setup inputs.
- Consolidate the runtime into generated metadata, shared JSON/result/identity
  and platform primitives, repositories, typed transactions, decomposed
  handlers, and a client-only CLI.
- Build packages only from the CMake install tree with deterministic archives,
  dirty-source refusal, component/hash manifests, complete SPDX SBOM closure,
  and unsigned provenance.
- Add affected/full test routing, warnings-as-errors, ABI checks, fuzz and
  sanitizer target lanes, advisory benchmarks, and compact AIDE lifecycle
  history.
- Add SPDX/REUSE metadata, exact vendored dependency notices, vulnerability and
  supported-version policy, while preserving provider licenses as
  `NOASSERTION` pending an operator decision.
