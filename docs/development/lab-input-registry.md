# Laboratory scenario and input custody

`release/index/lab_input_registry.v1.json` registers the existing J01-J12
journey census and14 cross-frontend fixtures for Windows x64, Linux x64 and
macOS Intel x64. It is development planning data, excluded from product
runtime authority. A registered cell is an obligation, never a passing result.

Run the read-only checks from the checkout:

```powershell
python tools/lab_input_registry.py check
python tools/lab_input_registry.py matrix
python tools/lab_input_registry.py inspect-input --input <absolute-file> --sha256 <approved-sha256>
python tools/lab_run_custody.py <run-custody.json>
```

The123 cells keep three evidence classes separate: machine fixtures, actual
Factorio readiness/Play/recovery, and human experience. Fifty-two Windows/WSL
fixture cells have available inventory for preparation. The other71 carry
explicit external blockers. Every cell still needs its own source/package,
fresh host, owned roots, allowed effects, reset/export, input and independent
outcome receipts. These counts describe registry obligations and availability;
they do not count completed tests or replace the deeper journey test matrix.

## Observed hosts and missing inputs

The current registry binds the retained 4 October read-only observation of
Windows10 build19045 on BLACKGLASS-WIN1 and Ubuntu24.04 under WSL2
kernel6.18.40.1. The earlier BlackGlass-Win10 observation remains historical.
This observation is separate from the Windows account/domain used for GitHub.
WSL's default uid0 cannot qualify permission refusals; those fixtures use the
existing uid/gid65534 without supplementary groups. Create fresh marker-owned
ext4 roots, preserve run failures, and export evidence before the temporary
root disappears. WSL observations do not qualify a physical desktop, Wayland,
GPU, every filesystem or human accessibility.

No persistent disposable macOS Intel laboratory host has been identified.
Hosted compile/package jobs remain useful, but bind only their own exact run.
The package maintainer/operator must register that host's identity, permitted
roots/effects and reset/export policy before claiming a laboratory result.

Windows x64 Factorio 2.0.77 input custody is registered from the user-supplied
`D:\Games\Factorio\2.0` installation. Two complete read-only captures matched:
19,742 files, 2,212 directories and 5,052,185,219 file bytes. Each retained private
manifest is 11,209,258 bytes with raw SHA256
`18a6400065167235f085e82902daa5a5828ac65006cfafb1f3cb2dd2fe8f9656`.
The registered digest identifies those exact manifest bytes; its rows contain
each file's content SHA256, size, identity and mtime, plus directory observations.
It is not an official archive digest, executable digest, canonical tree-root
digest or authenticated Wube source claim. The compact custody observation and
independent review are retained beside the registry's five-field approval record
in the active LAB WorkUnit evidence. The full manifests and game bytes remain
private external evidence.

The issuer is `Codex /root; independent input-custody review`, a maintainer/model
review of actual stable captures. The user supplied an input location and did
not attest a digest. The executable's separate raw SHA256 is
`d3bcfca4dbee407d472013b745ce2445d34af6f021aacc5753ee0dac54b56b0b`.
Revalidate the complete selected input before effects; capture supplies no
continuing filesystem lease. Windows input custody cannot qualify Linux or
macOS bytes, whose input records remain unavailable.

Custody registration grants no host qualification, source authentication, game
route permit or execution. Windows host capabilities remain machine-fixture
only, so the matrix retains 123 obligations, 52 preparation-available fixture
cells and 71 blocked cells. The six Windows Play/readiness/recovery input
blockers disappear while host and human blockers remain. Human experience
requires an actual person's candidate-bound observation. Workspace-only human
scenarios do not depend on game input. The fixture-only run inspector and the
product's separate real-Play readiness gate retain their authority boundaries.

## Concrete run record

The `facman.lab-run-custody.v1` record contains `scenario_id`, the canonical
JSON `registry_sha256`, declared `source_commit` and `source_tree`, the exact
`task_root` and `marker_sha256`, disjoint absolute `roots.state` and
`roots.export`, and `candidate`/`input` objects with absolute `path` and raw
`sha256`. The fixture input must also equal the registered corpus's semantic
identity. The task root must pass the existing FacMan development-marker
reader against this repository and its canonical configured task path.

The permitted fixture `effects` list is exactly `owned_fixture_files`,
`injected_or_fake_process`, `evidence_export`. `reset` is
`retain_then_marker_owned_cleanup`; `export` is `hash_and_archive_before_reset`.
These fields describe the proposed run; the inspector creates no directories,
dispatches no candidate/game/setup process, copies no input, resets nothing
and deletes nothing. Existing marker rules use read-only Git identity queries.
Current run inspection supports the available machine-fixture cells only.

The result binds actual content bytes and rejects missing/changed markers,
escaped or overlapping roots, substituted fixtures and broader effects.
It reports declared source identities separately: the package pipeline must
prove actual package provenance. Fresh host verification and the real effect
owner's admission remain required. Raw and semantic input identities, approval records and ownership markers are
validated from the same bounded read snapshots. Dangling linked ancestors are
refused even when their targets no longer exist. Input inspection is a point-in-time read;
revalidate before effects, because it does not hold a filesystem lease.

## Drift, validation and integration

Semantic JSON/TOML pins bind the canonical scenario sources and retained host
observation. Whitespace/line endings alone do not invalidate them; changed
scenarios, host identities, platform approvals or missing custody do. Actual
input SHA256 remains a raw-byte comparison. Do not rewrite old run evidence
when a source, package, host, input or effect policy changes; obtain new receipts.

The registry participates in full strict checks and impacted Python tests.
Behavioral tests cover complete coverage, external blockers, host/input
substitution, raw-byte drift, real CLI invocation, owned-root refusal and
unchanged filesystem snapshots on acceptance/refusal. The initial CLI import
failure is retained alongside the corrected tests. Registry validation is not
Beta1 qualification or publication approval.
