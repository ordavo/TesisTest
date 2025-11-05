USE Tesis;
GO

-- 🔹 Índices de rendimiento
CREATE INDEX IX_AuthorizedTags_UID ON dbo.AuthorizedTags (UID);
CREATE INDEX IX_UsedTags_UID ON dbo.UsedTags (UID);
CREATE INDEX IX_RFID_Sessions_SessionId ON dbo.RFID_Sessions (SessionId);
CREATE INDEX IX_RFID_Sessions_UID ON dbo.RFID_Sessions (UID);
CREATE INDEX IX_LogAccesos_UID ON dbo.LogAccesos (UID);
GO