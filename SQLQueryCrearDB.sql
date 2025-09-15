USE master;
IF DB_ID('Tesis') IS NULL
BEGIN
    CREATE DATABASE Tesis;
END
GO

USE Tesis;
GO

-- 1) Tabla de tags: UID (varbinary) y Clave secreta (varbinary)
IF OBJECT_ID('dbo.RFID_Tags') IS NOT NULL DROP TABLE dbo.RFID_Tags;
CREATE TABLE dbo.RFID_Tags (
    TagId INT IDENTITY PRIMARY KEY,
    UID VARBINARY(16) NOT NULL,          -- UID (4 bytes típicos)
    KeySecret VARBINARY(64) NOT NULL,    -- Clave (hasta 64 bytes)
    Enabled BIT NOT NULL DEFAULT 1
);
GO

-- 2) Tabla de sesiones/nonces (para evitar replay)
IF OBJECT_ID('dbo.RFID_Sessions') IS NOT NULL DROP TABLE dbo.RFID_Sessions;
CREATE TABLE dbo.RFID_Sessions (
    SessionId UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    UID VARBINARY(16) NOT NULL,
    Nonce VARBINARY(64) NOT NULL,
    CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    ExpireAt DATETIME2 NOT NULL
);
GO

-- 3) Función auxiliar: XOR de dos VARBINARY del mismo tamaño
IF OBJECT_ID('dbo.fn_XorBytes') IS NOT NULL DROP FUNCTION dbo.fn_XorBytes;
GO
CREATE FUNCTION dbo.fn_XorBytes(@a VARBINARY(8000), @b VARBINARY(8000))
RETURNS VARBINARY(8000)
AS
BEGIN
    DECLARE @len INT = CASE WHEN DATALENGTH(@a) < DATALENGTH(@b) THEN DATALENGTH(@a) ELSE DATALENGTH(@b) END;
    IF @len IS NULL OR @len = 0 RETURN 0x;

    DECLARE @i INT = 1;
    DECLARE @r VARBINARY(8000) = 0x;
    WHILE @i <= @len
    BEGIN
        -- obtener el byte i de cada varbinary
        DECLARE @ba INT = CAST(SUBSTRING(@a, @i, 1) AS INT);
        DECLARE @bb INT = CAST(SUBSTRING(@b, @i, 1) AS INT);
        DECLARE @bx INT = @ba ^ @bb;
        SET @r = @r + CAST(@bx AS BINARY(1));
        SET @i += 1;
    END
    RETURN @r;
END
GO

-- 4) Función HMAC-SHA256 (implementación en T-SQL)
-- Usa HASHBYTES('SHA2_256', ...)
IF OBJECT_ID('dbo.fn_HMAC_SHA256') IS NOT NULL DROP FUNCTION dbo.fn_HMAC_SHA256;
GO
CREATE FUNCTION dbo.fn_HMAC_SHA256(@key VARBINARY(8000), @message VARBINARY(MAX))
RETURNS VARBINARY(32)
AS
BEGIN
    -- SHA-256 block size = 64 bytes
    DECLARE @blockSize INT = 64;
    DECLARE @k VARBINARY(8000) = @key;

    -- If key length > blockSize, key = SHA256(key)
    IF (DATALENGTH(@k) > @blockSize)
    BEGIN
        SET @k = HASHBYTES('SHA2_256', @k);
    END

    -- pad key with zeros to blockSize
    IF (DATALENGTH(@k) < @blockSize)
    BEGIN
        SET @k = @k + (CONVERT(VARBINARY(8000), 0x) + REPLICATE(CAST(0x00 AS VARBINARY(1)), @blockSize - DATALENGTH(@k)));
        -- The expression above ensures padding to @blockSize
        -- But REPLICATE on binary not straightforward; do this:
        SET @k = @k + CAST(REPLICATE(CHAR(0), @blockSize - DATALENGTH(@k)) AS VARBINARY(@blockSize - DATALENGTH(@k)));
    END

    -- prepare ipad/opad
    DECLARE @ipad VARBINARY(64) = 0x;
    DECLARE @opad VARBINARY(64) = 0x;
    DECLARE @i INT = 1;
    WHILE @i <= @blockSize
    BEGIN
        SET @ipad = @ipad + CAST(0x36 AS BINARY(1));
        SET @opad = @opad + CAST(0x5C AS BINARY(1));
        SET @i += 1;
    END

    DECLARE @k_xor_ipad VARBINARY(8000) = dbo.fn_XorBytes(@k, @ipad);
    DECLARE @k_xor_opad VARBINARY(8000) = dbo.fn_XorBytes(@k, @opad);

    DECLARE @innerInput VARBINARY(MAX) = @k_xor_ipad + ISNULL(@message, 0x);
    DECLARE @innerHash VARBINARY(32) = HASHBYTES('SHA2_256', @innerInput);

    DECLARE @outerInput VARBINARY(MAX) = @k_xor_opad + @innerHash;
    DECLARE @outerHash VARBINARY(32) = HASHBYTES('SHA2_256', @outerInput);

    RETURN @outerHash;
