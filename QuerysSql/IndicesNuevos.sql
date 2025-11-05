USE Tesis;
GO

-- 1) Columna opcional para ver el alias vigente del tag
IF COL_LENGTH('dbo.AuthorizedTags','CurrentAlias') IS NULL
ALTER TABLE dbo.AuthorizedTags
ADD CurrentAlias NVARCHAR(16) NULL,      -- alias actual en hex (8 bytes -> 16 chars)
    LastRotated DATETIME2 NULL;          -- cuándo se generó el alias

-- 2) Historial de alias rotados (para no reutilizar nunca)
IF OBJECT_ID('dbo.UsedAliases') IS NOT NULL DROP TABLE dbo.UsedAliases;
CREATE TABLE dbo.UsedAliases (
    Id INT IDENTITY(1,1) PRIMARY KEY,
    UID NVARCHAR(64) NOT NULL,           -- UID físico (texto hex)
    Alias NVARCHAR(16) NOT NULL,         -- alias generado (hex)
    CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT UQ_UsedAliases_Alias UNIQUE (Alias)  -- jamás reutilizar un alias
);

-- 3) Índices útiles
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_AuthorizedTags_UID' AND object_id=OBJECT_ID('dbo.AuthorizedTags'))
CREATE INDEX IX_AuthorizedTags_UID ON dbo.AuthorizedTags(UID);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_UsedAliases_UID' AND object_id=OBJECT_ID('dbo.UsedAliases'))
CREATE INDEX IX_UsedAliases_UID ON dbo.UsedAliases(UID);
GO


-- En SQL Server
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_LogAccesos_Fecha' AND object_id=OBJECT_ID('dbo.LogAccesos'))
CREATE INDEX IX_LogAccesos_Fecha ON dbo.LogAccesos(Fecha DESC, IdLog DESC);


IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_LogAccesos_Fecha' AND object_id=OBJECT_ID('dbo.LogAccesos'))
CREATE INDEX IX_LogAccesos_Fecha ON dbo.LogAccesos(Fecha DESC, IdLog DESC);


IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_RFID_Sessions_CreatedAt' AND object_id=OBJECT_ID('dbo.RFID_Sessions'))
CREATE INDEX IX_RFID_Sessions_CreatedAt ON dbo.RFID_Sessions (CreatedAt DESC);
