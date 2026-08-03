# Changed files

- WinForms transport implementation:
  `BoundedByteChannel.cs`, `CliProcessClient.cs`, `CommandModels.cs`,
  `StrictTransportJson.cs`, `TransportOptions.cs`,
  `TransportResponseDecoder.cs`, and `WindowsContainedProcess.cs`.
- WinForms project, shell documentation, machine-transport architecture, and
  focused source/truth validators.
- Executable fake-backend and behavior harness under
  `tests/winforms_transport_harness/`, its Python entrypoint, unit wrapper, and
  Windows hosted-CI step.
- Canonical plan/status/current-state, generated AIDE projections, bounded
  WorkUnit queue/evidence records, roadmap/readiness surfaces, and their tests.
- Two qualification repairs: current-truth compaction expectations and
  platform scoping for the discovery-smoke environment helper.
- One deterministic smoke repair: explicit evidence mode before fixture-only
  WinForms rendering assertions.

No provider checkout, provider pin, workspace lock, historical evidence,
Factorio policy contract, backend-selection policy, or workspace-root policy
was changed.
