# test/test_sprint3_uid_correct_alias_random.py
"""
Prueba: intenta pedir nonce usando alias aleatorios y verificar con el UID real.
- Genera un CSV con resultados por intento.
- Al finalizar calcula estadísticas: unicidad de alias, latencias, rendimiento, etc.
"""

import requests, binascii, hmac, hashlib, time, random, csv, os, statistics
from datetime import datetime

BASE_URL = "http://localhost:8000"
UID = "C59B3706"                 # UID registrado (el correcto que quieres usar)
SECRET_KEY = b"MiEjemplo"

# Alias autorizado conocido (fallback) - úsalo solo si /api/nonce rechaza el alias aleatorio
AUTHORIZED_ALIAS_FOR_NONCE = "E9989D1C88EB2CA3"

MAX_ATTEMPTS = 500
SLEEP_BETWEEN = 0.05
VERIFY_NO_ALIAS_ENDPOINT = "/api/verify_no_alias"  # endpoint "sin rotación"

HEX_CHARS = "0123456789ABCDEF"

# Output files
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)
CSV_PATH = os.path.join(RESULTS_DIR, "test_sprint3_uid_correct_alias_random.csv")
SUMMARY_CSV_PATH = os.path.join(RESULTS_DIR, "test_sprint3_uid_correct_alias_random_summary.csv")

# Helper functions
def random_alias_hex(length_bytes=8):
    """Genera un alias aleatorio de `length_bytes` bytes (hex string)."""
    return ''.join(random.choice(HEX_CHARS) for _ in range(length_bytes*2))

def get_nonce_for_alias(alias):
    """Pide nonce/SessionId para el alias indicado. Devuelve (sessionId, nonce_bytes)."""
    r = requests.get(f"{BASE_URL}/api/nonce", params={"uid": alias}, timeout=6)
    r.raise_for_status()
    data = r.json()
    return data["sessionId"], binascii.unhexlify(data["nonce"])

def post_verify_no_alias(uid, session_id, hmac_bytes):
    """Llama al endpoint verify_no_alias (verifica HMAC/UID)."""
    body = {"uid": uid, "sessionId": session_id, "hmac": binascii.hexlify(hmac_bytes).decode()}
    r = requests.post(f"{BASE_URL}{VERIFY_NO_ALIAS_ENDPOINT}", json=body, timeout=8)
    r.raise_for_status()
    return r.json()

def compute_hmac(uid_hex: str, nonce_bytes: bytes) -> bytes:
    return hmac.new(SECRET_KEY, binascii.unhexlify(uid_hex), hashlib.sha256, ).digest() if False else hmac.new(SECRET_KEY, binascii.unhexlify(uid_hex) + nonce_bytes, hashlib.sha256).digest()

# CSV header
CSV_FIELDS = [
    "run",
    "timestamp_iso",
    "alias_used",
    "alias_type",   # "random" o "fallback"
    "uid",
    "result",       # 'OK' / 'DENIED' / '' if error
    "reason",       # si viene en la respuesta
    "response_raw", # stringified response json (truncated)
    "duration_s",
    "error"         # texto de excepción si ocurrió
]

