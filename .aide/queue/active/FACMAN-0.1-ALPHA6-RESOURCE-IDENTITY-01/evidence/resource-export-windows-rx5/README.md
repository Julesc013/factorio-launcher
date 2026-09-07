# Windows resource-export proof at rx5

The fresh Windows VS18 x64 shared-provider build passed its three selected fixtures:
`facman_resource_identity_smoke`, `facman_resource_product_cli`, and
`fl_archive_core_smoke`. All 16 command jobs and the outer job closed successfully.
The clean build took 318.692 seconds; the complete wrapper took 667.971 seconds.

The exact source is a dirty 27-path resource overlay on committed base
`c2ce811312aec8229c19f50fbbb07cac0b88a407`, projected tree
`288eb824f0e0ded9cf1061252cd495fdb6fba161`. The 4,743 resulting canonical source
files, three snapshots, 477 stable-provider files, five compiled binaries, both
compiler records and exact fixture arguments were independently checked by ROOT.
The candidate preserves the committed POSIX CMake and test-impact additions.

[Custody](custody.json) lists every original byte stream in [the archive](evidence.zip).
It includes source/patch/manifests, controller and supervision dependencies,
compiler-identification files, all raw command receipts, fixture metadata, source
maps, ROOT reviews, and the file-only seal. Full binaries and remaining build
artifacts stay in the external 16.8 MB archive identified by its exact member map.
The complete closed root has 8,407 rows; the controller's earlier 8,406 count
preceded writing its own final result.json.

All three failed predecessor attempts remain distinct and immutable. Rx2 failed
checkout on long paths; rx3 could not discover Visual Studio; rx4 produced C/C++
compiler-identification objects before FileTracker common-data initialization
failed. Their raw streams, compiler records, original ZIPs and causal observations
are included without normalizing the original bytes or claiming native test passes.
Nested original ZIPs retain their own adjacent member maps.

The qualification is limited to these three actual Windows fixtures. Synthetic
Linux/macOS layout names in retained Windows test directories do not establish
native Linux/macOS execution. This does not close the WorkUnit or qualify provider
adoption, integrated product process suites, other frontends/platforms, packaging,
human/game/signing or release gates. Repository application was still pending at
this evidence freeze. Later source integration must retain this exact distinction.
