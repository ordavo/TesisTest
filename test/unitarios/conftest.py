# test/unitarios/conftest.py
from pathlib import Path
import sys
from datetime import datetime
import pytest
import importlib

# ----------------------------------------------------------
# 1  Asegura que se pueda importar main.py desde la raíz
# ----------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]  # .../Tesis
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient


# ----------------------------------------------------------
# 2  FakeCursor y FakeConn: BD simulada en memoria
# ----------------------------------------------------------
class FakeCursor:
    def __init__(self, store):
        self.store = store
        self.last_exec = None
        self.rowcount = 0
        self._select_buffer = []

    def execute(self, sql, params=()):
        self.last_exec = (sql, params)
        s = sql.lower().replace("[", "").replace("]", "")
        self.rowcount = 0
        self._select_buffer = []

        # --- RFID_Sessions ---
        if "insert into" in s and "rfid_session" in s:
            sid, uid, nonce, expire = params
            self.store["sessions"][sid] = {
                "uid": uid,
                "nonce": nonce,
                "expire_at": expire
            }
            self.rowcount = 1

        elif "select" in s and "rfid_session" in s and "sessionid" in s:
            sid = params[0]
            data = self.store["sessions"].get(sid)
            if data:
                self._select_buffer = [(data["nonce"], data["expire_at"])]
            else:
                self._select_buffer = []

        elif "delete" in s and "rfid_session" in s and "sessionid" in s:
            sid = params[0]
            self.store["sessions"].pop(sid, None)
            self.rowcount = 1

        # --- LogAccesos ---
        elif "insert into" in s and "logacces" in s:
            uid = params[0] if params else None
            self.store["logs"].append({"uid": uid, "sql": sql, "at": datetime.utcnow()})
            self.rowcount = 1

        elif "select" in s and "logacces" in s:
            now = datetime.utcnow()
            self._select_buffer = [(1, "C59B3706", "DENIED", "HMAC_INVALIDO", now)]

        # --- AuthorizedTags ---
        elif "select" in s and "authorizedtag" in s and "uid" in s:
            uid = params[0]
            if uid in ["C59B3706", "A1B2C3D4"]:
                self._select_buffer = [(1, True)]
            else:
                self._select_buffer = []

        elif "update" in s and "authorizedtag" in s and "currentalias" in s:
            self.rowcount = 1

        # --- UsedAliases ---
        elif "insert into" in s and "usedalias" in s:
            uid, alias = params[0], params[1]
            if alias in self.store["aliases"]:
                raise Exception("UNIQUE VIOLATION")
            self.store["aliases"].add(alias)
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

    def commit(self):
        pass

    def close(self):
        pass


def make_fake_get_db():
    """Crea una base de datos simulada nueva por prueba"""
    store = {"sessions": {}, "logs": [], "aliases": set()}

    def _get_db():
        return FakeConn(store)

    return _get_db


# ----------------------------------------------------------
# 3  Fixture 'client' accesible desde todos los tests
# ----------------------------------------------------------
@pytest.fixture
def client():
    """
    Crea un cliente FastAPI de pruebas con BD simulada y pyodbc falso.
    """
    import types
    import main as appmod
    importlib.reload(appmod)

    # --- Parche para pyodbc.Binary / Error ---
    if not hasattr(appmod, "pyodbc") or not hasattr(appmod.pyodbc, "Binary"):
        appmod.pyodbc = types.SimpleNamespace(
            Binary=lambda b: b,   # devuelve los bytes sin cambio
            Error=Exception       # evita errores de tipo pyodbc.Error
        )

    # Reemplaza el acceso real a BD por la fake
    appmod.get_db = make_fake_get_db()

    # Devuelve el cliente de prueba
    return TestClient(appmod.app)
