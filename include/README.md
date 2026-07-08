# Include

Owns public Factorio binding ABI headers for this repository.

May contain:

- C-compatible public headers under `include/flb/`
- ABI-oriented documentation for those headers

Must not contain:

- `usk` or `ulk` headers
- private implementation headers
- C++ classes, STL types, Objective-C types, or C# code
- frontend or GUI implementation

Universal setup headers live in `universal-setup`. Universal launcher headers
live in `universal-launcher`.
