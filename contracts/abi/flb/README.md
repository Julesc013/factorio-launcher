# FLB ABI

Owns compatibility notes for the Factorio binding public C ABI.

Rules:

- public structs must be versioned or size-tagged
- ownership transfer must be explicit
- errors must be explicit result values
- no public C++ classes, STL, exceptions, RTTI, Objective-C types, or C# types
