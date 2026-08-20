# Remaining risks

- The Technical Preview candidate has been activated, not qualified. All 29
  required rows still require exact merged-source re-evaluation.
- `main` remains at `b70be106...`; no canonical promotion is claimed.
- Repository identity is still coupled to the legacy slug until
  `FACMAN-REPOSITORY-IDENTITY-DECOUPLING-01` is implemented and reviewed.
- No product execution, Setup mutation, route promotion, human accessibility
  verdict, tagging, signing, publication, or support authority is active.
- The current package and source-closure evidence is invalidated by the future
  repository rename and cannot substitute for new-slug reconstruction.
- The accepted dev source reproduces a native promotion failure in
  `facman_presentation_service_smoke`: 37 of 38 CTest cases pass, while the
  synthetic launch cannot finalize its durable idempotency receipt. Ninja and
  Visual Studio Debug builds agree. This requires a separately scoped runtime
  repair and fresh independent qualification before release promotion.