END
GO

-- 5) Procedimiento para generar nonce (lo devolverá un GUID de sesión)
IF OBJECT_ID('dbo.sp_GenerarNonce') IS NOT NULL DROP PROCEDURE dbo.sp_GenerarNonce;
GO
CREATE PROCEDURE dbo.sp_GenerarNonce
    @UID VARBINARY(16),
    @TTLSeconds INT = 10,              -- tiempo de validez del nonce
    @SessionId UNIQUEIDENTIFIER OUTPUT,
    @NonceHex VARCHAR(256) OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @nonce VARBINARY(64) = CAST(CRYPT_GEN_RANDOM(16) AS VARBINARY(16)) + CAST(CRYPT_GEN_RANDOM(8) AS VARBINARY(8)); -- 24 bytes
    DECLARE @expire DATETIME2 = DATEADD(SECOND, @TTLSeconds, SYSUTCDATETIME());
    SET @SessionId = NEWID();

    INSERT INTO dbo.RFID_Sessions (SessionId, UID, Nonce, CreatedAt, ExpireAt)
    VALUES (@SessionId, @UID, @nonce, SYSUTCDATETIME(), @expire);

    SET @NonceHex = LOWER(CONVERT(VARCHAR(MAX), @nonce, 2)); -- hex string
END
GO

-- 6) Procedimiento para verificar HMAC enviado por lector
IF OBJECT_ID('dbo.sp_VerificarHmac') IS NOT NULL DROP PROCEDURE dbo.sp_VerificarHmac;
GO
CREATE PROCEDURE dbo.sp_VerificarHmac
    @UID VARBINARY(16),        -- UID del tag
    @SessionId UNIQUEIDENTIFIER,
    @HmacHex VARCHAR(128),     -- hmac en hex (hex string)
    @Resultado VARCHAR(50) OUTPUT
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @rowKey VARBINARY(64);
    SELECT TOP(1) @rowKey = KeySecret FROM dbo.RFID_Tags WHERE UID = @UID AND Enabled = 1;

    IF @rowKey IS NULL
    BEGIN
        SET @Resultado = 'UID_NO_REGISTRADO';
        RETURN;
    END

    -- Obtener nonce de la sesión y validar expiración
    DECLARE @nonce VARBINARY(64), @expire DATETIME2;
    SELECT @nonce = Nonce, @expire = ExpireAt FROM dbo.RFID_Sessions WHERE SessionId = @SessionId;

    IF @nonce IS NULL
    BEGIN
        SET @Resultado = 'SESSION_INVALIDA';
        RETURN;
    END

    IF SYSUTCDATETIME() > @expire
    BEGIN
        SET @Resultado = 'SESSION_EXPIRADA';
        RETURN;
    END

    -- Mensaje que se firmó: en este ejemplo usamos (UID || nonce) como binario
    DECLARE @message VARBINARY(MAX) = @UID + @nonce;

    DECLARE @hmacServer VARBINARY(32) = dbo.fn_HMAC_SHA256(@rowKey, @message);

    -- Convertir HMACHex del cliente a varbinary
    DECLARE @hmacCliente VARBINARY(32) = CONVERT(VARBINARY(32), @HmacHex, 2);

    IF @hmacServer = @hmacCliente
    BEGIN
        SET @Resultado = 'OK';
        -- eliminar la session para evitar reuso
        DELETE FROM dbo.RFID_Sessions WHERE SessionId = @SessionId;
    END
    ELSE
    BEGIN
        SET @Resultado = 'HMAC_INVALIDO';
    END
END
GO

-- 7) Ejemplo: insertar un tag (UID en hex) con clave secreta (hex)
-- Reemplaza clave hex por un valor seguro generado
-- Ejemplo: UID 0xA1B2C3D4 (4 bytes)
INSERT INTO dbo.RFID_Tags (UID, KeySecret)
VALUES (0xA1B2C3D4, CONVERT(VARBINARY(64), '5365677572302D323032352D4B657921', 2)); -- ejemplo de clave en hex (Secur0-2025-Key!)
GO






CREATE TABLE TarjetasNFC (
    Id INT IDENTITY(1,1) PRIMARY KEY,
    UID VARCHAR(50) NOT NULL,
    FechaRegistro DATETIME DEFAULT GETDATE()
);

USE Tesis;
GO

