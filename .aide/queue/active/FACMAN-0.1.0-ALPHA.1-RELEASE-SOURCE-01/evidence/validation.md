# Validation

Source-level validation passed for the exact task diff based on protected
`dev@8744e35529b62cbb56326c32c2281669478061a0`.

The predecessor machine-qualified package remains the immutable
`0.1.0-alpha.0` development-contract baseline. It is not renamed, relabelled,
or published as `0.1.0-alpha.1`.

This record will bind source-level validation only. Three-root package, route,
and human evidence are produced after the release-source commit is frozen so
that receipt-only work does not change the candidate bytes.

## Exact source-level result

- `0.1.0-alpha.1` is allocated across authored and generated version surfaces.
- All external GitHub Actions are pinned to reviewed immutable full SHAs; no
  Dependabot major-version update was taken.
- The tagless asset manifest, prospective ledger, publication-authority
  schema, manual workflow, route scaffold, and human packet bind alpha.1 while
  retaining closed tag, signing, publication, Factorio-execution, support, and
  human-verdict authority.
- The release-source transition changes no product capability, ordinary
  CLI/TUI/WinForms UX, ULK pin, or USK pin.

## Validation

```text
full Windows Python regression suite
  1,173 passed; 19 expected skips; 0 failures/errors

focused alpha/release/workflow/human suite
  47 passed

repaired-provider alpha.1 canary composition/round-trip
  18 passed

native MSVC Debug build
  facman_cli, facman_presentation_service_smoke,
  facman_tui_product_model_smoke, facman_diagnostic_traversal_smoke: PASS

native focused execution
  facman_presentation_service_smoke: PASS in real Windows user topology
  facman_tui_product_model_smoke: PASS
  diagnostic Windows junction negative control: PASS

WinForms Release build
  PASS; 0 warnings; 0 errors

schema validation
  362 schemas: PASS

strict exact-provider validation
  PASS with ULK 5479939ca5cbc9ee0f901608a92012778b4752ae
  and USK d2a2aae7e61c47035c92334b0522143b4fea3880

AIDE Lite test
  PASS

generated metadata, source format, and git diff whitespace
  PASS
```

The sandbox-only MSBuild FileTracker denial and Windows user-TEMP
canonicalization refusals were rerun successfully in the real Windows user
topology. They are environment/topology classifications, not product defects.
