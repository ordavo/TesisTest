import pyodbc

# Parámetros de conexión
driver = "{ODBC Driver 17 for SQL Server}"
server = "DESKTOP-UOJSRMF"   # o "127.0.0.1"
database = "Tesis"
username = "sa"
password = "Guadual1t0"

# Crear cadena de conexión
connection_string = f"""
    DRIVER={driver};
    SERVER={server};
    DATABASE={database};
    UID={username};
    PWD={password};
    TrustServerCertificate=yes;
"""

try:
    # Conectar
    conn = pyodbc.connect(connection_string)
    print(" Conexión exitosa a SQL Server!")

    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sys.databases;")
    for row in cursor.fetchall():
        print(row)

except Exception as e:
    print(" Error al conectar:", e)
