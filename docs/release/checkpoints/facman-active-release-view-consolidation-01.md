# FacMan active release view consolidation 01

WorkUnit: `FACMAN-ACTIVE-RELEASE-VIEW-CONSOLIDATION-01`

Status: canonical-dev restack and local requalification complete; exact-head
hosted validation, review, and protected integration pending

## Outcome

One closed active-release selector now binds the three unified product profiles
and canonical eight-asset shape. Existing package and release profile arrays
remain complete construction catalogs for compatibility, while support rows,
distribution lanes, update lanes, and package producers carry explicit current,
preview, historical, or future roles.

The selector admits:

- Windows x64 as the WinForms/.NET Framework 4.8 reference product;
- macOS Intel x64/AppKit as a selected experimental preview;
- Linux x64/GTK3/X11 as a selected experimental preview; and
- six product packages, checksums, and consolidated evidence.

It excludes standalone CLI/TUI/toolkit profiles, earlier candidate records, and
the Alpha.3 distribution from current release obligations without deleting
their evidence.

## Fail-closed controls

- The active view has a closed JSON schema and grants no human, release,
  signing, tagging, publication, or support authority.
- A dedicated validator cross-checks all producer, support, distribution,
  package, catalog, update, artifact, and history views.
- Strict validation and the hosted schema workflow execute the validator and
  its negative controls.
- Project-state generation reads the selector and exposes only its three
  current profiles.

## Evidence

The dedicated active-view validator passed with exactly three product profiles,
two selected previews, and eight canonical assets. Its negative controls proved
that a legacy profile, an undeclared preview, or a mismatched producer,
support, distribution, package, update, artifact, or historical view fails
closed.

The original affected matrix passed 41/41 native tests and 171 Python tests
with two declared skips. After the predecessor merged, this WorkUnit was
forward-restacked without a consolidation-tree change onto canonical `dev`
commit `f99d96e002f5af519824942a1f8b74bcc26d96f8`.

The restack's deterministic affected run exposed one fail-closed test-policy
omission: configured CTest target `facman_content_foundation_smoke` was not in
the fast impact set. The policy and its `runtime/factorio/` mapping now include
that target, with a regression test proving selection. The repaired affected
gate passed three selected native tests and 15 selected Python tests with no
required or unknown skip.

After binding the canonical base and restack receipt, the final affected gate
passed four selected native tests, 90 selected Python tests, and all 13
selected strict validators. Its single optional installed-component skip was
classified; required and unknown skip counts remained zero.

The final managed command was:

```text
py -3 tools/dev.py verify-all developer
```

It exited 0 and completed:

- Debug native configure/build and 41/41 CTest cases;
- Release source-static and product-shared builds;
- WinForms .NET Framework 4.8 x64 Release with 0 warnings and 0 errors;
- 1,478 Python tests with 0 failures, 0 errors, 0 required-blocked skips, and
  0 unknown skips;
- nine classified skips: two optional, five unsupported Windows symlink cases,
  and two not applicable POSIX PTY cases covered by the ConPTY lane; and
- the final strict pass, including all 402 registered JSON schemas.

`py -3 .aide/scripts/aide_lite.py test`, generated metadata checks,
project-state validation, plan-view validation, and `git diff --check` also
passed. Detailed receipts are retained with the WorkUnit evidence.

No protected branch, tag, release, signing, publication, live Factorio,
managed-install, support promotion, GitHub setting, or human-verdict action is
authorized or performed here.
