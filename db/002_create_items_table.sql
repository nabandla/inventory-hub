-- 002_create_items_table.sql
-- Creates the inventory items table.
-- Run as the admin login (nadmin) while connected to the TARGET database
-- (inventory-dev or inventory-prod), NOT master. Safe to run more than once.
-- The app user (app_inventory) already has db_datareader/db_datawriter, which
-- cover this table automatically - no extra GRANT is needed.

SELECT DB_NAME();

IF OBJECT_ID('dbo.items', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.items (
        id          INT IDENTITY(1,1) NOT NULL,
        sku         NVARCHAR(50)      NOT NULL,
        name        NVARCHAR(200)     NOT NULL,
        quantity    INT               NOT NULL CONSTRAINT df_items_quantity DEFAULT 0,
        created_at  DATETIME2(0)      NOT NULL CONSTRAINT df_items_created_at DEFAULT SYSUTCDATETIME(),
        updated_at  DATETIME2(0)      NOT NULL CONSTRAINT df_items_updated_at DEFAULT SYSUTCDATETIME(),
        CONSTRAINT pk_items          PRIMARY KEY (id),
        CONSTRAINT uq_items_sku      UNIQUE (sku),
        CONSTRAINT ck_items_quantity CHECK (quantity >= 0)
    );
END;

-- Verify: expect 6 rows (id, sku, name, quantity, created_at, updated_at)
SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'items'
ORDER BY ORDINAL_POSITION;
