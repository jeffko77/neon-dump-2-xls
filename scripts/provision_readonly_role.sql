-- Mirror of provision logic for Neon SQL Editor / MCP run_sql_transaction.
-- Replace placeholders before running.

-- CREATE ROLE neon_export_reader WITH LOGIN PASSWORD '<strong-password>';
-- GRANT CONNECT ON DATABASE neondb TO neon_export_reader;
-- GRANT pg_read_all_data TO neon_export_reader;

-- GRANT USAGE ON SCHEMA public TO neon_export_reader;
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO neon_export_reader;
-- GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO neon_export_reader;
-- ALTER DEFAULT PRIVILEGES FOR ROLE neondb_owner IN SCHEMA public
--   GRANT SELECT ON TABLES TO neon_export_reader;

-- GRANT USAGE ON SCHEMA archive TO neon_export_reader;
-- GRANT SELECT ON ALL TABLES IN SCHEMA archive TO neon_export_reader;
-- GRANT SELECT ON ALL SEQUENCES IN SCHEMA archive TO neon_export_reader;
-- ALTER DEFAULT PRIVILEGES FOR ROLE neondb_owner IN SCHEMA archive
--   GRANT SELECT ON TABLES TO neon_export_reader;
