# Automatic Database Backup Pro (Odoo 19)

## Install
1. Drop `ow_db_backup_pro` into your addons path.
2. Update Apps List, install **Automatic Database Backup Pro**.
3. Assign yourself to the **Backup Manager** group
   (Settings > Users, under "Database Backup Pro" category).

## Optional dependencies
Only install what you actually use as a storage destination:

| Destination     | pip package(s)                                  |
|------------------|--------------------------------------------------|
| SFTP             | `paramiko`                                        |
| Amazon S3 / compatible | `boto3`                                     |
| Google Drive     | `google-api-python-client` `google-auth`         |
| Dropbox          | `dropbox`                                         |
| Encryption       | `pyzipper`                                        |

Local and FTP work out of the box with the Python standard library.

## Menu: DB Backup Pro
- **Configurations** — create one or more backup profiles: source database(s),
  schedule, storage destination, retention policy, encryption, email alerts.
  "Backup Now" runs immediately; "Test Connection" verifies credentials
  without uploading anything.
- **Backup History** — every run, its status, size, duration, destination and
  (on failure) the full error trace. Includes Graph and Pivot views for
  storage-usage trends. Local backups can be downloaded straight from the
  list; any successful backup can be restored.
- **Instant Backup** — one-off backup you generate and download immediately,
  independent of any saved configuration.

## Restore behaviour (important)
Restore **always creates a brand-new database** — it will refuse to run if
the target name already exists, and it never touches your live database.
This mirrors Odoo's own `/web/database/manager` restore, just triggered
from inside the backend. Test the restore flow on staging before relying on
it in production; `odoo.service.db.restore_db()`'s exact signature has
shifted slightly across Odoo releases, so verify against your specific 19.0
core build.

## Notes / assumptions
- Scheduling uses a dynamically managed `ir.cron` per configuration
  (created/updated automatically — you don't need to touch Scheduled
  Actions directly).
- "Additional Databases" lets one config back up several databases on the
  same Postgres server in a single run; this requires the Postgres role
  Odoo connects with to have rights on those other databases.
- Encrypted backups are re-zipped with AES-256 via `pyzipper`; without
  that library installed, enabling encryption raises a clear error rather
  than silently skipping it.
