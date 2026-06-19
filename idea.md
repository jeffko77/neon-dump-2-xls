Local Neon Database Excel Export

Recommendation

Use a local CLI script only — no Fly.io endpoint, no background worker, no extra RAM in production.

This matches your constraints:





~100MB database (per docs/setup/backup_setup.md) is small enough for a laptop to handle comfortably



Rare use does not justify keeping Excel libraries or export code in the production container



Neon direct access already exists in the repo via db_URL_PROD / scripts/_prod_db_url.py patterns used by other scripts



Existing exports (app/services/scheduler/arbiter_export.py) load everything into memory — we should not copy that pattern for 72 tables

flowchart LR
    subgraph local [Your laptop]
        CLI["scripts/export_database_excel.py"]
        XLSX["lacrosse_scheduler_export_YYYYMMDD.xlsx"]
    end
    subgraph neon [Neon PostgreSQL]
        DB[(public + archive schemas)]
        IS[information_schema / pg_catalog]
    end
    CLI -->|"db_URL_PROD from .env"| DB
    CLI --> IS
    CLI --> XLSX



What to build

1. Shared export module (testable, no FastAPI dependency)

New file: app/services/export/database_excel_export.py

Responsibilities:





Discover tables via information_schema.tables (schemas: public, archive; optionally skip pg_catalog internals)



For each table, stream rows with a server-side cursor (psycopg2 named cursor or SQLAlchemy stream_results) — one table at a time, not .all() across the DB



Write each table to its own Excel worksheet (tab name truncated/sanitized to Excel’s 31-char limit; prefix with schema if needed, e.g. archive.historical...)



Build documentation sheets from metadata queries (no ORM required)

2. Local CLI entry point

New file: scripts/export_database_excel.py

Follow existing script conventions:





sys.path bootstrap like scripts/audit_dbo_dependencies.py



--prod flag → scripts/_prod_db_url.py for Neon prod URL



--output path.xlsx (default: exports/lacrosse_scheduler_YYYYMMDD_HHMMSS.xlsx)



--schemas public,archive (default both)



--exclude-pattern for scratch tables if desired later

Example usage:

uv run python scripts/export_database_excel.py --prod

No Fly.io, no deployed code path.

3. Excel workbook structure







Sheet



Contents





_README



Export timestamp, connection host (not password), row counts per table, link note to in-app docs/db/database_charts.html





_Tables



Table inventory: schema, name, approx row count, column count





_Columns



All columns: schema, table, column, type, nullable, default





_ForeignKeys



Explicit PG FK constraints from information_schema / pg_constraint





_LogicalKeys



Important for this codebase: legacy tables use text IDs (schoolid, composite keys) without FK constraints — document known logical links from docs/reference/DATABASE_TABLES_BY_FUNCTION.md and ORM ForeignKey declarations in app/models.py





_ER_Diagram



Mermaid source text (pasteable into Mermaid Live / GitHub) generated from _ForeignKeys + curated logical edges





One sheet per table



Header row + data rows

The documentation sheets address your “figure of dependencies” requirement without needing image rendering in the script. Optionally add a _ER_Diagram.png later via mermaid-cli as a dev-only enhancement — not required for v1.

4. Memory-efficient Excel writing

Library: openpyxl in write_only mode (or xlsxwriter — either is fine; openpyxl already used in scripts/import_arbiter_reference_data.py).

Strategy:





Process one table at a time: fetch batch → append rows to worksheet → discard batch



Never hold full workbook + all tables in RAM



For very wide tables, cap displayed columns only if Excel limits are hit (unlikely at current scale)

Expected peak RAM on laptop: tens of MB, not hundreds — well outside Fly’s 256MB concern.

5. Dependencies (keep out of production image)

Add optional dependency group in pyproject.toml:

[project.optional-dependencies]
export = ["openpyxl>=3.1.2"]

Install only when needed:

uv sync --extra export

Do not add openpyxl to requirements.txt (used by Dockerfile for Fly deploy).



What NOT to build (and why)







Approach



Why skip





In-app /help/export-database download



Loads openpyxl + full export into 256MB uvicorn process; same machine serves HTTP





Fly.io one-off machine / second service



You explicitly want to avoid this





pg_dump only



Great for backup/restore, but not “one tab per table” Excel with readable docs





Pandas read_sql entire DB



Higher RAM; unnecessary for ~100MB





Neon MCP / API export



MCP is for management, not bulk data export; direct psycopg2 is simpler

Note: docs/setup/backup_setup.md references backup_script.py that doesn’t exist in the repo. This Excel export is documentation/analysis, not a substitute for Neon PITR + pg_dump backups. Consider a separate small pg_dump script later if you want operational backups.



Security





Script reads db_URL_PROD from local .env only — never commit credentials



Output .xlsx may contain passwords hashes, coach emails, etc. — write to exports/ (gitignored) and treat file as sensitive



No new public HTTP route



Optional future enhancement (only if you want in-app convenience later)

A thin Help page button that documents the CLI command and links to docs/db/database_charts.html — not a server-side export. Zero RAM cost.



Files to add/change







File



Action





app/services/export/__init__.py



Create package





app/services/export/database_excel_export.py



Core export logic





scripts/export_database_excel.py



CLI entry point





pyproject.toml



[project.optional-dependencies] export





.gitignore



Ensure exports/ is ignored





docs/reference/DATABASE_EXPORT.md



Short usage doc (trigger, flags, sheet glossary)

No changes to fly.toml, Dockerfile, or requirements.txt.



Verification





uv sync --extra export



uv run python scripts/export_database_excel.py --prod --output /tmp/test_export.xlsx



Open workbook: confirm sheet count ≈ table count + 6 doc sheets



Spot-check large tables (tblschedule, tblscheduleversiongames, tblroster) for row counts vs DB



Confirm _ForeignKeys lists ORM-declared FKs; _LogicalKeys documents schoolid-style legacy links



Confirm production Docker image build unchanged (no openpyxl in requirements.txt)

