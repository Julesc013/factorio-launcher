# Side-by-side self-maintenance source checkpoint

This checkpoint implements the bounded source layer for explicit FacMan
update, downgrade, and rollback. It does not close WorkUnit acceptance.

The transition derives a full-digest sibling candidate root and a distinct
`facman.self.generation.<digest>` install ID from product version, complete
package SHA-256, FacMan revision, pinned Universal Setup revision, layout,
protocol, and entrypoint identities. Its provider boundary exposes
`install_local` only. Candidate inspection and verification must both return
exact receipt identities before shell cutover can begin.

The global lock is `%LOCALAPPDATA%/FacMan/setup-coordinator.v1/setup-operations/
facman.self.lock` for legacy setup and side-by-side transitions. Generation,
phase, and activation records are no-replace immutable files. The activation
scanner rejects changed predecessors, missing links, forks, cycles, multiple
heads, and a caller-selected stale head.

The Windows shortcut adapter recognizes exact old and new targets and retains
an operation-bound same-directory backup across publication. Registration
cutover is transactional. The handoff primitive hashes the external helper and
journal while holding no-write, no-delete-sharing handles across process
creation. It creates the helper suspended, revalidates both paths before any
child code can execute, terminates while suspended on refusal, and only then
resumes the admitted primary thread. It uses
`PROC_THREAD_ATTRIBUTE_HANDLE_LIST` and passes only a limited inherited process
handle. The helper validates PID plus process creation time and spends the
remaining portion of one absolute monotonic deadline.

Post-create cleanup is explicit: only successful termination followed by
`WAIT_OBJECT_0` is a confirmed closed refusal. Failure to request termination
or to confirm exit within the nonzero bounded cleanup allowance returns cleanup
outcome unknown together with the spawned PID. The negative native fixture
forces a post-create refusal, observes that no child marker ran, and requires
either confirmed exit or that explicit unresolved result.

Focused validation uses the existing marker-owned external task root. Native
tests cover preview, version direction, provider outcome loss without replay,
candidate verification before shell effects, global lock contention, missing
rollback generations, exact absolute rollback paths, malformed and cyclic
activation history, duplicate-genesis, generation-link and inactive-generation
refusal, phase semantics, shortcut backup recovery, inherited-handle timeout
and identity substitution, plus the existing repair/native recovery
regressions.

Strict SemVer parsing applies to every source and target generation, including
complete build-metadata validation and numeric-prerelease rules. A product
version must also be one safe path component. Runtime and schema regressions
cover rollback source and target traversal, malformed build metadata, and a
valid dotted build identity.

Still required: public setup verb routing, a production adapter between the
transition and pinned USK `install_local`, legacy activation migration,
multi-generation repair/removal and retention, a complete external helper
parent-exit/resume candidate run, and update/downgrade qualification using two
clean source-distinct packages on a disposable current-user Windows host.

## Local validation on the changed source

The existing marker-owned
`task-facman-s-7c8b05c46e/native-developer` build root was reused. Its cached
Universal Setup source was updated to the already owned, currently pinned
`4c766b342e68656a2d4e26a14cfe51ab2209ad41` checkout under
`managed-install-repair-01`; no task root or worktree was created.

- Debug build of `facman_self_maintenance_smoke`,
  `facman_windows_maintenance_handoff_smoke`, and
  `facman_windows_integration_ownership_smoke`: passed.
- Debug CTest selection including those three tests and the pre-existing
  `facman_self_setup_recovery_smoke`: 4/4 passed.
- Release build and CTest selection for the three changed-source targets: 3/3
  passed. The Release `facman_setup` executable also linked successfully.
- `python -m unittest tests.test_self_setup_package
  tests.test_alpha3_distribution`: 12/12 passed.
- Schema validation: passed with 432 schemas. Source formatting, security,
  component ownership, and portable AIDE Lite validation passed.
- A 40-test adjacent Python selection passed 39 tests. Its sole failure was
  the already stale generated command/version catalogs; this slice preserved
  those generated reports as required and did not rewrite them.
- After the reviewed package/schema corrections, the final adjacent Python
  selection passed 42/42 tests. This is the current result; the earlier 39/40
  observation remains above as failure history.
- Final review-remediation reruns passed Debug focused native 4/4 and Release
  focused native 3/3. Schema validation passed for 432 schemas; source format,
  component ownership, code security, security policy, and portable AIDE Lite
  all passed.
- A subsequent re-review added strict source/target SemVer and safe-component
  checks plus suspended helper admission. The affected Debug and Release tests
  passed 2/2 in each configuration, and the complete current Debug native suite
  passed 47/47. The unchanged adjacent selection remained 42/42 after its
  schema-negative cases were extended.
- Cleanup-accounting remediation passed the affected handoff test in Debug and
  Release (1/1 each). It preserves the prior complete Debug 47/47 result while
  binding the additional rerun to the changed handoff source.
- Canonical project-state and metadata regeneration refreshed the stale
  project-state, README, roadmap, current-state, WinForms catalog, and native
  version projections. The final full strict check passed with 131 commands,
  432 schemas, and 290 refusal codes.
- Independent non-authoring review returned `PASS` after all recorded findings
  and their regressions were remediated.
