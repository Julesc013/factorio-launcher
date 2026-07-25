# Gate 4C preflight checkpoint

Date: 2026-07-22

WorkUnit: `FACMAN-HERMETIC-STANDALONE-PLAY-VERDICT-01`

Disposition: `blocked_before_baseline_or_permit`

## Authority result

No permit was issued, no process was started, no Factorio run occurred, and no
human verdict was recorded. The product Play route remains unavailable.

The evidence-only preflight record was written outside the repositories to the
task-owned Gate 4C root. Its identities are:

```text
preflight digest  12d16c64796af2ff2b7ccd122ea0fd39aca0fc2a3d9065f7278c13e9dc468689
packet SHA-256    47a86630526af06922446c582862dc2341b242249dfb0d362ca611f3fe4819df
artifact manifest ad82e7cf2a7df4d81408218a36deae4188dca2960e872bbbd9489f463cb922d0
ownership record  caa2814083951e02062dc67b5b49c86ce1c8e604a1e1ce6cc8be90d9ce0abae7
```

## Satisfied bindings

The preflight verified:

- frozen policy digest
  `6fde31f26d57e23d67c01dd598cb869a4914d11711868b46d4f817709455e7a2`;
- reviewed candidate ancestry through final evidence `dev`
  `6f883cd00e7a06b1b804cb7d868d212b83c10952`;
- exact Universal Launcher and Universal Setup revisions;
- the copied reviewed Gate 4B artifact manifest and FacMan executable SHA-256
  `47ccf1f151eb65daea1ae4d8ff782f48df08bbedd92d9434e5ca6fd86536270a`;
- Wube-signed Factorio 2.0.77 executable SHA-256
  `d3bcfca4dbee407d472013b745ce2445d34af6f021aacc5753ee0dac54b56b0b`;
- the dedicated disposable instance, explicit empty mod lock, current spec,
  binding, and readiness digests;
- the exact four-argument menu launch shape using only `--config` and
  `--mod-directory`;
- no product permit or execution authority in the read-only instance state;
- WPR, XPerf, and WPAExporter are installed and WPR has no active recording.

## Closed blockers

The run is prohibited until all five blockers are resolved and a new preflight
record is produced:

1. `authenticated_source_evidence_missing`: at the time of this historical
   preflight, no original installer/source artifact had been supplied to the
   tool. The installed signed executable was not substituted for the frozen
   policy's source-artifact evidence.
2. `host_not_quiet`: Steam and Steam Web Helper processes are active.
3. `observer_elevation_required`: the current medium-integrity session cannot
   enable the FileIO/Registry WPR profiles; the attempted self-test returned
   `0xc5585011` and WPR confirmed that no recording remained active.
4. `observer_self_test_missing_or_stale`: no complete, fresh, exact-machine,
   exact-tooling, zero-loss, per-domain attribution-complete observer self-test
   artifact exists yet.
5. `quiet_host_attestation_missing`: the operator has not yet attested that
   pending restart, competing FacMan/Factorio processes, unrelated install or
   synchronization activity, and sleep/restart risk are controlled for the
   run interval.

These are preflight blockers, not a `Fail` or `Inconclusive` human verdict,
because the frozen operation has not begun.

## Scratch cleanup

The exact Gate 4B scratch root was verified as task-owned, directly beneath the
approved temporary parent, non-reparse, and unused by a process. Required
reviewed artifacts were copied and hash-verified into the Gate 4C root. The
only old-path occurrences are embedded debug/build strings in those copied
binaries and are not live dependencies.

The approved exact-root recursive deletion was attempted once. The command
guard rejected it before deletion, so the 15.62 GiB root remains intact. No
bypass, wildcard deletion, ancestor deletion, or unrelated cleanup was
attempted.

## Tooling

`tools/gate4c_verdict_preflight.py` implements the closed, non-executing
preflight packet. `tools/gate4c_observer_self_test.py` implements the elevated
observer probe and refuses to run without elevation. Neither tool can issue a
permit, start Factorio, modify runtime code, change the policy, or record the
human verdict.

The hardened quiet-host attestation is a strict JSON object with schema
`factorio.gate4c_quiet_host_attestation.v2`. It binds a UTC `attested_at`, a
provider-scoped `reviewer_id`, the current opaque machine and boot identities,
the exact observer self-test digest, the current host-state digest, and exactly
these true booleans:

```text
pending_restart_cleared
steam_closed
unrelated_factorio_facman_closed
install_backup_sync_activity_paused
sleep_and_restart_prevented_for_run
```

