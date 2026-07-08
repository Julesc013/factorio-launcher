# Save Manager

Save workflows are product-specific and remain behind the Factorio binding.

Planned commands:

```bash
factorio-launcher saves list --instance <instance-id>
factorio-launcher saves backup <save>
factorio-launcher saves import <file> --instance <instance-id>
factorio-launcher saves export <save> <file>
```

Save operations must support backups, locks, redaction in diagnostic bundles,
and dry-run previews where mutation is involved.
