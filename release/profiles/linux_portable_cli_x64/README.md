# Linux Portable CLI x64

Target-specific unsigned package proof for the CLI built on the declared
Ubuntu 24.04 x64 runner. The FacMan project libraries are linked into the
executable; the package still depends on the explicitly inspected Linux system
libraries recorded in `manifest/linux_linkage.v1.json`.

The proof covers integrity closure, ELF x86-64 identity, no RPATH/RUNPATH,
dynamic-dependency allowlisting, relocation, spaces, Unicode, read-only package
roots, arbitrary working directories, external workspaces, empty `PATH`, and
post-extraction execution. It is not an all-distributions, universal Unix,
fully static, signed, released, or published claim.
