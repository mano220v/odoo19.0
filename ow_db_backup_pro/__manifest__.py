{
    'name': 'Automatic Database Backup Pro',
    'version': '19.0.1.0.0',
    'category': 'Administration',
    'summary': 'Premium automated, multi-destination database backup with retention, encryption & alerts',
    'description': """
Automatic Database Backup Pro
==============================
Enterprise-grade scheduled backup solution for Odoo 19.

Features
--------
* Schedule backups (minutes/hours/days/weeks/months) per configuration
* Multiple storage destinations: Local disk, FTP, SFTP, Amazon S3 (or compatible),
  Google Drive, Dropbox
* Backup format: Full (Database + Filestore ZIP) or SQL Dump only
* AES-256 password protected / encrypted backups (optional, via pyzipper)
* Auto-retention: keep last N backups, or keep backups for N days
* Email alerts on success and/or failure per configuration
* One-click "Backup Now" and "Test Connection" for every storage type
* Full backup history log: size, duration, status, destination, error trace
* One-click restore from history (local storage) or by uploading a file --
  always restores into a brand-new database, never overwrites an existing one
* Backup analytics: success/failure counts, storage usage, size trend graph & pivot
* Multiple independent backup configurations, each with its own schedule and destination
* Additional database names supported per configuration (same Postgres server)

Optional Python dependencies (install only what you need)
-----------------------------------------------------------
* SFTP: paramiko
* Amazon S3 / compatible: boto3
* Google Drive: google-api-python-client, google-auth
* Dropbox: dropbox
* Encryption: pyzipper
    """,
    "author": "Odoo Wings",
    "website": "https://apps.odoo.com/apps/modules/browse?author=Odoo%20Wings",
    "support": "vsmanoj144@gmail.com",
    "license": "OPL-1",
    "price": 3.95,
    "currency": "USD",
    'depends': ['base', 'mail'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/mail_template_data.xml',
        'views/db_backup_config_views.xml',
        'views/db_backup_history_views.xml',
        'wizard/backup_now_wizard_views.xml',
        'wizard/restore_wizard_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
