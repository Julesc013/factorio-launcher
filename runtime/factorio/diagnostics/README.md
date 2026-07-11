# Diagnostics

Doctor reports, launch explanations, reviewed log/crash collection, redaction,
stable source reads, and typed diagnostic bundle export.

The enabled export path emits structured traversal, redaction, file-read, and
omission reports. It uses the production archive and bounded transaction
layers. Frontends invoke `diagnostics.export`; they do not reconstruct
collection or ZIP behavior.
