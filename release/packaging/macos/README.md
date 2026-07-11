# macOS Packaging

The target-specific `macos_portable_cli_x64` package-preview lane contains the
CLI only and is proven on `macos-15-intel`. AppKit and SwiftUI product packages
remain planned separately; no `.app` runtime, signing, notarization, Apple
Silicon, or universal-binary claim follows from the CLI tarball.
