# test/test_sprint3_uid_correct_rotate_stats.py
# Ejecuta /api/nonce -> /api/verify con el UID correcto MAX_ATTEMPTS veces.
# Genera:
#   - results/test_sprint3_uid_correct_rotate_stats.csv (1 fila por intento)
#   - results/test_sprint3_uid_correct_rotate_stats_summary.csv (estadísticas)

import requests, binascii, hmac, hashlib, time, csv, os, statistics
from datetime import datetime

BASE_URL = "http://localhost:8000"
UID = "C59B3706"          # UID registrado
SECRET_KEY = b"MiEjemplo"

MAX_ATTEMPTS = 500
SLEEP_BETWEEN = 0.05

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)
CSV_PATH = os.path.join(RESULTS_DIR, "test_sprint3_uid_correct_rotate_stats.csv")
SUMMARY_CSV_PATH = os.path.join(RESULTS_DIR, "test_sprint3_uid_correct_rotate_stats_summary.csv")

def get_nonce(uid_hex: str):
    r = requests.get(f"{BASE_URL}/api/nonce", params={"uid": uid_hex}, timeout=6)
    r.raise_for_status()
    d = r.json()
    return d["sessionId"], binascii.unhexlify(d["nonce"])

def compute_hmac(uid_hex: str, nonce_bytes: bytes) -> bytes:
    uid_bytes = binascii.unhexlify(uid_hex)
    return hmac.new(SECRET_KEY, uid_bytes + nonce_bytes, hashlib.sha256).digest()

def post_verify(uid_hex: str, session_id: str, hmac_bytes: bytes):
    body = {"uid": uid_hex, "sessionId": session_id, "hmac": binascii.hexlify(hmac_bytes).decode()}
    r = requests.post(f"{BASE_URL}/api/verify", json=body, timeout=8)
    r.raise_for_status()
    return r.json()

FIELDS = ["run","timestamp_iso","uid","result","reason","alias","duration_s","error"]

def write_header(path): 
    with open(path, "w", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=FIELDS).writeheader()

def append_row(path, row):
    with open(path, "a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=FIELDS).writerow(row)

def save_summary(stats: dict, path: str):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["metric","value"])
        for k,v in stats.items(): w.writerow([k, v])

def main():
    if os.path.exists(CSV_PATH): os.remove(CSV_PATH)
    write_header(CSV_PATH)

    durations, aliases = [], []
    results = {"OK":0, "DENIED":0, "ERROR":0}
    reasons = {}

    for i in range(1, MAX_ATTEMPTS+1):
        ts = datetime.utcnow().isoformat()
        row = {"run": i, "timestamp_iso": ts, "uid": UID,
               "result":"", "reason":"", "alias":"", "duration_s":"", "error":""}
        t0 = time.time()
        try:
            sid, nonce = get_nonce(UID)
            hm = compute_hmac(UID, nonce)
            resp = post_verify(UID, sid, hm)
            dur = time.time() - t0

            row["result"] = resp.get("result","")
            row["reason"] = resp.get("reason","")
            row["alias"]  = resp.get("alias","")   # alias nuevo tras rotación
            row["duration_s"] = f"{dur:.4f}"

            durations.append(dur)
            if row["alias"]: aliases.append(row["alias"])
            key = row["result"] if row["result"] else "ERROR"
            results[key] = results.get(key,0) + 1
            if row["reason"]: reasons[row["reason"]] = reasons.get(row["reason"],0) + 1

            print(f"[{i:04d}] {row['result']} {row['reason']} alias={row['alias']} dur={row['duration_s']}s")

        except requests.exceptions.HTTPError as he:
            dur = time.time() - t0
            row["error"] = f"HTTPError: {he}"
            row["duration_s"] = f"{dur:.4f}"
            results["ERROR"] += 1
            print(f"[{i:04d}] HTTP ERROR: {he}")
        except Exception as e:
            dur = time.time() - t0
            row["error"] = f"Exception: {e}"
            row["duration_s"] = f"{dur:.4f}"
            results["ERROR"] += 1
            print(f"[{i:04d}] ERROR: {e}")

        append_row(CSV_PATH, row)
        time.sleep(SLEEP_BETWEEN)

    total = sum(results.values())
    ok, denied, err = results.get("OK",0), results.get("DENIED",0), results.get("ERROR",0)
    pct_ok = (ok/total*100) if total else 0.0

    if durations:
        lat_mean = statistics.mean(durations)
        lat_med  = statistics.median(durations)
        lat_min, lat_max = min(durations), max(durations)
        lat_std  = statistics.pstdev(durations) if len(durations)>1 else 0.0
        total_time = sum(durations)
        throughput = ok/total_time if total_time>0 else 0.0
    else:
        lat_mean = lat_med = lat_min = lat_max = lat_std = total_time = throughput = 0.0

    alias_counts = {}
    for a in aliases: alias_counts[a] = alias_counts.get(a,0) + 1
    unique_count = sum(1 for c in alias_counts.values() if c==1)
    total_alias_seen = len(aliases)
    pct_alias_unique = (unique_count/total_alias_seen*100) if total_alias_seen else 0.0
    collisions = {a:c for a,c in alias_counts.items() if c>1}
    top_aliases = sorted(alias_counts.items(), key=lambda x:x[1], reverse=True)[:20]

    stats = {
        "total_runs": total,
        "ok": ok, "denied": denied, "error": err,
        "pct_ok": f"{pct_ok:.2f}%",
        "dur_mean_s": f"{lat_mean:.4f}", "dur_median_s": f"{lat_med:.4f}",
        "dur_min_s": f"{lat_min:.4f}",  "dur_max_s": f"{lat_max:.4f}",
        "dur_std_s": f"{lat_std:.4f}",
        "total_time_s": f"{total_time:.4f}",
        "throughput_ok_per_s": f"{throughput:.4f}",
        "aliases_total_seen": total_alias_seen,
        "aliases_unique_count": unique_count,
        "aliases_pct_unique": f"{pct_alias_unique:.2f}%",
        "alias_collisions_count": len(collisions),
        "alias_collisions_sample": "; ".join([f"{a}:{c}" for a,c in list(collisions.items())[:10]]),
        "reasons_breakdown": "; ".join([f"{k}:{v}" for k,v in reasons.items()]),
        "top_aliases_top20": "; ".join([f"{a}:{c}" for a,c in top_aliases]),
    }

    print("\n=== RESUMEN ===")
    for k,v in stats.items(): print(f"{k}: {v}")
    save_summary(stats, SUMMARY_CSV_PATH)
    print(f"\nCSV intentos: {CSV_PATH}")
    print(f"CSV resumen:  {SUMMARY_CSV_PATH}")

if __name__ == "__main__":
    main()
