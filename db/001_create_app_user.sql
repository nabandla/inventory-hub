-- 001_create_app_user.sql
-- Creates the limited app user (least privilege: read/write rows, no schema changes).
-- Run as the admin login (nadmin) while connected to the TARGET database
-- (inventory-dev or inventory-prod), NOT master.
-- Replace <<PASSWORD>> locally. NEVER commit the real password.
-- Password rules: 8+ chars, 3 of 4 character types, avoid ' ; { } # $ and spaces.

-- Confirm which database you are in
SELECT DB_NAME();

IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'app_inventory')
    CREATE USER app_inventory WITH PASSWORD = '<<PASSWORD>>';

ALTER ROLE db_datareader ADD MEMBER app_inventory;
ALTER ROLE db_datawriter ADD MEMBER app_inventory;

-- Verify: expect two rows (db_datareader, db_datawriter)
SELECT r.name AS role_name, m.name AS member_name
FROM sys.database_role_members rm
JOIN sys.database_principals r ON rm.role_principal_id = r.principal_id
JOIN sys.database_principals m ON rm.member_principal_id = m.principal_id
WHERE m.name = 'app_inventory';