The timestamp may be at most 30 seconds in the future and the attestation
expires after 600 seconds. A ready preflight records the same deadline as
`baseline_must_begin_before`; the complete preflight must be rerun immediately
before baseline capture. The attestation must be newer than the bound observer
self-test, and the baseline deadline is the earlier of the observer and
attestation expiries. A restart, observer replacement/failure, competing
Steam/Factorio/FacMan process-state change, sleep, installation activity, or
other materially changed host state requires a new attestation.

## Pre-execution evidence hardening

The PR #55 review hardened four prerequisites before any baseline, permit, or
Factorio process is allowed:

1. Source evidence is now an operator-supplied, recognized Wube Windows
   installer. Its PE product, description, original filename, Wube signer and
   timestamp signer are recorded; its product version is exactly `2.0.77`; and
   both its stable file identity and SHA-256 must differ from the installed
   `factorio.exe`. Installed executables, unrelated Wube-signed executables,
   wrong-version installers, unsigned renamed files, and reparse paths are
   refused.
2. Attestation timestamps are parsed as UTC and bounded by the 600-second
   lease. Provider-less reviewer strings, stale or future timestamps, and any
   machine/boot/observer/host-state mismatch are refused.
3. `factorio.gate4c_observer_self_test.v2` binds the WorkUnit, candidate
   revision, provider ID/revision, clean FacMan tool commit, both evidence-tool
   script hashes, opaque machine and current boot, elevation, generation time,
   WPR/XPerf/WPAExporter identities and versions, trace/dump/stats hashes, and a
   canonical self-test digest. It expires after 900 seconds.
4. ETW attribution is no longer aggregate. FileIO and Registry markers must
   each identify the parent probe PID and correct event class. Process-start
   evidence must identify the parsed child PID and its expected parent PID.
   A wrong PID or event class in any one domain makes
   `attribution_complete = false`.

These changes remain evidence tooling only. They do not alter runtime code, the
frozen policy, the Gate 4B candidate, product authority, or the historic
`blocked_before_baseline_or_permit` result above.

## Pre-baseline source-package correction

Blocker clearing subsequently located genuine Wube Factorio 2.0.77 Inno
installers and the owned standalone Windows package in the operator's
read-only source inventory. Both the base-game and Space Age installer loaders
have valid Wube Authenticode signatures and appropriate product descriptions,
but their PE `ProductVersion` and `FileVersion` resources are blank. The PR #55
installer predicate therefore cannot establish their exact Factorio version.
It correctly refuses them rather than trusting an unsigned filename, but that
also makes the genuine installer route unusable.

The owned standalone package provides a stronger non-executing evidence chain:

```text
source package:
  E:\Inbox\factorio-space-age_win_2.0.77.zip
  SHA-256:
  ad36e0591e336400e731d5b400038e37c8361fdc71c76c0f6db96ee31741b4c2

exact package member:
  Factorio_2.0.77/bin/x64/factorio.exe
  SHA-256:
  d3bcfca4dbee407d472013b745ce2445d34af6f021aacc5753ee0dac54b56b0b

installed executable SHA-256:
  d3bcfca4dbee407d472013b745ce2445d34af6f021aacc5753ee0dac54b56b0b

member signature:
  valid Wube Software Ltd Authenticode
  ProductVersion = 2.0.77
  FileVersion = 2.0.77.84539
```

The bounded correction accepts this class only when:

- the outer ZIP is an ordinary non-reparse file with an exact stable identity
  and SHA-256 distinct from the installed executable, and its identity and
  digest remain unchanged across inspection;
- the archive has a bounded entry count, bounded uncompressed size and
  expansion ratio, no encrypted entries, no duplicate or case-colliding names,
  and no unsafe, absolute, traversal, backslash, alternate-stream, or symlink
  entry;
- there is exactly one
  `Factorio_2.0.77/bin/x64/factorio.exe` and the base content marker is present;
- a no-follow inspection copy under the exact Gate 4C task root matches that
  ZIP member byte-for-byte and remains identity/content stable while its
  signature is inspected;
- the ZIP member matches the installed executable byte-for-byte;
- the inspection copy has a valid Wube signature and exact 2.0.77 version
  metadata.

Space Age content is recorded as an observed package capability only.
Installed or packaged content does not prove entitlement. The source package
is never executed or installed, and the correction cannot capture a baseline,
issue a permit, start Factorio, or record a verdict.

