# connection.py
import os

# Ajusta si usas otro driver
ODBC_DRIVER = os.getenv("ODBC_DRIVER", "{ODBC Driver 17 for SQL Server}")
SERVER      = os.getenv("SQLSERVER", "DESKTOP-UOJSRMF")   # "SERVER\\INSTANCIA" si aplica
DATABASE    = os.getenv("SQLDB", "Tesis")
USER        = os.getenv("SQLUSER", "sa")
PASSWORD    = os.getenv("SQLPWD", "Guadual1t0")

connection_string = (
    f"DRIVER={ODBC_DRIVER};"
    f"SERVER={SERVER};"
    f"DATABASE={DATABASE};"
    f"UID={USER};"
    f"PWD={PASSWORD};"
    "TrustServerCertificate=yes;"
)
