# Observer-start diagnostic slice

## Purpose

The first correction slice makes the previously hidden observer-start result
inspectable without launching Factorio or issuing a permit.

It adds:

- exact propagation of the observer provider's structured start error;
- a regression proving observer-start failure occurs before permit consumption
  and process creation;
- an elevated Windows probe that exercises the exact reviewed WPR profile
  without Factorio;
- exact command, exit-code, stdout, stderr, process identity, job-context,
  cleanup-state, and artifact evidence; and
- append-only probe outputs under the exact repair task root.

## Boundary

The probe cannot:

- construct or issue an operation permit;
- call the candidate process supervisor for Factorio;
- launch Factorio;
- modify the frozen policy;
- record a Gate 4C human verdict; or
- promote product Play or any other authority.

The underlying observer-start root cause is deliberately not inferred from the
two earlier generic refusals. It will be established from a fresh elevated
direct-versus-native-supervised probe after this diagnostic slice is committed
and the repository is clean.

## Pre-probe validation

- focused Gate 4C verdict-evidence Python tests: 8 passed;
- observer error propagation and canonical harness native tests: 2 passed;
- source format: passed; and
- diff whitespace validation: passed.
