# main.py
import os
import uuid
import binascii
import hmac
import hashlib
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from dotenv import load_dotenv
import pyodbc

load_dotenv()

# Cargar configuración desde .env
DRIVER = os.getenv("SQLSERVER_DRIVER", "{ODBC Driver 17 for SQL Server}")
SERVER = os.getenv("SQLSERVER_SERVER", "DESKTOP-UOJSRMF")
DATABASE = os.getenv("SQLSERVER_DB", "Tesis")
DB_USER = os.getenv("SQLSERVER_USER", "sa")
DB_PASS = os.getenv("SQLSERVER_PASS", "")
NONCE_TTL_SECONDS = int(os.getenv("NONCE_TTL_SECONDS", "10"))

# Conexión ODBC
CONN_STR = (
    f"DRIVER={DRIVER};"
    f"SERVER={SERVER};"
    f"DATABASE={DATABASE};"
    f"UID={DB_USER};"
    f"PWD={DB_PASS}"
)

app = FastAPI(title="RFID Auth API (FastAPI)")

# Pydantic model para POST /api/verify
class VerifyRequest(BaseModel):
    uid: str          # UID en hex (ej: "0C5B9B37")
    sessionId: str    # GUID string
    hmac: str         # HMAC en hex

def get_db_connection():
    # Abrir conexión pyodbc (caller debe cerrar)
    return pyodbc.connect(CONN_STR, autocommit=True)

def hex_to_bytes(hexstr: str) -> bytes:
    # eliminar posibles 0x o espacios
    s = hexstr.strip().lower()
    if s.startswith("0x"):
        s = s[2:]
    s = s.replace(" ", "")
    try:
        return binascii.unhexlify(s)
    except Exception as e:
        raise ValueError(f"hex inválido: {hexstr}")

@app.get("/api/nonce")
def get_nonce(uid: str = Query(..., description="UID en hex, p.ej. 0C5B9B37")):
    """
    Genera un nonce para el UID dado y lo guarda en la tabla RFID_Sessions.
    Retorna: {"sessionId":"<guid>", "nonce":"<hex>"}
    """
    try:
        uid_bin = hex_to_bytes(uid)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    session_id = str(uuid.uuid4())
    nonce = os.urandom(16)  # 16 bytes de nonce
    expire_at = datetime.utcnow() + timedelta(seconds=NONCE_TTL_SECONDS)

    # Insertar sesión en la tabla RFID_Sessions
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        # Asegúrate que tu tabla RFID_Sessions tiene columnas:
        # SessionId UNIQUEIDENTIFIER, UID VARBINARY(...), Nonce VARBINARY(...), CreatedAt DATETIME2, ExpireAt DATETIME2
        cur.execute("""
            INSERT INTO dbo.RFID_Sessions(SessionId, UID, Nonce, CreatedAt, ExpireAt)
            VALUES(?, ?, ?, SYSUTCDATETIME(), ?)
        """, (session_id, pyodbc.Binary(uid_bin), pyodbc.Binary(nonce), expire_at))
        cur.close()
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"DB error al crear nonce: {e}")
    conn.close()

    return {"sessionId": session_id, "nonce": binascii.hexlify(nonce).decode()}

@app.post("/api/verify")
def verify(req: VerifyRequest):
    """
    Recibe JSON { uid, sessionId, hmac }.
    Verifica HMAC calculado como HMAC_SHA256(KeySecret, UID_bin || nonce_bin).
    Devuelve {"result":"OK"} o {"result":"DENIED", "reason": "..."}.
    """
    # 1) validar y convertir
    try:
        uid_bin = hex_to_bytes(req.uid)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # sessionId (GUID) y hmac hex
    try:
        provided_hmac = binascii.unhexlify(req.hmac)
    except Exception:
        raise HTTPException(status_code=400, detail="HMAC hex inválido")

    conn = get_db_connection()
    try:
        cur = conn.cursor()

        # 2) recuperar nonce de la sesión y validar existencia/expiración
        cur.execute("SELECT Nonce, ExpireAt FROM dbo.RFID_Sessions WHERE SessionId = ?", (req.sessionId,))
        row = cur.fetchone()
        if not row:
            cur.close()
            conn.close()
            return {"result": "DENIED", "reason": "SESSION_INVALIDA"}

        nonce_bin = row[0]  # varbinary
        expire_at = row[1]
        if datetime.utcnow() > expire_at:
            # borrar la session y denegar
            cur.execute("DELETE FROM dbo.RFID_Sessions WHERE SessionId = ?", (req.sessionId,))
            cur.close()
            conn.close()
            return {"result": "DENIED", "reason": "SESSION_EXPIRADA"}

        # 3) recuperar la key secreta asociada al UID (tabla RFID_Tags)
        cur.execute("SELECT KeySecret FROM dbo.RFID_Tags WHERE UID = ? AND Enabled = 1", (pyodbc.Binary(uid_bin),))
        row2 = cur.fetchone()
        if not row2:
            cur.close()
            conn.close()
            return {"result": "DENIED", "reason": "UID_NO_REGISTRADO"}

        key_bin = bytes(row2[0])  # obtén los bytes de la columna varbinary

        # 4) calcular HMAC-SHA256 en el servidor: HMAC(key, UID || nonce)
        message = uid_bin + bytes(nonce_bin)
        hm = hmac.new(key_bin, message, hashlib.sha256).digest()

        # 5) comparar de forma segura
        if hmac.compare_digest(hm, provided_hmac):
            # éxito -> borrar sesión para evitar replay
            cur.execute("DELETE FROM dbo.RFID_Sessions WHERE SessionId = ?", (req.sessionId,))
            # opcional: registrar log en LogAccesos o tabla de auditoría
            cur.execute("""
                INSERT INTO dbo.LogAccesos (UID, HashHMAC, AccesoPermitido)
                VALUES (?, ?, 1)
            """, (pyodbc.Binary(uid_bin), pyodbc.Binary(provided_hmac)))
            cur.close()
            conn.close()
            return {"result": "OK"}
        else:
            # registrar intento fallido
            cur.execute("""
                INSERT INTO dbo.LogAccesos (UID, HashHMAC, AccesoPermitido)
                VALUES (?, ?, 0)
            """, (pyodbc.Binary(uid_bin), pyodbc.Binary(provided_hmac)))
            cur.close()
            conn.close()
            return {"result": "DENIED", "reason": "HMAC_INVALIDO"}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"DB error en verify: {e}")

