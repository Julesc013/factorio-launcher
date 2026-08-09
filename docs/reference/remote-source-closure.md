# Remote Source Closure

`tools/remote_source_closure.py` proves that the locked three-repository source
set can be reconstructed and qualified without borrowing a developer's local
Git object database or build outputs.

This is an explicit network and promotion proof. Ordinary local development
continues to use the offline checks in `tools/workspace_config.py doctor` and
`tools/verify_dependency_revisions.py`.

## Preconditions

- The exact FacMan proof commit has been pushed to an HTTPS remote branch.
- The FacMan workspace lock names full lowercase provider pins, HTTPS remotes,
  canonical `refs/heads/*` refs, and
  `reachability = "required_for_source_closure"`.
- The selected clone and build roots are absent or empty.
- The report path does not already exist; the proof never overwrites prior
  evidence or an operator-owned file.
- Git, CMake, a supported x64 native toolchain, and Python are available.

## Run the proof

From a FacMan checkout:

```powershell
py -3 tools/remote_source_closure.py `
  --factorio-pin <published-40-character-commit> `
  --factorio-ref refs/heads/<published-proof-branch> `
  --report docs/quality/evidence/source-closure/remote-source-closure.v1.json
```

For the successor Play source-closure WorkUnit, add the read-only standalone
archive observation:

```powershell
py -3 tools/remote_source_closure.py `
  --factorio-pin <published-task-head> `
  --factorio-ref refs/heads/task/facman-successor-play-source-closure-01 `
  --successor-route `
  --factorio-archive <factorio-2.0.77-standalone.zip> `
  --report <out-of-tree>/successor-source-closure.v1.json
```

The successor projection resolves the sole current new-evidence target through
`release/index/successor_play_route.index.v1.toml`. It requires immutable route
v2, its reconciled canonical providers, and the reserved
`facman.successor-play.source-closure.02` identity. Route v1 remains a validated
historical record, but new `.01` evidence and mixed v1/v2 chains are refused.
The source-closure form also requires all three mutable admission gates in the
route index to be true: new-evidence execution, source-closure execution, and
the active route row's new-source-closure-evidence flag. The checked-in index
currently keeps them false. Until a separate reviewed authority transition
opens those gates, the command fails before provider cloning, archive hashing,
building, or report creation.

The archive is opened read-only. The proof hashes the archive and its unique
`Factorio_2.0.77/bin/x64/factorio.exe` member; it never extracts or executes
Factorio. Lookalike paths, non-regular or encrypted members, oversized inputs,
and excessive executable compression ratios are refused. A task ref produces
a visibly non-canonical
`task_ref_reconstruction_passed` rehearsal. Only an exact `main` or `dev` head
can set `canonical_gate_satisfied = true`.

The default clone root is a newly allocated temporary directory. Use
`--clone-root` and `--build-root` only with empty task-owned directories.
`--keep-clones` retains an automatically allocated clone root for diagnosis.
Although every Git call enables `core.longpaths`, Windows hosts can impose a
materialized-path ceiling outside Git. Prefer a short proof root on Windows. A
partial checkout is never accepted: the clean-worktree gate refuses it.

## What is proven

For FacMan, Universal Launcher, and Universal Setup, the command:

- binds `core.longpaths=true` on every proof-local Git command so tracked source
  identity is reconstructible on Windows without changing global Git policy;
- clones the declared HTTPS remote with `git clone --no-local`;
- refuses every inherited `GIT_*` or `SSH_ASKPASS` variable before cloning,
  refuses named compiler, CMake, provider-root, cache, and loader injection
  variables, disables system/global Git config and system attributes for proof
  subprocesses, and forbids prompts;
- proves that the loaded source-closure helpers byte-match the exact FacMan
  clone before any provider or build work, runs the exact cloned strict route
  validator, and binds the pinned `jsonschema` validator and dependency lock;
- fetches only the declared canonical branch;
- proves the exact pin exists and is an ancestor of that branch;
- checks out the exact pin in detached mode;
- rejects Git alternates, replace refs, config includes, shallow history,
  partial-clone/promisor configuration, unexpected git/common/object/worktree
  paths, extra remotes, refspec drift, non-SHA-1 object stores, local-clone
  substitution, dirty source, and revision drift;
- hashes each repository's tracked `.gitattributes` and complete
  `git ls-files --eol` inventory;
- runs the complete three-repository native, Python, strict, and AIDE
  validation matrix in a fresh out-of-tree build root;
- runs the host's required zero-skip package proof;
- builds, hashes, verifies, extracts, and runtime-smokes the unsigned portable
  CLI package;
- verifies that the package source revisions exactly equal the three proof
  checkouts;
- binds the package manifest, stage manifest, composition resolution root,
  source observation, runtime metadata, artifact, and provenance digests;
- records repository trees, tool identities, test counts, artifact and
  provenance digests, and final source cleanliness in a schema-validated JSON
  report.

New reports retain the historical `facman.remote_source_closure.v1` envelope
for existing evidence readers but declare the explicit
`facman.remote_source_closure.hardened.v2` proof profile. That profile requires
the complete repository-isolation, package-custody, proof-code, and schema-
validator fields. Retained profile-less v1 evidence remains valid only as the
legacy `.01` class; `.02` successor evidence requires the hardened profile.

The successor projection additionally binds the active route index, immutable
route-v2 definition digest, reconciled provider pins, read-only Factorio
archive/executable identity,
an unmaterialized source-level instance spec/binding/readiness record, the
reviewed workspace-root contract, and exact tool/test/schema identities. The
instance state is deliberately `source_observed_not_materialized`; source
closure does not create a player stage or claim candidate qualification.

The proof commit and the evidence commit are intentionally separate. The JSON
report binds the published source commit that was actually reconstructed; a
later documentation/evidence commit preserves that report without pretending
that an untested self-referential commit was the candidate.

## Claim boundary

A passing source-closure report proves source availability and reproducibility.
It does not prove publisher authenticity, sign a package, publish an artifact,
issue a permit, execute Factorio, qualify a Play candidate, record a human Play
verdict, or promote route authority.

The proof deliberately relies on a qualified clean host for the executable
search path, operating-system loader, native toolchain installation, SDK image,
and Python interpreter. Their observed identities are evidence, not a complete
transitive hermetic-host proof. Closing that residual requires a separately
reviewed toolchain/runner image and immutable image identity; it must not be
inferred from this environment scrubber alone.
