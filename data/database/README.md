# Local database

`cf.db` is the active SQLite database used by Cadence Focus.

The importer saves timestamped copies in `backups/` before changing the active
database. Generated backup files are kept out of Git.

Expected path:

```text
data/database/cf.db
```
