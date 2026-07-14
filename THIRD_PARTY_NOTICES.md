# Third Party Notices

This repository does not bundle Factorio binaries or Wube assets.

## Universal Launcher

- Source: https://github.com/Julesc013/universal-launcher
- Pinned commit: `6d41e07b76cd19b2a7630835e05ac3aa125d57b8`
- License: MIT
- License notice: `LICENSES/UniversalLauncher.txt`
- Use: linked runtime library and installed public C headers for the experimental FacMan SDK
- Runtime networking: none enabled by this repository

## Universal Setup

- Source: https://github.com/Julesc013/universal-setup
- Pinned commit: `17db1bd9a680d97611fa73f7639c38e1c9472680`
- License: MIT
- License notice: `LICENSES/UniversalSetup.txt`
- Use: linked setup runtime and installed public C headers for managed-setup contracts
- Runtime networking: none enabled by this repository

## Miniz 3.1.2

- Source: https://github.com/richgel999/miniz
- Pinned commit: `77d0dce8627735138c51770d1799a1ef48f2117d`
- License: MIT
- Use: source-vendored private static archive and deflate implementation
- Runtime networking: none
- Transitive runtime dependencies: none

The full copyright, permission notice, and disclaimer are retained in
`external/miniz/LICENSE`. Binary distributions containing Miniz must include
that notice.

## PicoJSON 1.3.0+git.111c9be

- Source: https://github.com/kazuho/picojson
- Pinned commit: `111c9be5188f7350c2eac9ddaedd8cca3d7bf394`
- License: BSD-2-Clause
- Use: source-vendored private header-only JSON parser behind `runtime/core/json`
- Runtime networking: none
- Transitive runtime dependencies: none

The full copyright, redistribution conditions, and disclaimer are retained in
`external/picojson/LICENSE`. Binary distributions containing PicoJSON must
reproduce that notice in their documentation or other supplied materials.

Dependencies must document:

- dependency name and version;
- license and exact retained notice;
- source URL and pinned revision;
- whether the dependency is linked, bundled, or used only for development;
- runtime networking and transitive dependencies; and
- redistribution obligations.
