# Development getting started

Requirements are CMake 3.20+, a C/C++ toolchain, and Python 3.11+ for repository
tooling. The product runtime does not depend on Python. Universal Launcher and
Universal Setup must be available at the paths resolved by the root CMake
configuration and pinned by `release/index/workspace_lock.v1.toml`.

```powershell
py -3 tools/workspace_config.py doctor
cmake -S . -B build/native-smoke -DFACMAN_BUILD_TESTS=ON
cmake --build build/native-smoke --config Debug --parallel
ctest --test-dir build/native-smoke -C Debug --output-on-failure
py -3 tools/dev.py test --fast
```

The CLI is normally `build/native-smoke/Debug/facman.exe` on a multi-config
Windows build and `build/native-smoke/facman` on a single-config Unix build.
Use `tools/dev.py test --affected` while iterating and `verify-all` before a
promotion handoff.

Current project truth is generated into `.aide/memory/project-state.v2.json`.
Run `py -3 tools/project_state.py --write` after changing its canonical inputs.
Archived AIDE history is discoverable through `.aide/history/<checkpoint>/index.json`
but excluded from normal context packets.
