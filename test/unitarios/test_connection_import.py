# test/unitarios/test_connection_import.py
import sys, types
import importlib

def test_connection_import_and_string():
    # 1) Stub de pyodbc ANTES de importar connection
    class DummyConn:
        def cursor(self): return self
        def execute(self, *_): return self
        def fetchall(self): return []
        def close(self): pass

    def fake_connect(cs):
        assert isinstance(cs, str) and "DRIVER=" in cs
        return DummyConn()

    sys.modules['pyodbc'] = types.SimpleNamespace(connect=fake_connect)

    # 2) Import limpio de connection usando el stub
    import connection as connmod
    importlib.reload(connmod)  # por si pytest precargó algo

    # 3) Afirmaciones mínimas
    assert isinstance(connmod.connection_string, str)
    assert "DRIVER=" in connmod.connection_string
