# Linux Packaging

`linux_portable_cli.v1.toml` owns the target-specific unsigned Linux x64 CLI
package preview. It ships no GUI, TUI, daemon, shared project libraries,
Factorio binary, Python runtime, signature, installer, or updater. Its system
dynamic dependencies are inspected and recorded by the Linux package proof.

GTK, Qt, AppImage, and legacy multi-binary manifests remain compatibility or
future packaging definitions; they are not promoted by the CLI tarball proof.
