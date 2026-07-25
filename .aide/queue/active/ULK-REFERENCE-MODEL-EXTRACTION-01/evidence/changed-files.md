# Changed files

Universal Launcher provider revision `e78cc9f3a23f748130749ebe7241dbd1166f8b25`
adds ULK ABI 1.5 with versioned product, install, instance, profile,
artifact-set, and launch-plan references, a closed reference-graph contract,
and identity/staleness validation.

FacMan pins the provider, requires ULK ABI 1.5, projects complete Factorio
launch references in its launch handler, and validates them through ULK before
strict launch eligibility. Factorio workspace composition, content, paths, and
profiles remain in the Factorio binding.