-- Tabla de usuarios autorizados (tarjetas NFC registradas)
IF OBJECT_ID('dbo.UsuariosNFC') IS NOT NULL DROP TABLE dbo.UsuariosNFC;
CREATE TABLE dbo.UsuariosNFC (
    IdUsuario INT IDENTITY(1,1) PRIMARY KEY,
    Nombre NVARCHAR(100) NOT NULL,
    UID VARBINARY(16) NOT NULL UNIQUE,  -- UID de la tarjeta NFC
    FechaRegistro DATETIME DEFAULT GETDATE()
);
GO

-- Tabla de logs de accesos (cada intento de lectura de tarjeta)
IF OBJECT_ID('dbo.LogAccesos') IS NOT NULL DROP TABLE dbo.LogAccesos;
CREATE TABLE dbo.LogAccesos (
    IdLog INT IDENTITY(1,1) PRIMARY KEY,
    UID VARBINARY(16) NOT NULL,         -- UID leído
    HashHMAC VARBINARY(64) NOT NULL,    -- Hash enviado por ESP32
    AccesoPermitido BIT NOT NULL,       -- 1 = acceso válido, 0 = denegado
    Fecha DATETIME DEFAULT GETDATE()    -- Momento del intento
);
GO







USE Tesis;
GO

----------------------------------------------------------
-- 1) Función auxiliar para hacer XOR de dos varbinary
----------------------------------------------------------
IF OBJECT_ID('dbo.fn_XorBytes') IS NOT NULL DROP FUNCTION dbo.fn_XorBytes;
GO
CREATE FUNCTION dbo.fn_XorBytes(@a VARBINARY(8000), @b VARBINARY(8000))
RETURNS VARBINARY(8000)
AS
BEGIN
    DECLARE @len INT = CASE WHEN DATALENGTH(@a) < DATALENGTH(@b) THEN DATALENGTH(@a) ELSE DATALENGTH(@b) END;
    DECLARE @i INT = 1;
    DECLARE @result VARBINARY(8000) = 0x;

    WHILE @i <= @len
    BEGIN
        SET @result = @result + 
            CAST(
                CONVERT(BINARY(1), SUBSTRING(@a, @i, 1)) 
                ^ 
                CONVERT(BINARY(1), SUBSTRING(@b, @i, 1))
            AS BINARY(1));
        SET @i += 1;
    END

    RETURN @result;
END
GO

----------------------------------------------------------
-- 2) Función HMAC-SHA256
----------------------------------------------------------
IF OBJECT_ID('dbo.fn_HMAC_SHA256') IS NOT NULL DROP FUNCTION dbo.fn_HMAC_SHA256;
GO
CREATE FUNCTION dbo.fn_HMAC_SHA256(@key VARBINARY(8000), @message VARBINARY(MAX))
RETURNS VARBINARY(32)
AS
BEGIN
    DECLARE @blockSize INT;
    SET @blockSize = 64;  -- SHA-256 trabaja en bloques de 64 bytes

    DECLARE @k VARBINARY(8000);
    SET @k = @key;

    -- Si la clave es mayor al blocksize, se reduce con SHA256
    IF (DATALENGTH(@k) > @blockSize)
        SET @k = HASHBYTES('SHA2_256', @k);

    -- Si la clave es menor, se rellena con ceros hasta blocksize
    IF (DATALENGTH(@k) < @blockSize)
        SET @k = @k + CAST(REPLICATE(CHAR(0), @blockSize - DATALENGTH(@k)) AS VARBINARY(8000));

    -- Preparar ipad y opad
    DECLARE @ipad VARBINARY(64) = CAST(REPLICATE(CHAR(0x36), @blockSize) AS VARBINARY(64));
    DECLARE @opad VARBINARY(64) = CAST(REPLICATE(CHAR(0x5C), @blockSize) AS VARBINARY(64));

    -- XOR de clave con ipad y opad
    DECLARE @k_xor_ipad VARBINARY(8000) = dbo.fn_XorBytes(@k, @ipad);
    DECLARE @k_xor_opad VARBINARY(8000) = dbo.fn_XorBytes(@k, @opad);

    -- Calcular HMAC
    DECLARE @innerHash VARBINARY(32) = HASHBYTES('SHA2_256', @k_xor_ipad + ISNULL(@message, 0x));
    DECLARE @outerHash VARBINARY(32) = HASHBYTES('SHA2_256', @k_xor_opad + @innerHash);

    RETURN @outerHash;
END
GO

----------------------------------------------------------
-- 3) Ejemplo de uso
----------------------------------------------------------
DECLARE @key VARBINARY(8000) = CONVERT(VARBINARY(8000), 'clave_secreta');
DECLARE @msg VARBINARY(MAX) = CONVERT(VARBINARY(MAX), 'mensaje123');

SELECT dbo.fn_HMAC_SHA256(@key, @msg) AS HMAC_Resultado;
GO




INSERT INTO TarjetasNFC (UID) VALUES ('0xC5 0x9B 0x37 0x6');
INSERT INTO TarjetasNFC (UID) VALUES ('0xE2 0x89 0x41 0x6');



