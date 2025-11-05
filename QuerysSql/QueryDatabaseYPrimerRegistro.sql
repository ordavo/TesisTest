USE Tesis;
GO

-- Tabla de usuarios
IF OBJECT_ID('dbo.Usuarios') IS NOT NULL DROP TABLE dbo.Usuarios;
CREATE TABLE dbo.Usuarios (
    IdUsuario INT IDENTITY(1,1) PRIMARY KEY,
    Nombre NVARCHAR(150) NOT NULL,
    Correo NVARCHAR(250) NOT NULL,
    FechaRegistro DATETIME2 DEFAULT SYSUTCDATETIME()
);
GO

-- Tabla con tags autorizados, vinculada al usuario
IF OBJECT_ID('dbo.AuthorizedTags') IS NOT NULL DROP TABLE dbo.AuthorizedTags;
CREATE TABLE dbo.AuthorizedTags (
    IdTag INT IDENTITY(1,1) PRIMARY KEY,
    UID NVARCHAR(64) NOT NULL UNIQUE,    -- UID en hex (ej: "C59B3706")
    IdUsuario INT NOT NULL,
    Activa BIT NOT NULL DEFAULT 1,
    FechaAlta DATETIME2 DEFAULT SYSUTCDATETIME(),
    CONSTRAINT FK_AuthorizedTags_Usuarios FOREIGN KEY (IdUsuario) REFERENCES dbo.Usuarios(IdUsuario)
);
GO

-- Tabla para almacenar UIDs ya utilizados / revocados (evita reuso)
IF OBJECT_ID('dbo.UsedTags') IS NOT NULL DROP TABLE dbo.UsedTags;
CREATE TABLE dbo.UsedTags (
    IdUsed INT IDENTITY(1,1) PRIMARY KEY,
    UID NVARCHAR(64) NOT NULL,           -- UID en hex que fue usado
    IdUsuario INT NULL,                  -- optional: quien lo usó
    Motivo NVARCHAR(200) NULL,
    FechaUsado DATETIME2 DEFAULT SYSUTCDATETIME(),
    CONSTRAINT FK_UsedTags_Usuarios FOREIGN KEY (IdUsuario) REFERENCES dbo.Usuarios(IdUsuario)
);
GO

-- Tabla de sesiones/nonces (para challenge-response)
IF OBJECT_ID('dbo.RFID_Sessions') IS NOT NULL DROP TABLE dbo.RFID_Sessions;
CREATE TABLE dbo.RFID_Sessions (
    SessionId UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    UID NVARCHAR(64) NOT NULL,
    Nonce VARBINARY(64) NOT NULL,
    CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    ExpireAt DATETIME2 NOT NULL
);
GO

-- Tabla opcional para registrar logs / accesos
IF OBJECT_ID('dbo.LogAccesos') IS NOT NULL DROP TABLE dbo.LogAccesos;
CREATE TABLE dbo.LogAccesos (
    IdLog INT IDENTITY(1,1) PRIMARY KEY,
    UID NVARCHAR(64) NOT NULL,
    Resultado NVARCHAR(50) NOT NULL, -- OK / DENIED / ERROR
    Details NVARCHAR(400) NULL,
    Fecha DATETIME2 DEFAULT SYSUTCDATETIME()
);
GO


-- Insertar usuario (si no existe aún en la tabla Usuarios)
INSERT INTO Usuarios (Nombre, Correo)
VALUES ('Camilo Alvarez', 'camilo.alvarez@example.com');

-- Insertar UID autorizado y asociarlo al usuario
INSERT INTO AuthorizedTags (UID, IdUsuario, FechaAlta)
VALUES ('C59B3706', 1, SYSDATETIMEOFFSET() AT TIME ZONE 'SA Pacific Standard Time');
