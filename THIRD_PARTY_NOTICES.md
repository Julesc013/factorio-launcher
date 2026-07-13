# Third Party Notices

This repository does not bundle Factorio binaries or Wube assets.

## Universal Launcher

- Source: pinned workspace provider `universal-launcher`, resolved outside this repository
- Pinned commit: `de6c7c6cfa80c524296066bd6bb90a70ba02b760`
- License: no license file is declared at the pinned commit
- Use: linked shared library and installed public C headers for the experimental FacMan SDK
- Runtime networking: none enabled by this repository

The missing upstream license declaration is an unresolved redistribution issue.
The installed SDK proof is therefore a local compatibility proof, not publication
or redistribution approval. The provider README is installed as provenance and is
not represented as a license.

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

- dependency name and version
- license
- source URL
- whether the dependency is linked, bundled, or used only for development
- any redistribution obligations
