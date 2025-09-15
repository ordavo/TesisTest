from fastapi import FastAPI
import pyodbc

app = FastAPI()

# Configuración SQL Server
driver = "{ODBC Driver 17 for SQL Server}"
server = "localhost"
database = "Tesis"
username = "sa"
password = "Guadual1t0"

connection_string = f"""
    DRIVER={driver};
    SERVER={server};
    DATABASE={database};
    UID={username};
    PWD={password};
    TrustServerCertificate=yes;
"""

@app.get("/")
def home():
    return {"status": "Servidor en línea ✅"}

@app.get("/verificar/{uid}")
def verificar_uid(uid: str):
    try:
        conn = pyodbc.connect(connection_string)
        cursor = conn.cursor()
        cursor.execute("SELECT Activa FROM TarjetasNFC WHERE UID = ?", (uid,))
        row = cursor.fetchone()
        if row:
            if row[0] == 1:
                return {"autorizado": True, "uid": uid}
            else:
                return {"autorizado": False, "uid": uid, "motivo": "Tarjeta inactiva ❌"}
        else:
            return {"autorizado": False, "uid": uid, "motivo": "No registrada ❌"}
    except Exception as e:
        return {"status": "Error", "detalle": str(e)}