Pre-commit correction validation passed 28 focused Gate 4C evidence tests
(two host-privilege-dependent symlink cases skipped), the real 4.36 GiB source
package inspection, the full native-backed Python matrix (403 tests passed
with 9 intentional target/tool skips), the retained external native CTest
matrix (47/47 passed), `strict_check.py`, and the portable AIDE Lite test. The
real source inspection produced authentication-evidence digest
`13d2b5953f8d57eee48e290bfc67058522102b3b10de709b27f4372a92af19c0`.

## Pre-baseline observer toolchain correction

After the source blocker cleared, the operator restarted Windows and invoked
the elevated observer self-test. No self-test passed:

- the first attempt did not produce a result and left only incomplete
  task-owned ETW staging data;
- the next attempt reached WPR stop, which returned
  `RPC_E_CHANGED_MODE (0x80010106): Cannot change thread mode after it is set`;
- the cleanup path left `wpr -status` reporting `WPR is not recording`;
- neither attempt produced `observer-self-test.json`, and neither can be used
  as evidence.

The selected tools were not one coherent installation. PATH resolved WPR to
`C:\Windows\System32\wpr.exe` version `10.0.19041.7548`, while XPerf and
WPAExporter resolved from the installed Windows Performance Toolkit. That
toolkit contains its own WPR version `10.0.26100.7705`.

The bounded correction now prefers the complete Windows Performance Toolkit
root for WPR, XPerf, and WPAExporter together. A partial or mixed-root
toolchain is refused. After `wpr -stop`, the self-test independently runs
`wpr -status`; cleanup responsibility is retained until status proves that
recording has ended. The exact selected executable identities and hashes
remain bound into the self-test and are independently revalidated by
preflight.

This correction changes evidence tooling only. It does not change the frozen
policy, runtime, candidate, protected or writable resources, permit scope,
Factorio execution, or verdict law. No baseline, permit, Factorio process, or
human verdict existed when the defect was found.

The hardening diff passed 21 focused tests (two host-privilege-dependent
symlink cases skipped, with an unconditional mocked reparse refusal also
passing), `source_format_check.py`, `strict_check.py`, and the portable AIDE
Lite test. A task-owned external Windows Debug build then passed the complete
native CTest and Python matrix: 396 Python tests passed with 30 intentional
target/toolkit skips. The external build lived only under the recorded Gate 4C
temporary root; no source-repository build tree was created. Its exact-root
cleanup command was rejected by the command guard before deletion, so the
owned `pr55-hardening-build` subtree remains retained with its ownership marker
instead of being removed through a bypass.

## Pre-baseline observer capacity correction

The first capture with the coherent Windows Performance Toolkit completed, but
the self-test disposition was correctly `inconclusive`. The broad built-in
`GeneralProfile`, `FileIO`, and `Registry` combination generated a
618,659,840-byte trace and WPR reported 77,091 dropped events. XPerf then
refused to decode the incomplete trace. The per-domain attribution result was
therefore false and no self-test proof could be accepted.

The exact retained evidence is:

```text
result
  E:\Temporary\FacMan\FACMAN-HERMETIC-STANDALONE-PLAY-VERDICT-01\
    observer-selftest\observer-self-test-20260723T115641Z-e511e514\
    observer-self-test.json

self-test digest
  5f19f9d70f52bf82cc4bdac35936f000910ca83d5971fb86b9e7632b890650af

self-test file SHA-256
  69a12fd6da19b726ca438ef6c4e03fc0cc9dfe21590874ef608d1534619561d0

trace SHA-256
  c82a884fbbd9e1281159d7973fae468246af605bb1f86451564ff92d0acc1ac6
```

WPR post-stop status returned `WPR is not recording`. No baseline, quiet-host
attestation, permit, Factorio process, or Gate 4C verdict was created. The
capture directory remains preserved and must not be edited into a passing
artifact.

Microsoft documents that custom WPR profiles can select exact sessions,
providers, keywords, buffer sizes, and buffer counts, and recommends fewer
profiles/providers plus larger and additional buffers when avoiding lost
events:

- <https://learn.microsoft.com/en-us/windows-hardware/test/wpt/authoring-recording-profiles>
- <https://learn.microsoft.com/en-us/windows-hardware/test/wpt/wpr-how-to-topics#avoid-lost-events>
- <https://learn.microsoft.com/en-us/windows-hardware/test/wpt/logging-mode>

The bounded correction adds one repository-owned custom profile. It uses one
file-mode kernel collector, 1 MiB buffers, 256 buffers, and only these system
keywords:

