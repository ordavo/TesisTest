# tests/conftest.py
import types
import binascii
import hmac, hashlib
from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient

# Importa la app y utilidades
import main as appmod  # <- tu main.py

@pytest.fixture(autouse=True)
def no_real_db(monkeypatch):
    """
    Mockea get_db() para no tocar SQL Server.
    Emula un cursor con respuestas mínimas por endpoint.
    """
    class FakeCursor:
        def __init__(self, store):
            self.store = store
            self.last_exec = None
            self.rowcount = 0
            self._select_buffer = []

        def execute(self, sql, params=()):
            self.last_exec = (sql, params)
            # Ruteo "naive" por frase clave:
            if "INSERT INTO RFID_Sessions" in sql:
                sid, uid, nonce, expire = params
                self.store["sessions"][sid] = {
                    "uid": uid,
                    "nonce": bytes(nonce),
                    "expire_at": expire
                }
                self.rowcount = 1
            elif "SELECT Nonce, ExpireAt FROM RFID_Sessions WHERE SessionId" in sql:
                sid = params[0]
                s = self.store["sessions"].get(sid)
                if s:
                    self._select_buffer = [(s["nonce"], s["expire_at"])]
                else:
                    self._select_buffer = []
            elif "DELETE FROM RFID_Sessions WHERE SessionId" in sql:
                sid = params[0]
                self.store["sessions"].pop(sid, None)
                self.rowcount = 1
            elif "INSERT INTO LogAccesos" in sql:
                uid = params[0]
                self.store["logs"].append({"uid": uid, "sql": sql})
                self.rowcount = 1
            elif "SELECT IdUsuario, Activa FROM AuthorizedTags WHERE UID" in sql:
                uid = params[0]
                # existe y activa
                tag = appmod.pyodbc  # solo para diferenciar mock vs real
                self._select_buffer = [(1, True)] if uid in ["C59B3706", "A1B2C3D4"] else []
            elif "INSERT INTO UsedTags" in sql:
                self.rowcount = 1
            elif "SELECT TOP" in sql and "FROM dbo.LogAccesos" in sql:
                # listar logs
                items = self.store["logs"]
                now = datetime.utcnow()
                # simulamos 1 fila
                self._select_buffer = [(1, "C59B3706", "DENIED", "HMAC_INVALIDO", now)]
            elif "INSERT INTO dbo.UsedAliases" in sql:
                uid, alias = params
                if alias in self.store["aliases"]:
                    # simular colisión UNIQUE
                    raise appmod.pyodbc.Error("UNIQUE VIOLATION")
                self.store["aliases"].add(alias)
                self.rowcount = 1
            elif "UPDATE dbo.AuthorizedTags" in sql and "CurrentAlias" in sql:
                self.rowcount = 1

            return self

        def fetchone(self):
            if not self._select_buffer:
                return None
            return self._select_buffer.pop(0)

        def fetchall(self):
            out = list(self._select_buffer)
            self._select_buffer.clear()
            return out

        def close(self):
            pass

    class FakeConn:
        def __init__(self, store):
            self.store = store
        def cursor(self):
            return FakeCursor(self.store)
        def commit(self): pass
        def close(self): pass

    store = {"sessions": {}, "logs": [], "aliases": set()}

    def fake_get_db():
        return FakeConn(store)

    monkeypatch.setattr(appmod, "get_db", fake_get_db)
    # Evita que rotate_alias intente re-intentar infinitamente en colisiones
    # (dejamos su lógica tal como está; el mock de cursor ya maneja colisión una vez)

@pytest.fixture
def client():
    from main import app
    return TestClient(app)
