# Third Party Notices

This repository does not bundle Factorio binaries or Wube assets.

## Universal Launcher

- Source: https://github.com/Julesc013/universal-launcher
- Pinned commit: `5479939ca5cbc9ee0f901608a92012778b4752ae`
- License: MIT
- License notice: `LICENSES/UniversalLauncher.txt`
- Use: linked runtime library and installed public C headers for the experimental FacMan SDK
- Runtime networking: none enabled by this repository

## Universal Setup

- Source: https://github.com/Julesc013/universal-setup
- Pinned commit: `279ad4876dc325f8e1fcdc918c91b098a11bc616`
- Package license: MIT AND Zlib
- License notice: `LICENSES/UniversalSetup.txt`
- Use: linked setup runtime and installed public C headers for managed-setup contracts
- Runtime networking: none enabled by this repository

### Universal Setup bundled dependency: Zlib 1.3.2

Copyright notice:

 (C) 1995-2026 Jean-loup Gailly and Mark Adler

This software is provided 'as-is', without any express or implied warranty.
In no event will the authors be held liable for any damages arising from the
use of this software.

Permission is granted to anyone to use this software for any purpose,
including commercial applications, and to alter it and redistribute it freely,
subject to the following restrictions:

1. The origin of this software must not be misrepresented; you must not claim
   that you wrote the original software. If you use this software in a product,
   an acknowledgment in the product documentation would be appreciated but is
   not required.
2. Altered source versions must be plainly marked as such, and must not be
   misrepresented as being the original software.
3. This notice may not be removed or altered from any source distribution.

Jean-loup Gailly and Mark Adler

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
