#!/usr/bin/env python3
"""
run_tests_bulk.py

Ejecuta múltiples pruebas definidas contra la API RFID y genera un CSV por prueba
con el resultado de cada ejecución. Por defecto ejecuta hasta 500 repeticiones por prueba.
"""

import os
import time
import csv
import argparse
from datetime import datetime
import binascii
import os as _os

# Importa el cliente reutilizable en test/rfid_client.py
import importlib.util
import sys
PROJECT_ROOT = os.path.dirname(__file__)
TEST_DIR = os.path.join(PROJECT_ROOT, "test")
if TEST_DIR not in sys.path:
    sys.path.insert(0, TEST_DIR)

try:
    import rfid_client
except Exception as e:
    raise SystemExit(f"No se pudo importar test/rfid_client.py: {e}")

# ====== Config ======
RESULTS_DIR = os.path.join(TEST_DIR, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

# Tests disponibles: cada función realiza UNA ejecución y devuelve un dict con keys:
#   result, reason, alias, error, notes
# Si quieres añadir tests nuevos, añade una función con la misma sig.
def test_ok_once():
    """Un run del caso OK (equivalente a test_ok_single.py)."""
    UID = "C59B3706"
    try:
        t0 = time.time()
        session_id, nonce = rfid_client.get_nonce(UID)
        hmac_b = rfid_client.compute_hmac(UID, nonce)
        res = rfid_client.post_verify(UID, session_id, hmac_b)
        dur = time.time() - t0
        return {
            "result": res.get("result"),
            "reason": res.get("reason") if res.get("reason") else "",
            "alias": res.get("alias") if res.get("alias") else "",
            "error": "",
            "notes": "",
            "duration_s": dur
        }
    except Exception as e:
        return {"result": "", "reason": "", "alias": "", "error": str(e), "notes": "", "duration_s": 0.0}

def test_denied_hmac_once():
    """Un run del caso HMAC inválido (random HMAC)."""
    import os as _os
    UID = "C59B3706"
    try:
        t0 = time.time()
        session_id, nonce = rfid_client.get_nonce(UID)
        fake_hmac = _os.urandom(32)
        res = rfid_client.post_verify(UID, session_id, fake_hmac)
        dur = time.time() - t0
        return {
            "result": res.get("result"),
            "reason": res.get("reason") if res.get("reason") else "",
            "alias": res.get("alias") if res.get("alias") else "",
            "error": "",
            "notes": "HMAC aleatorio enviado",
            "duration_s": dur
        }
    except Exception as e:
        return {"result": "", "reason": "", "alias": "", "error": str(e), "notes": "HMAC aleatorio", "duration_s": 0.0}

def test_session_expired_once():
    """Un run del caso sesión expirada (espera > TTL)."""
    UID = "C59B3706"
    try:
        t0 = time.time()
        session_id, nonce = rfid_client.get_nonce(UID)
        # Espera para que expire. TTL en tu API es 3s; usamos 4s.
        time.sleep(4.0)
        hmac_b = rfid_client.compute_hmac(UID, nonce)
        res = rfid_client.post_verify(UID, session_id, hmac_b)
        dur = time.time() - t0
        return {
            "result": res.get("result"),
            "reason": res.get("reason") if res.get("reason") else "",
            "alias": res.get("alias") if res.get("alias") else "",
            "error": "",
            "notes": "Se durmió > TTL para provocar expiración",
            "duration_s": dur
        }
    except Exception as e:
        return {"result": "", "reason": "", "alias": "", "error": str(e), "notes": "session_expired", "duration_s": 0.0}

def test_unauthorized_uid_once():
    """Un run del caso UID no autorizado."""
    UID = "DEADBEEF"
    try:
        t0 = time.time()
        session_id, nonce = rfid_client.get_nonce(UID)
        hmac_b = rfid_client.compute_hmac(UID, nonce)
        res = rfid_client.post_verify(UID, session_id, hmac_b)
        dur = time.time() - t0
        return {
            "result": res.get("result"),
            "reason": res.get("reason") if res.get("reason") else "",
            "alias": res.get("alias") if res.get("alias") else "",
            "error": "",
            "notes": "UID no autorizado",
            "duration_s": dur
        }
    except Exception as e:
        return {"result": "", "reason": "", "alias": "", "error": str(e), "notes": "unauthorized_uid", "duration_s": 0.0}

def test_burst_load_once(burst_n=20, sleep_between=0.02):
    """
    Ejecuta un mini-burst interno: N accesos válidos seguidos (cada uno hace nonce->verify).
    Devuelve resumen agregado del burst (oks, denies, errores).
    """
    UID = "C59B3706"
    oks = 0
    den = 0
    errs = 0
    aliases = []
    t0 = time.time()
    for i in range(burst_n):
        try:
            session_id, nonce = rfid_client.get_nonce(UID)
            hmac_b = rfid_client.compute_hmac(UID, nonce)
            res = rfid_client.post_verify(UID, session_id, hmac_b)
            if res.get("result") == "OK":
                oks += 1
                if res.get("alias"):
                    aliases.append(res.get("alias"))
            else:
                den += 1
        except Exception as e:
            errs += 1
        time.sleep(sleep_between)
    dur = time.time() - t0
    notes = f"burst_n={burst_n}, sleep={sleep_between}s"
    return {
        "result": f"BURST_OK={oks}",
        "reason": f"denied={den}",
        "alias": ",".join(aliases[:5]) if aliases else "",
        "error": "" if errs == 0 else f"errors={errs}",
        "notes": notes,
        "duration_s": dur
    }

# Mapa de tests disponibles
TESTS = {
    "test_ok_single": test_ok_once,
    "test_denied_hmac": test_denied_hmac_once,
    "test_session_expired": test_session_expired_once,
    "test_unauthorized_uid": test_unauthorized_uid_once,
    "test_burst_load": test_burst_load_once,
}

CSV_FIELDS = ["run_index", "timestamp_iso", "duration_s", "result", "reason", "alias", "error", "notes"]

def run_and_log(test_name: str, func, run_index: int, csv_path: str, **kwargs):
    started_at = datetime.utcnow().isoformat()
    t0 = time.time()
    # Ejecuta la función de prueba (acepta kwargs como burst_n)
    try:
        out = func(**kwargs) if kwargs else func()
    except Exception as e:
        out = {"result": "", "reason": "", "alias": "", "error": str(e), "notes": "exception", "duration_s": 0.0}
    duration = out.get("duration_s", time.time() - t0)
    row = {
        "run_index": run_index,
        "timestamp_iso": started_at,
        "duration_s": f"{duration:.4f}",
        "result": out.get("result", ""),
        "reason": out.get("reason", ""),
        "alias": out.get("alias", ""),
        "error": out.get("error", ""),
        "notes": out.get("notes", ""),
    }
    write_header = not os.path.exists(csv_path)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)
    return row

