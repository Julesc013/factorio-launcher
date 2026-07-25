# Local dependency pin enforcement remaining risks

- Local checks cannot prove a remote branch or tag; they bind the checked-out
  Git object only.
- Hosted workflows retain explicit `--align` because they construct detached
  dependency checkouts. That mutation remains opt-in and visible.
- Direct custom CMake invocations do not run the Python doctor; the canonical
  local and package workflows do.
- New dependency components must be added to the workspace lock and verifier
  path mapping.
- Pin correctness does not by itself prove behavioral compatibility; the
  clean three-repository integration proof remains required after extraction.
