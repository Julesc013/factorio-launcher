# Remaining risks

- A future central AIDE refresh could introduce overlapping commit-profile
  functionality. The target overlay is isolated and documented so it can be
  removed after an equivalent central profile exists.
- Newly introduced well-formed scopes warn until maintainers add them to the
  recommended FacMan list; they do not silently bypass subject/type checks.
- Legacy messages remain accepted and visibly classified for compatibility.
  The FacMan template prevents their continued generation.
- Hosted policy and required-check validation completed with protected `dev`
  integration through PR #138 (`3987f58a`).

No product, provider, protected-ref, Setup, Factorio execution, signing,
publication, or release authority was granted.
