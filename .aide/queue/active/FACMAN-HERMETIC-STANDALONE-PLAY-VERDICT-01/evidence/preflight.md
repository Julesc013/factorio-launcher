# Gate 4C preflight

The first exact-candidate preflight completed without issuing a permit or
starting a process. The detailed checkpoint is
`docs/quality/evidence/gate4c/gate4c-preflight-2026-07-22.md`.

Disposition: `blocked_before_baseline_or_permit`.

Open prerequisites:

- provide the exact Wube-authenticated source artifact;
- close Steam and Steam Web Helper for the quiet interval;
- run the ETW observer self-test from an elevated operator prompt;
- bind a complete, zero-loss observer self-test artifact into a fresh
  preflight;
- provide the strict quiet-host operator attestation immediately before
  baseline capture.

The draft tooling checkpoint now fails closed on four reviewed evidence laws:

- the source must be a recognized operator-supplied installer whose stable
  identity and SHA-256 differ from the installed executable;
- the provider-scoped quiet-host attestation is UTC parsed, machine/boot/host
  bound, and expires after 10 minutes;
- the observer self-test is exact-machine, exact-boot, exact-tooling, exact-tool
  and artifact-hash bound, and expires after 15 minutes;
- FileIO, Registry, and process-start probes must each match their own expected
  PID and ETW event class, including the child-to-parent process relationship.

An expired ready record cannot authorize baseline capture. The complete
preflight must be rerun immediately before the baseline, within the attestation
lease. Any restart, Steam/Factorio/FacMan process-state change, observer/tool
change, sleep, or materially changed host state invalidates the evidence.

Pre-commit hardening validation passed the focused evidence-tool tests, strict
repository checks, AIDE Lite, and a complete external Windows native/Python
matrix (396 Python tests passed; 30 intentional skips). The task-owned build
tree was kept outside the repository. Its exact-root cleanup was rejected by
the command guard before mutation, so it remains retained and explicitly owned;
no deletion workaround was attempted.

This is not a human `Pass`, `Fail`, or `Inconclusive` verdict. Gate 4C remains
active and product Play remains unavailable.

## Source-package correction before baseline

Blocker clearing found genuine Wube 2.0.77 Inno installers, but their signed
loader executables contain blank PE product/file version resources. Trusting
their filenames would weaken the merged predicate, so they remain unverified.

The owned standalone ZIP package contains one exact Wube-signed Factorio
2.0.77 executable. Its member SHA-256 equals the selected installed executable
SHA-256, while the outer package has its own distinct stable identity and
digest. The bounded correction branch adds static, no-follow, size-limited ZIP
inspection and binds a task-owned inspection copy to the archive member and
installed executable.

This correction was opened before baseline capture. The historic blocked
packet remains unchanged. No permit was issued, no Factorio process started,
and the verdict remains unset.

## Observer toolchain correction before baseline

Two elevated self-test attempts after the required restart failed before
producing a self-test record. The second attempt reached WPR stop and returned
`RPC_E_CHANGED_MODE (0x80010106)`. WPR cleanup left no active recording, but
the attempt remains incomplete and cannot satisfy preflight.

Inspection found that PATH selected the inbox Windows WPR `10.0.19041.7548`
while XPerf and WPAExporter came from the installed Windows Performance
Toolkit. The complete toolkit also contains WPR `10.0.26100.7705`. The bounded
correction therefore selects all three observer tools from that one exact
toolkit root and refuses mixed-root toolchains. It also rechecks WPR status
after stop and retains cleanup responsibility until WPR proves that recording
has ended.

This remains a pre-baseline evidence-tool correction. The incomplete ETW
attempt directories are preserved, no baseline has been captured, no permit
has been issued, no Factorio process has started, and the verdict remains
unset.

## Observer capacity correction before baseline

The first self-test using the corrected coherent toolkit completed WPR stop
and produced a hash-closed self-test record, but it correctly returned
`inconclusive`. WPR reported 77,091 dropped events; XPerf refused to decode the
incomplete 618,659,840-byte trace, so file, Registry, and process attribution
could not be established. WPR post-stop status proved that no recording
remained active.

The preserved result is:

```text
self-test digest
  5f19f9d70f52bf82cc4bdac35936f000910ca83d5971fb86b9e7632b890650af

self-test file SHA-256
  69a12fd6da19b726ca438ef6c4e03fc0cc9dfe21590874ef608d1534619561d0

trace SHA-256
  c82a884fbbd9e1281159d7973fae468246af605bb1f86451564ff92d0acc1ac6
```

The observer had combined the broad built-in `GeneralProfile`, `FileIO`, and
`Registry` profiles. The bounded correction replaces those profiles with one
repository-owned WPRP whose only system keywords are `ProcessThread`,
`FileIO`, `FileIOInit`, and `Registry`. The file-mode collector uses 1 MiB
buffers and 256 buffers, enables no stacks and no user-mode event providers,
and is hash-bound into the provider/tool identity. The observer schema and
provider revision advance to v3 so no v2 proof can satisfy fresh preflight.
Loss parsing also covers WPR's `dropped N events` stop message instead of
depending solely on a decodable XPerf statistics report.

The reviewed LF-normalized canonical profile SHA-256 is
`57d5301961d0c9877d769f9d4a175aae7fa4d558769f89fb32481f2046b2fd40`.
Each self-test additionally binds the SHA-256 of the exact materialized bytes
passed to WPR, so Windows CRLF checkout identity remains explicit without
changing the reviewed XML contract.

This correction follows Microsoft's documented lost-event controls: use fewer
profiles/providers, larger buffers, and more buffers. It does not ignore,
waive, or reinterpret the retained loss. The failed capture remains
observer-self-test evidence only, not the human Gate 4C verdict. No baseline,
attestation, permit, Factorio process, or verdict exists.

Pre-commit correction validation ran 34 focused Gate 4C evidence tests
(32 passed; two host-privilege-dependent symlink cases skipped) and the
complete 409-test Python matrix (315 intentional platform/tool skips). It also
passed the retained external Windows Debug
native matrix (47/47), strict/source-format/code-security/policy validation,
the WPR profile parser, and the complete portable AIDE Lite test.
