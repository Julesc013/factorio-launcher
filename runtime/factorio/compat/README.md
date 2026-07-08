# Compatibility

Optional home for narrowly scoped compatibility shims.

May contain:

- wrappers required by a specific legacy compiler or platform lane
- adapters that isolate unavoidable API differences

Must not contain:

- general Factorio product logic
- broad helper libraries
- language-version buckets

Prefer domain folders first. Use this folder only when the compatibility concern
is the primary reason the file exists.