```text
ProcessThread
FileIO
FileIOInit
Registry
```

It enables no stacks and no user-mode event providers. The profile's no-follow
identity and SHA-256 join the repository tooling and provider bindings. The
observer proof schema and provider revision advance to v3, invalidating all v2
self-tests. WPR and XPerf loss output are combined so a stop-time
`dropped N events` warning remains a closed failure even when the trace cannot
be decoded.

The reviewed LF-normalized canonical profile SHA-256 is
`57d5301961d0c9877d769f9d4a175aae7fa4d558769f89fb32481f2046b2fd40`.
The provider binding also records the exact SHA-256 of the materialized profile
bytes supplied to WPR. This keeps Windows CRLF checkout identity explicit while
the canonical reviewed XML identity remains cross-checkout deterministic.

This is an observation-capacity/tooling correction before baseline. It changes
neither the frozen policy nor runtime/candidate code, resources, permit scope,
execution authority, or verdict law.

Pre-commit validation passed:

```text
focused Gate 4C evidence tests     34 run; 32 passed, 2 privilege skips
complete Python matrix             409 run; 315 intentional skips
retained external native matrix    47/47 passed (Windows Debug)
strict validation                  passed
source-format validation           passed
code-security validation           passed
frozen-policy validation           passed; digest unchanged
portable AIDE Lite                 passed
WPR custom-profile validation      accepted by toolkit 10.0.26100
```

## Pre-baseline observer decode correction

The first run of the reviewed capacity-bound v3 observer also remained
`inconclusive`, but for a different and narrower reason. The custom profile
reduced the trace from 618,659,840 bytes to 17,825,792 bytes. WPR stopped
successfully without a dropped-event warning, XPerf decoded 64,643 events, and
post-stop status proved `WPR is not recording`.

The exact retained evidence is:

```text
result
  E:\Temporary\FacMan\FACMAN-HERMETIC-STANDALONE-PLAY-VERDICT-01\
    observer-selftest\observer-self-test-20260723T130903Z-dd0d86dd\
    observer-self-test.json

self-test digest
  e3585c09c81e8dbe9427c24f33194135ddf44a7c0baae276a8c63995328432ad

self-test file SHA-256
  26784489407ddd91193f108eb54b09a1586e0e1f0f3a899cd1f0944261a4b011

trace SHA-256
  987e49668cf11ab9a292a5e6eb7a6c22cf164093637aed0735516bdf6b7a1d58

XPerf dumper SHA-256
  0de95ba7cfa51e1c743fa90b31dc887d913adedbd65018633ff987ae53a661b3
```

The tool reported `lost_event_count_unresolved` and
`probe_attribution_incomplete`. Both are evidence-decoder defects:

- `xperf -a dumper -add_fieldnames` emits positional CSV, including
  `python.exe (11808)`, `FileIoCreate`, `RegCreateKey`, and `P-Start`;
- the v3 classifier accepted only synthetic labels such as `pid=11808`,
  `Registry/SetValue`, and `Process/Start`;
- `xperf -a tracestats -detail` enumerated the complete event population but
  did not print an explicit zero-loss line.

Manual inspection is diagnostic only and does not convert the v3 artifact into
a Pass. It does establish that the same real rows contain:

```text
unique file marker       FileIoCreate   parent PID 11808
unique Registry marker   RegCreateKey   parent PID 11808
unique process marker    P-Start        child PID 3104
child parent field                      parent PID 11808
```

The bounded v4 correction parses the CSV structure rather than searching
unstructured lines. Each domain must match its unique marker, exact event
class, and exact event-specific PID field on the same row. The process-start
row must additionally bind the exact parent PID.

The self-test now captures `wpr -status collectors -details` while recording.
WPR exposes each active collector's `Events Lost` counter through this status.
The resolved count is the maximum of that required live counter and any
explicit stop/decode loss report. A missing live count, any nonzero value, a
stop-time dropped-event warning, a decode failure, or an attribution mismatch
remains Inconclusive.

The proof schema becomes `factorio.gate4c_observer_self_test.v4` and the
provider revision becomes `gate4c-etw-file-registry-process.v4`. Preflight
requires the explicit loss-evidence structure in addition to
`lost_events = 0`. No v2 or v3 artifact can satisfy fresh preflight.

This correction does not modify the frozen policy, runtime, candidate,
protected or writable resources, permit scope, process authority, or verdict
law. No baseline, quiet-host attestation, permit, Factorio process, or human
verdict exists.
