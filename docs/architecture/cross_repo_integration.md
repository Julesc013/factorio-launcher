# Cross-Repo Integration

FacMan is validated as part of a three-repo workspace:

```text
universal-setup      setup mutation, refusal, audit, and installed-state authority
universal-launcher   product orchestration, command graph, and launch-plan authority
factorio-launcher    Factorio binding, product facts, and app frontends
```

`tools/cross_repo_check.py` validates the local boundaries:

- `factorio-launcher/include` exposes only `flb`.
- `factorio-launcher/runtime` does not own `usk` or `ulk`.
- `universal-launcher` exposes `ulk` and launcher command graph paths.
- `universal-setup` exposes `usk` and setup contract paths.
- sibling repos do not grow Factorio-specific implementation paths.

Use product-only mode for single-repo validation:

```powershell
py -3 tools/cross_repo_check.py --product-only
```

Use workspace mode for the full integration baseline:

```powershell
py -3 tools/cross_repo_check.py
```

Use the reproducibility smoke when publishing or validating a fresh clone:

```powershell
py -3 tools/repro_workspace_smoke.py
py -3 tools/repro_workspace_smoke.py --build
```

The smoke keeps quick boundary checks separate from the heavier build matrix so
single-repo contributors can validate product-only work while release or branch
handoffs can prove the full sibling workspace.