def run_suite(max_runs: int, tests_to_run: list, burst_params: dict = None, sleep_between_runs: float = 0.0):
    summary = {}
    for tname in tests_to_run:
        func = TESTS.get(tname)
        if func is None:
            print(f"[WARN] Test desconocido: {tname}, se salta.")
            continue
        csv_file = os.path.join(RESULTS_DIR, f"{tname}.csv")
        print(f"\n=== Ejecutando test: {tname} -> {csv_file} (hasta {max_runs} runs) ===")
        summary[tname] = {"runs": 0, "last_row": None}
        for i in range(1, max_runs + 1):
            kwargs = {}
            if tname == "test_burst_load" and burst_params:
                kwargs = burst_params
            row = run_and_log(tname, func, i, csv_file, **kwargs)
            summary[tname]["runs"] = i
            summary[tname]["last_row"] = row
            # imprimir progreso cada 10 o si hay error
            if i % 10 == 0 or row["error"]:
                print(f"[{tname}] run {i}: result={row['result']} reason={row['reason']} error={row['error']}")
            if sleep_between_runs:
                time.sleep(sleep_between_runs)
        print(f"=== Fin test {tname}: total_runs={summary[tname]['runs']} ===")
    return summary

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run test suite in bulk and write CSVs per test.")
    parser.add_argument("--max", type=int, default=500, help="Max runs per test (default 500)")
    parser.add_argument("--tests", type=str, default=",".join(TESTS.keys()),
                        help=f"Comma-separated list of tests to run. Available: {','.join(TESTS.keys())}")
    parser.add_argument("--burst_n", type=int, default=20, help="burst_n for test_burst_load (default 20)")
    parser.add_argument("--burst_sleep", type=float, default=0.02, help="sleep_between for burst (default 0.02s)")
    parser.add_argument("--sleep_between_runs", type=float, default=0.0, help="sleep between each run (default 0.0s)")
    args = parser.parse_args()

    tests_list = [t.strip() for t in args.tests.split(",") if t.strip()]

    burst_params = {"burst_n": args.burst_n, "sleep_between": args.burst_sleep}
    print("Iniciando ejecución bulk:", tests_list)
    print("Resultados en:", RESULTS_DIR)
    summary = run_suite(args.max, tests_list, burst_params=burst_params, sleep_between_runs=args.sleep_between_runs)

    print("\n=== Resumen final ===")
    for k,v in summary.items():
        print(f"{k}: runs={v['runs']} last_result={v['last_row']['result'] if v['last_row'] else 'N/A'} last_error={v['last_row']['error'] if v['last_row'] else ''}")
    print("CSV files generated.")
