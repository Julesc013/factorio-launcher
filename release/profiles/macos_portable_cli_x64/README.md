# macOS Portable CLI x64

Target-specific unsigned CLI package proof built and executed on the explicit
GitHub `macos-15-intel` runner with deployment target macOS 13.0. The package
contains the FacMan CLI, compatibility contracts and Factorio content only.

The proof covers integrity closure, Mach-O x86_64 identity, deployment target,
system dynamic-dependency allowlisting, absence of `LC_RPATH`, relocation,
spaces, Unicode, read-only package roots, arbitrary working directories,
external workspaces, empty `PATH`, provenance, and post-extraction execution.

This is not an Apple Silicon, universal binary, AppKit runtime, signed,
notarized, released, or published claim.
