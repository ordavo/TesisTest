# main.py
import os, binascii, uuid, hmac, hashlib, time, threading
from datetime import datetime, timedelta
from typing import Optional, List, Dict

import pyodbc
from fastapi import FastAPI, HTTPException, Query, Form, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from connection import connection_string

# ================== CONFIG ==================
SECRET_KEY = b"MiEjemplo"
NONCE_TTL_SECONDS = 3  # segundos

# ================== DB POOL ==================
_pool_lock = threading.Lock()
_conn_pool = None

def get_db():
    """Reutiliza una única conexión; si muere, reconecta."""
    global _conn_pool
    with _pool_lock:
        if _conn_pool is None:
            _conn_pool = pyodbc.connect(connection_string, autocommit=True)
            return _conn_pool
        try:
            cur = _conn_pool.cursor()
            cur.execute("SELECT 1")
            cur.close()
            return _conn_pool
        except Exception:
            try:
                _conn_pool.close()
            except Exception:
                pass
            _conn_pool = pyodbc.connect(connection_string, autocommit=True)
            return _conn_pool

# ================== UTILS ==================
def hex_to_bytes(s: str) -> bytes:
    s = s.strip().replace(" ", "")
    if s.lower().startswith("0x"):
        s = s[2:]
    return binascii.unhexlify(s)

def bytes_to_hex(b: bytes) -> str:
    return binascii.hexlify(b).decode()

# ----- Alias dinámicos -----
def gen_alias_hex(nbytes: int = 8) -> str:
    """Genera alias aleatorio en hex (16 caracteres, 8 bytes)."""
    return binascii.hexlify(os.urandom(nbytes)).decode().upper()

def rotate_alias(conn, uid_text: str) -> str:
    """
    Crea alias nuevo y actualiza AuthorizedTags.
    Evita colisión por UNIQUE en UsedAliases.Alias (si choca, reintenta).
    """
    cur = conn.cursor()
    while True:
        alias = gen_alias_hex(8)
        try:
            cur.execute("""
                INSERT INTO dbo.UsedAliases (UID, Alias)
                VALUES (?, ?)
            """, (uid_text, alias))

            cur.execute("""
                UPDATE dbo.AuthorizedTags
                SET CurrentAlias = ?, LastRotated = SYSUTCDATETIME()
                WHERE UID = ? AND Activa = 1
            """, (alias, uid_text))

            if cur.rowcount == 0:
                # revertir si no existe tag activo
                cur.execute("DELETE FROM dbo.UsedAliases WHERE Alias = ?", (alias,))
                conn.commit()
                raise HTTPException(status_code=400, detail="UID no autorizado o inactivo")

            conn.commit()
            return alias

        except pyodbc.Error:
            # posible colisión: vuelve a intentar con otro alias
            continue

