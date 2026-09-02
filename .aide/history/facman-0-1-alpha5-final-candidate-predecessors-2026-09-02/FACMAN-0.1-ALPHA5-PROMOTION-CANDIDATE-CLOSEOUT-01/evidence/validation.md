# Validation

Result: PASS for the complete local promotion obligation profile and for the
exact hosted, unsigned, unpublished alpha.5 product candidate. This is machine
qualification only; it grants no human or release authority.

The final clean local command was:

```text
py -3 tools/dev.py test release --full --obligation-profile promotion --task-root <marker-owned-alpha5-closeout-root>
```

Final results:

- native static suite: 41/41 passed;
- shared/product build and package-proof roots: passed;
- WinForms .NET Framework 4.8 Release build: 0 warnings, 0 errors;
- WinForms transport harness: 38/38 cases passed;
- Python suite: 1,443 tests, 0 failures, 0 errors, 0 unexpected successes;
- promotion obligation gate: passed;
- skips: 2 optional, 5 unsupported, 2 not applicable, 0 required blocked,
  0 unknown, and 0 historical-only;
- strict validation: passed, including 400 schemas, 127 commands, 247 refusal
  codes, 128 refusal goldens, package TCK for Windows/macOS/Linux, security,
  compliance, source-format, accessibility, AIDE queue, and generated-state
  checks.

The validation sequence retained its failures as remediation evidence:

1. The first full local profile exposed source-size, line-length, generated
   metadata, and plan-state inconsistencies. Alpha.5 state rendering was
   extracted, support rows were made schema-bounded, and generated views were
   reconciled without increasing quality budgets.
2. A complete rerun then exposed an absolute developer-machine custody path in
   packaged release metadata. The receipt and schema were changed to exact,
   portable `facman-development://` locators; the detector was not weakened and
   the receipt remained in the packaged metadata closure.
3. That canonical-input change correctly made generated projections stale.
   The command catalog and native version header were regenerated, their
   focused tests passed, and the final complete profile above passed cleanly.
4. A final cross-platform scope audit then found that the immutable archive
   index was bound to Windows CRLF working-tree bytes even though Git enforces
   LF for JSON. The receipt now records the declared `text_lf_v1` digest,
   `eecc84950b0905e14f22ea5ad35066ec39cbd8fabf1d75ccb5a8b62164435c73`,
   and the checker canonicalizes only that text record before hashing. A
   focused LF/CRLF regression protects Linux and macOS CI from checkout-form
   drift without weakening binary artifact hashing.

After that audit, 118 affected closeout, release, plan, schema, package, and
generated-state tests passed, followed by 73 post-lifecycle AIDE/truth tests,
the complete strict validator, AIDE validation, and AIDE self-test. The new
line-ending regression increases the next complete Python-suite census to
1,444; the 1,443 figure above remains the exact persisted result of the final
full promotion-profile invocation rather than a reconstructed count.

Hosted product-candidate evidence is bound by
`release/index/alpha5_promotion_candidate_closeout.v1.toml`. Manual workflow
run `33576140943`, attempt 1, ran from `2026-09-02T00:38:12Z` to
`2026-09-02T00:45:42Z` at exact `main` revision
`a7a518dbfe2a6d54da7b9c84fbd318300265e31d` and tree
`1ebcd2b230ed188e021880ffa4c438de2ede655b`. All five jobs passed and four
workflow artifacts were retained. The final artifact `9826850751` has digest
`sha256:2afe4529f056ac4400352400418e5cede776146e9ef803aa4901cc76944f71c5`.
Independent `product_candidate verify` passed its exact flat 14-file,
47,353,341-byte closure containing six product packages, six evidence records,
`SHA256SUMS`, and the bundle manifest.

The receipt also preserves the complete failed-attempt chronology and repairs:
the initial HTTP 422/no-run dispatch, contract failure run `33557664813`, and
platform failure run `33567017006` with its surviving Linux artifact. No fact
was reconstructed where durable evidence was absent.

The AIDE `task dependencies` report labels producer
`FACMAN-0.1-BETA-READINESS-01` as `missing` because that legacy report resolves
only mutable `queue/active` and `queue/next` records. The producer is not
missing from repository custody: it is closed and immutable in the dated
foundation archive, whose generated index binds its task, status, and evidence
hashes. The canonical plan retains the dependency and marks the producer
complete; AIDE archive/compaction and plan validators passed. This reporting
limitation is recorded rather than hiding the dependency.

Two pre-existing Beta evidence sentences preserve the original Windows
download path inside the immutable AIDE history record. They are retained as
historical custody facts rather than rewritten after closure. Current
package-facing records use the portable `facman-development://` locator, and
`.aide/**` is excluded from every product package, so those archived sentences
are neither runtime metadata nor a package privacy leak.

Qualification is intentionally non-circular. It applies only to the exact
candidate revision above, not to the later closeout revision, synchronized
`dev`, or a future same-tree revision. Tagging, release, beta allocation,
signing, notarization, publication, support, human verdict, Factorio execution,
and managed-install authority remain false.

The non-publishing AIDE changelog preview passed over
`v0.1.0-alpha.3..43af71f8231c5a1b843636df7fd0ab8a6040d25c`. It reported one
pre-existing `release(alpha.4)` scope-format exception at commit `4289bf46`;
that published merge history is preserved rather than rewritten. The planned
closeout commit message independently passed the current FacMan `compact_v1`
policy.
