#!/usr/bin/env python3
"""
run_all_500.py

Ejecuta todos los tests secuencialmente y genera un CSV por test
cuando termina cada test. Por defecto hace 500 iteraciones por test.
"""

import os
import sys
import time
import csv
import argparse
from datetime import datetime

# Asegura import desde test/
PROJECT_ROOT = os.path.dirname(__file__)
TEST_DIR = os.path.join(PROJECT_ROOT, "test")
if TEST_DIR not in sys.path:
    sys.path.insert(0, TEST_DIR)

try:
    import rfid_client
except Exception as e:
    raise SystemExit(f"ERROR: no se pudo importar test/rfid_client.py: {e}")

# Resultado: carpeta donde se escribirán los CSV por test
RESULTS_DIR = os.path.join(TEST_DIR, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

# ====== Funciones unitarias (1 run) ======
def run_ok_once():
    UID = "C59B3706"
    t0 = time.time()
    try:
        session_id, nonce = rfid_client.get_nonce(UID)
        hmac_b = rfid_client.compute_hmac(UID, nonce)
        res = rfid_client.post_verify(UID, session_id, hmac_b)
        duration = time.time() - t0
        return {
            "result": res.get("result", ""),
            "reason": res.get("reason", ""),
            "alias": res.get("alias", ""),
            "error": "",
            "notes": "",
            "duration_s": f"{duration:.4f}"
        }
    except Exception as e:
        return {"result": "", "reason": "", "alias": "", "error": str(e), "notes": "exception", "duration_s": "0.0000"}

def run_denied_hmac_once():
    import os as _os
    UID = "C59B3706"
    t0 = time.time()
    try:
        session_id, nonce = rfid_client.get_nonce(UID)
        fake_hmac = _os.urandom(32)
        res = rfid_client.post_verify(UID, session_id, fake_hmac)
        duration = time.time() - t0
        return {
            "result": res.get("result", ""),
            "reason": res.get("reason", ""),
            "alias": res.get("alias", ""),
            "error": "",
            "notes": "HMAC aleatorio",
            "duration_s": f"{duration:.4f}"
        }
    except Exception as e:
        return {"result": "", "reason": "", "alias": "", "error": str(e), "notes": "denied_hmac_exception", "duration_s": "0.0000"}

def run_session_expired_once():
    UID = "C59B3706"
    t0 = time.time()
    try:
        session_id, nonce = rfid_client.get_nonce(UID)
        time.sleep(4.0)  # TTL=3s en la API; dormimos > TTL
        hmac_b = rfid_client.compute_hmac(UID, nonce)
        res = rfid_client.post_verify(UID, session_id, hmac_b)
        duration = time.time() - t0
        return {
            "result": res.get("result", ""),
            "reason": res.get("reason", ""),
            "alias": res.get("alias", ""),
            "error": "",
            "notes": "session_expired_sleep",
            "duration_s": f"{duration:.4f}"
        }
    except Exception as e:
        return {"result": "", "reason": "", "alias": "", "error": str(e), "notes": "session_expired_exception", "duration_s": "0.0000"}

def run_unauthorized_uid_once():
    UID = "DEADBEEF"
    t0 = time.time()
    try:
        session_id, nonce = rfid_client.get_nonce(UID)
        hmac_b = rfid_client.compute_hmac(UID, nonce)
        res = rfid_client.post_verify(UID, session_id, hmac_b)
        duration = time.time() - t0
        return {
            "result": res.get("result", ""),
            "reason": res.get("reason", ""),
            "alias": res.get("alias", ""),
            "error": "",
            "notes": "unauthorized_uid",
            "duration_s": f"{duration:.4f}"
        }
    except Exception as e:
        return {"result": "", "reason": "", "alias": "", "error": str(e), "notes": "unauthorized_exception", "duration_s": "0.0000"}

def run_burst_load_once(burst_n=20, sleep_between=0.02):
    UID = "C59B3706"
    t0 = time.time()
    oks = 0
    denies = 0
    errors = 0
    aliases = []
    for i in range(burst_n):
        try:
            sid, nonce = rfid_client.get_nonce(UID)
            hmac_b = rfid_client.compute_hmac(UID, nonce)
            res = rfid_client.post_verify(UID, sid, hmac_b)
            if res.get("result") == "OK":
                oks += 1
                if res.get("alias"):
                    aliases.append(res.get("alias"))
            else:
                denies += 1
        except Exception:
            errors += 1
        time.sleep(sleep_between)
    duration = time.time() - t0
    return {
        "result": f"BURST_OK={oks}",
        "reason": f"denied={denies}",
        "alias": ",".join(aliases[:5]),
        "error": "" if errors == 0 else f"errors={errors}",
        "notes": f"burst_n={burst_n}, sleep={sleep_between}",
        "duration_s": f"{duration:.4f}"
    }

# ====== Mapa de tests (nombre -> función unit run) ======
TEST_FUNCTIONS = {
    "test_ok_single": run_ok_once,
    "test_denied_hmac": run_denied_hmac_once,
    "test_session_expired": run_session_expired_once,
    "test_unauthorized_uid": run_unauthorized_uid_once,
    "test_burst_load": run_burst_load_once,
}

CSV_FIELDS = ["run_index", "timestamp_iso", "duration_s", "result", "reason", "alias", "error", "notes"]

def execute_test_n_times(test_name, func, n, burst_params=None, sleep_between_runs=0.0, progress_interval=50):
    """
    Ejecuta la función `func` n veces, acumula resultados y escribe CSV AL FINALIZAR.
    """
    rows = []
    print(f"-> Iniciando {test_name}: {n} iteraciones")
    for i in range(1, n + 1):
        started_at = datetime.utcnow().isoformat()
        try:
            if test_name == "test_burst_load":
                out = func(**(burst_params or {}))
            else:
                out = func()
        except Exception as e:
            out = {"result": "", "reason": "", "alias": "", "error": str(e), "notes": "exception", "duration_s": "0.0000"}

        row = {
            "run_index": i,
            "timestamp_iso": started_at,
            "duration_s": out.get("duration_s", "0.0000"),
            "result": out.get("result", ""),
            "reason": out.get("reason", ""),
            "alias": out.get("alias", ""),
            "error": out.get("error", ""),
            "notes": out.get("notes", ""),
        }
        rows.append(row)

        # imprimir progreso
        if i % progress_interval == 0 or i == n:
            print(f"[{test_name}] progreso: {i}/{n} (último result={row['result']} error={bool(row['error'])})")

        if sleep_between_runs:
            time.sleep(sleep_between_runs)

    # escribir CSV sólo al finalizar el test
    csv_path = os.path.join(RESULTS_DIR, f"{test_name}.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    print(f"-> Finalizado {test_name}. CSV escrito: {csv_path} (rows={len(rows)})")
    return {"test": test_name, "rows": len(rows), "csv": csv_path}

def run_all_tests(max_runs=500, tests_list=None, burst_n=20, burst_sleep=0.02, sleep_between_runs=0.0):
    if tests_list is None:
        tests_list = list(TEST_FUNCTIONS.keys())
    summary = []
    for test_name in tests_list:
        func = TEST_FUNCTIONS.get(test_name)
        if func is None:
            print(f"[WARN] Test desconocido: {test_name}. Se salta.")
            continue
        burst_params = {"burst_n": burst_n, "sleep_between": burst_sleep} if test_name == "test_burst_load" else None
        info = execute_test_n_times(
            test_name,
            func,
            n=max_runs,
            burst_params=burst_params,
            sleep_between_runs=sleep_between_runs
        )
        summary.append(info)
    return summary

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ejecuta todos los tests n veces y genera CSV por test.")
    parser.add_argument("--max", type=int, default=500, help="Número de iteraciones por test (default 500)")
    parser.add_argument("--tests", type=str, default=",".join(TEST_FUNCTIONS.keys()),
                        help=f"Lista CSV de tests a ejecutar. Disponibles: {','.join(TEST_FUNCTIONS.keys())}")
    parser.add_argument("--burst_n", type=int, default=20, help="burst_n interno para test_burst_load")
    parser.add_argument("--burst_sleep", type=float, default=0.02, help="sleep entre accesos dentro del burst")
    parser.add_argument("--sleep_between_runs", type=float, default=0.0, help="sleep entre cada iteración del test")
    args = parser.parse_args()

    tests_to_run = [t.strip() for t in args.tests.split(",") if t.strip()]
    print(f"Iniciando ejecución secuencial: tests={tests_to_run}, max_runs={args.max}")
    summary = run_all_tests(max_runs=args.max, tests_list=tests_to_run,
                            burst_n=args.burst_n, burst_sleep=args.burst_sleep,
                            sleep_between_runs=args.sleep_between_runs)
    print("\n=== Resumen ejecuciones ===")
    for s in summary:
        print(f"{s['test']}: rows={s['rows']} csv={s['csv']}")
    print("Todos los CSVs generados en", RESULTS_DIR)
