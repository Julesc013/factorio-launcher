# Validation

The corrected implementation through `f65c5ae2901e2673b5dc02d784baefcacb661ae4`
is machine-qualified:

- contract and metadata generators are deterministic and current;
- project state, plan views, AIDE Lite, queue state, source closure, release
  programme, source format, schema, and alpha release-source checks pass;
- the strict gate passes, including release-identity coherence and the
  F100-through-F210 family check;
- the full explicitly bound clean-root Python suite passes: 1,263 tests with
  9 declared skips;
- the release identity coherence check reports no active misnumbered residue;
- F100, F110, F200, and F210 read-only version/help probes report exact versions
  `1.0.0`, `1.1.110`, `2.0.77`, and `2.1.14`, retain no absolute paths, and
  record unchanged installation-tree fingerprints;
- static and supported shared-provider Debug and Release matrices pass 39/39
  in each configuration; the subsequent `f65c5ae2` change is confined to the
  Python package-smoke decoder, and all three Release package roots were
  refreshed to that exact source identity;
- the WinForms x64 Release build succeeds with 0 warnings and 0 errors, and its
  C1 runtime and command-client smokes pass;
- three independent clean roots produce the same path-free source-observation
  digest, `c912f038553128edce0605209561f752c69949621c1b730344ea7c5d9394b77c`;
- all three release profiles rebuild in all three roots with matching package
  trees, SBOMs, provenance, and byte-identical archives:
  - CLI: 508 files, 4,097,557 bytes,
    `f6c84bea5403ee4efab421111542f97b8d48da346a4294deb8569b57999ab483`;
  - TUI: 506 files, 4,093,730 bytes,
    `b2862f164f78af6b60aba4641c25d08971f2217eda513c4d379f09e282ea237c`;
  - WinForms: 510 files, 6,002,323 bytes,
    `0972cbfa8197fbf34233448c9fc339753bdef5456048499b83feff9e4a6363e7`;
- all nine package hash-manifest, provenance, and runtime checks pass with an
  empty `PATH`, arbitrary current directory, exact alpha identity, read-only
  doctor behavior, and no workspace creation;
- relocated Unicode install paths and a 236-character Unicode workspace path
  pass for CLI, TUI, and WinForms packages;
- the exact-provider synthetic product TCK passes; full canonical-provider
  conformance passes provider self-conformance, source/static/shared installed
  and relocated consumers, private runtime, and all 19 negative controls.

The source record intentionally does not embed a self-referential hash for an
archive built from the evidence-only closeout commit. Exact PR-head archive
hashes and hosted check URLs belong in the protected-dev pull-request receipt.

No tag, signing, publication, support promotion, protected-reference mutation,
merge, gameplay execution, or human acceptance authority is granted.