def write_csv_row(path, row, write_header=False):
    mode = "a"
    if write_header or (not os.path.exists(path)):
        mode = "w"
    with open(path, mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if mode == "w":
            writer.writeheader()
        writer.writerow(row)

def summarize_and_save(stats, path):
    # stats: dict con métricas ya calculadas
    # guardamos como CSV con dos columnas: metric, value
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value"])
        for k,v in stats.items():
            writer.writerow([k, v])

def main():
    # Preparar CSV (sobrescribe si existe)
    if os.path.exists(CSV_PATH):
        os.remove(CSV_PATH)
    write_csv_row(CSV_PATH, {k:"" for k in CSV_FIELDS}, write_header=True)  # escribe header

    # Recolección para stats
    durations = []
    results = {"OK":0, "DENIED":0, "ERROR":0}
    reasons_count = {}
    alias_list = []
    alias_type_counts = {"random":0, "fallback":0}
    response_samples = []

    for i in range(1, MAX_ATTEMPTS+1):
        timestamp_iso = datetime.utcnow().isoformat()
        alias_try = random_alias_hex(8)
        alias_used = alias_try
        alias_type = "random"
        start = time.time()
        row = {k:"" for k in CSV_FIELDS}
        row["run"] = i
        row["timestamp_iso"] = timestamp_iso
        row["alias_used"] = alias_used
        row["alias_type"] = alias_type
        row["uid"] = UID
        row["result"] = ""
        row["reason"] = ""
        row["response_raw"] = ""
        row["duration_s"] = ""
        row["error"] = ""

        try:
            # 1) intentar nonce con alias aleatorio
            try:
                sid, nonce = get_nonce_for_alias(alias_try)
                alias_used = alias_try
                alias_type = "random"
                alias_type_counts["random"] += 1
            except requests.exceptions.HTTPError:
                # fallback: usar alias autorizado conocido
                sid, nonce = get_nonce_for_alias(AUTHORIZED_ALIAS_FOR_NONCE)
                alias_used = AUTHORIZED_ALIAS_FOR_NONCE
                alias_type = "fallback"
                alias_type_counts["fallback"] += 1

            # 2) calcular HMAC con UID correcto + nonce
            hm = compute_hmac(UID, nonce)

            # 3) enviar verify_no_alias
            resp = post_verify_no_alias(UID, sid, hm)
            duration = time.time() - start

            # Registrar resultados
            row["result"] = resp.get("result", "")
            row["reason"] = resp.get("reason", "")
            # stringify response but truncate to avoid huge CSV cells
            resp_str = str(resp)
            row["response_raw"] = resp_str if len(resp_str) < 800 else resp_str[:800] + "..."
            row["duration_s"] = f"{duration:.4f}"

            # update aggregates
            durations.append(duration)
            response_samples.append(resp_str)
            alias_list.append(alias_used)
            results_key = row["result"] if row["result"] else "ERROR"
            if results_key not in results:
                results[results_key] = 0
            results[results_key] += 1
            if row["reason"]:
                reasons_count[row["reason"]] = reasons_count.get(row["reason"], 0) + 1

            # print simple progress
            print(f"[{i:04d}] alias_used={alias_used} ({alias_type}) UID={UID} -> {row['result']} {row['reason']} dur={row['duration_s']}s")

        except requests.exceptions.HTTPError as he:
            duration = time.time() - start
            row["error"] = f"HTTPError: {he}"
            row["duration_s"] = f"{duration:.4f}"
            results["ERROR"] += 1
            print(f"[{i:04d}] HTTP ERROR: {he}")
        except Exception as e:
            duration = time.time() - start
            row["error"] = f"Exception: {e}"
            row["duration_s"] = f"{duration:.4f}"
            results["ERROR"] += 1
            print(f"[{i:04d}] ERROR: {e}")

        # Finalizar row con alias info (en caso se haya cambiado)
        row["alias_used"] = alias_used
        row["alias_type"] = alias_type

        # Escribir fila al CSV incremental (si prefieres escribir solo al final, cambia esto)
        write_csv_row(CSV_PATH, row, write_header=False)

        # Pause
        time.sleep(SLEEP_BETWEEN)

    # --- stats post-run ---
    total_runs = sum(results.values())
    ok_count = results.get("OK", 0)
    denied_count = results.get("DENIED", 0)
    error_count = results.get("ERROR", 0)
    pct_ok = (ok_count / total_runs * 100) if total_runs else 0.0

    # latency stats
    latency_stats = {}
    if durations:
        latency_stats["lat_mean_s"] = statistics.mean(durations)
        latency_stats["lat_median_s"] = statistics.median(durations)
        latency_stats["lat_min_s"] = min(durations)
        latency_stats["lat_max_s"] = max(durations)
        latency_stats["lat_std_s"] = statistics.pstdev(durations) if len(durations) > 1 else 0.0
    else:
        latency_stats.update({"lat_mean_s":0,"lat_median_s":0,"lat_min_s":0,"lat_max_s":0,"lat_std_s":0})

    # alias uniqueness
    unique_aliases = set(alias_list)
    alias_counts = {}
    for a in alias_list:
        alias_counts[a] = alias_counts.get(a, 0) + 1
    collisions = {a:c for a,c in alias_counts.items() if c > 1}
    unique_count = len(unique_aliases)
    pct_alias_unique = (unique_count / total_runs * 100) if total_runs else 0.0

    # top aliases
    top_aliases = sorted(alias_counts.items(), key=lambda x: x[1], reverse=True)[:20]

    # throughput approx: OK per total time
    total_time = sum(durations) if durations else 0.0
    throughput_ok_per_s = (ok_count / total_time) if total_time > 0 else 0.0

    # Build stats dict
    stats = {
        "total_runs": total_runs,
        "ok_count": ok_count,
        "denied_count": denied_count,
        "error_count": error_count,
        "pct_ok": f"{pct_ok:.2f}%",
        "alias_total_used": len(alias_list),
        "alias_unique_count": unique_count,
        "pct_alias_unique": f"{pct_alias_unique:.2f}%",
        "fallback_alias_used_count": alias_type_counts.get("fallback", 0),
        "random_alias_used_count": alias_type_counts.get("random", 0),
        "total_time_s_sum_of_requests": f"{total_time:.4f}",
        "throughput_ok_per_s": f"{throughput_ok_per_s:.4f}"
    }
    # add latency stats
    stats.update(latency_stats)
    # add top aliases sample (string)
    stats["top_aliases_top20"] = "; ".join([f"{a}:{c}" for a,c in top_aliases])
    stats["alias_collisions_count"] = len(collisions)
    stats["alias_collisions_sample"] = "; ".join([f"{a}:{c}" for a,c in list(collisions.items())[:10]])
    stats["reasons_count"] = "; ".join([f"{k}:{v}" for k,v in reasons_count.items()])

    # print summary
    print("\n=== RESUMEN ===")
    for k,v in stats.items():
        print(f"{k}: {v}")

    # guardar resumen CSV
    summarize_and_save(stats, SUMMARY_CSV_PATH)
    print(f"Resumen guardado en: {SUMMARY_CSV_PATH}")
    print(f"Resultados detallados en: {CSV_PATH}")

if __name__ == "__main__":
    main()