# ================== APP ==================
app = FastAPI(title="RFID Auth API (<2s)")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- CORS (abierto para la LAN) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Middleware de tiempo ---
@app.middleware("http")
async def log_time(request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    dur = time.perf_counter() - start
    print(f"[{request.url.path}] {dur:.3f}s")
    return response

# ================== MODELOS ==================
class VerifyReq(BaseModel):
    uid: str
    sessionId: str
    hmac: str

# ================== ENDPOINTS CORE ==================
# Salud
@app.get("/health")
def health():
    return {"ok": True, "time": datetime.utcnow().isoformat()}

# 1) NONCE
@app.get("/api/nonce")
def api_nonce(uid: str = Query(..., description="UID en hex (ej: C59B3706)")):
    try:
        _ = hex_to_bytes(uid)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"UID inválido: {e}")

    session_id = str(uuid.uuid4())
    nonce = os.urandom(16)
    expire_at = datetime.utcnow() + timedelta(seconds=NONCE_TTL_SECONDS)

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO RFID_Sessions (SessionId, UID, Nonce, CreatedAt, ExpireAt)
            VALUES (?, ?, ?, SYSUTCDATETIME(), ?)
        """, (session_id, uid, pyodbc.Binary(nonce), expire_at))
    except Exception as e:
        print("⚠ Error SQL /api/nonce:", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()

    return {"sessionId": session_id, "nonce": bytes_to_hex(nonce)}

# 2) VERIFY
@app.post("/api/verify")
def api_verify(req: VerifyReq):
    conn = get_db()
    cur = conn.cursor()
    try:
        uid_bin = hex_to_bytes(req.uid)
        try:
            provided_hmac = binascii.unhexlify(req.hmac)
        except Exception:
            return {"result": "DENIED", "reason": "HMAC_MALFORMADO"}

        # Sesión (ligada a UID)
        cur.execute("""
            SELECT Nonce, ExpireAt
            FROM RFID_Sessions
            WHERE SessionId = ? AND UID = ?
        """, (req.sessionId, req.uid))
        row = cur.fetchone()
        if not row:
            return {"result": "DENIED", "reason": "SESSION_INVALIDA"}

        nonce, expire_at = bytes(row[0]), row[1]
        if datetime.utcnow() > expire_at:
            cur.execute("DELETE FROM RFID_Sessions WHERE SessionId = ?", (req.sessionId,))
            conn.commit()
            return {"result": "DENIED", "reason": "SESSION_EXPIRADA"}

        # HMAC
        hm_server = hmac.new(SECRET_KEY, uid_bin + nonce, hashlib.sha256).digest()
        if not hmac.compare_digest(hm_server, provided_hmac):
            cur.execute(
                "INSERT INTO LogAccesos (UID, Resultado, Details) VALUES (?, 'DENIED', 'HMAC_INVALIDO')",
                (req.uid,),
            )
            conn.commit()
            return {"result": "DENIED", "reason": "HMAC_INVALIDO"}

        # Validación de autorización
        cur.execute("SELECT IdUsuario, Activa FROM AuthorizedTags WHERE UID = ?", (req.uid,))
        tag = cur.fetchone()
        if not tag or not tag[1]:
            cur.execute(
                "INSERT INTO LogAccesos (UID, Resultado, Details) VALUES (?, 'DENIED', 'NO_AUTORIZADO')",
                (req.uid,),
            )
            conn.commit()
            return {"result": "DENIED", "reason": "NO_AUTORIZADO"}

        id_usuario = tag[0]

        # Registrar OK y cerrar sesión
        cur.execute("INSERT INTO LogAccesos (UID, Resultado) VALUES (?, 'OK')", (req.uid,))
        cur.execute("DELETE FROM RFID_Sessions WHERE SessionId = ?", (req.sessionId,))
        # (Opcional) registrar uso del UID
        cur.execute(
            "INSERT INTO UsedTags (UID, IdUsuario, Motivo) VALUES (?, ?, 'Post-OK')",
            (req.uid, id_usuario),
        )
        conn.commit()

        # Rotación de alias
        new_alias = rotate_alias(conn, req.uid)
        return {"result": "OK", "alias": new_alias}

    except Exception as e:
        print("Error /api/verify:", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()

# 3) Registro de tarjeta
@app.post("/agregar_tarjeta")
def agregar_tarjeta(uid: str = Form(...), nombre: str = Form(...), correo: str = Form(...)):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT IdUsuario FROM Usuarios WHERE Nombre = ?", (nombre,))
        user = cur.fetchone()
        if not user:
            cur.execute("INSERT INTO Usuarios (Nombre, Correo) VALUES (?, ?)", (nombre, correo))
            cur.execute("SELECT IdUsuario FROM Usuarios WHERE Nombre = ?", (nombre,))
            user = cur.fetchone()
        id_usuario = user[0]

        cur.execute(
            "INSERT INTO AuthorizedTags (UID, IdUsuario, Activa) VALUES (?, ?, 1)",
            (uid, id_usuario),
        )
        conn.commit()
        return {"mensaje": f"Tarjeta {uid} vinculada al usuario {nombre}"}
    except Exception as e:
        return {"error": str(e)}
    finally:
        cur.close()

# 4) Listado de logs (para /mostrar)
@app.get("/api/logs")
def api_logs(
    response: Response,
    uid: Optional[str] = Query(None, description="UID en hex opcional"),
    limit: int = Query(50, ge=1, le=500),
):
    # Evita caché
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"

    cur = get_db().cursor()
    try:
        if uid:
            cur.execute(f"""
                SELECT TOP ({limit}) IdLog, UID, Resultado, ISNULL(Details,''), Fecha
                FROM dbo.LogAccesos
                WHERE UID = ?
                ORDER BY Fecha DESC, IdLog DESC
            """, (uid,))
        else:
            cur.execute(f"""
                SELECT TOP ({limit}) IdLog, UID, Resultado, ISNULL(Details,''), Fecha
                FROM dbo.LogAccesos
                ORDER BY Fecha DESC, IdLog DESC
            """)

        rows = cur.fetchall()
        data: List[Dict] = []
        for r in rows:
            data.append({
                "id": r[0],
                "uid": r[1],
                "resultado": r[2],
                "details": r[3],
                "fecha": r[4].isoformat() if r[4] else None
            })
        return {"count": len(data), "items": data}
    finally:
        cur.close()

# 5) Último log (compatibilidad)
@app.get("/api/logs/last")
def api_logs_last(uid: Optional[str] = Query(None, description="UID en hex opcional")):
    cur = get_db().cursor()
    try:
        if uid:
            cur.execute("""
                SELECT TOP 1 IdLog, UID, Resultado, ISNULL(Details,''), Fecha
                FROM dbo.LogAccesos
                WHERE UID = ?
                ORDER BY Fecha DESC, IdLog DESC
            """, (uid,))
        else:
            cur.execute("""
                SELECT TOP 1 IdLog, UID, Resultado, ISNULL(Details,''), Fecha
                FROM dbo.LogAccesos
                ORDER BY Fecha DESC, IdLog DESC
            """)
        row = cur.fetchone()
        if not row:
            return {"hasData": False}
        idlog, ruid, resu, det, fecha = row
        return {
            "hasData": True,
            "id": idlog,
            "uid": ruid,
            "resultado": resu,
            "details": det,
            "fecha": fecha.isoformat()
        }
    finally:
        cur.close()

# 6) Último UID de sesiones recientes
@app.get("/api/ultimo-uid")
def ultimo_uid(seconds: int = 10):
    """
    Devuelve el último UID leído en RFID_Sessions.
    'seconds' = ventana máxima de antigüedad (por defecto 10 s).
    Respuesta: { "found": true/false, "uid": "E2894106", "createdAt": "..." }
    """
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT TOP 1 UID, CreatedAt
            FROM dbo.RFID_Sessions
            ORDER BY CreatedAt DESC
        """)
        row = cur.fetchone()
        if not row:
            return {"found": False}

        uid, created_at = row
        # created_at proviene de SYSUTCDATETIME() (UTC naive)
        if (datetime.utcnow() - created_at).total_seconds() <= seconds:
            return {"found": True, "uid": uid, "createdAt": created_at.isoformat()}
        else:
            return {"found": False, "createdAt": created_at.isoformat()}
    finally:
        cur.close()

# ================== VISTAS ==================
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/mostrar", response_class=HTMLResponse)
def mostrar_uid(request: Request):
    return templates.TemplateResponse("mostrar.html", {"request": request})

@app.get("/registrar", response_class=HTMLResponse)
def registrar_uid(request: Request):
    return templates.TemplateResponse("registrar.html", {"request": request})

@app.get("/rechazado", response_class=HTMLResponse)
def acceso_rechazado(request: Request):
    return HTMLResponse("""
    <html><body style="font-family:Arial;text-align:center;background:#fee;">
    <h1 style="color:#d00;">❌ Acceso denegado</h1>
    <p>Tiempo expirado o cancelado.</p>
    </body></html>
    """)
