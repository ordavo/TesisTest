from fastapi import FastAPI
import pyodbc

app = FastAPI()

driver = "{ODBC Driver 17 for SQL Server}"
server = "localhost"
database = "Tesis"
username = "sa"
password = "tu_password_segura"

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

@app.post("/guardar_uid/{uid}")
def guardar_uid(uid: str):
    try:
        conn = pyodbc.connect(connection_string)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO TarjetasNFC (UID) VALUES (?)", (uid,))
        conn.commit()
        return {"status": "OK", "uid": uid}
    except Exception as e:
        return {"status": "Error", "detalle": str(e)}

@app.get("/test")
async def test_connection():
    return {"status": "ok", "message": "ESP32 conectado correctamente 🚀"}
