Lax Scheduler Tools
===================

Local desktop app for the assigner:

- **Database Export** — export the Neon PostgreSQL scheduler database to Excel
- **Invoice Database** — manage billing, schools, payments, and PDF invoices

First-time setup (database export only)
---------------------------------------
If you skipped the connection string during install, re-run the installer and
paste your readonly PostgreSQL connection string on the Database Connection step.

The invoice database works offline and is seeded automatically on first launch
from the bundled original dataset (`data/invoice_database_seed.json`).

Use **Backup → Reset to original dataset** to restore the starting data after edits.

Where files are saved
---------------------
Database exports:
  Documents\LaxSchedulerExports\

Invoice database and backups:
  Documents\InvoiceDatabase\

Updating the connection string
------------------------------
Re-run the installer and enter a new readonly connection string.

Support
-------
Contact your administrator for a readonly database connection string.

PDF invoice format reference:
  docs\INVOICE_PDF_FORMAT.md (included in install)
