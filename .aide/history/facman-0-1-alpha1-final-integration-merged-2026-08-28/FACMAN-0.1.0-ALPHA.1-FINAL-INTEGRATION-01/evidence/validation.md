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

Independent review found release identity, authority closure, route-permit
ordering and durable claim semantics, typed frontend identities/refusals, and
exact provider closure fit for protected integration. PR #191 head
`e3c994770b0da07f0493e22c6c502aafd653680c` and tree
`ffeb7b092f4c8f2a55f5418068593677d5426670` were integrated with a normal merge
commit. Protected `dev` now records:

- merge commit `06f0f7c9084ad90c59b09c5691847791ddc7dd85`;
- tree `ffeb7b092f4c8f2a55f5418068593677d5426670`;
- parents `e73d778173be283d47925fa055ba1aae7b82fb28` and
  `e3c994770b0da07f0493e22c6c502aafd653680c`;
- actor `Julesc013`, merged at `2026-08-28T11:41:44Z`;
- seven workflow runs and all 20 check runs completed successfully, including
  CI, CodeQL/code security, schema/security policy, synthetic product TCK,
  bounded provider inputs, and Linux/macOS/Windows provider SDK consumption.

The exact durable receipt is
`release/index/alpha1_dev_integration_closeout.v1.toml`. Final-dev package
hashes deliberately remain outside this integrated WorkUnit: the three final
human-test packages must be rebuilt after the narrow closeout itself reaches
protected `dev`.

No tag, signing, publication, support promotion, protected-reference mutation,
merge, gameplay execution, or human acceptance authority is granted.
