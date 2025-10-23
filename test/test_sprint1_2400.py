# test_sprint1_2400.py
import requests, binascii, hmac, hashlib, time

BASE_URL = "http://localhost:8000"   # cambiar según tu servidor
UID = "C59B3706"                     # UID autorizado en tu DB
SECRET_KEY = b"MiEjemplo"            # asegúrate que coincide con main.py

MAX_ATTEMPTS = 2400
SLEEP_BETWEEN = 0.05  # tiempo entre intentos (segundos). Ajustar si es necesario.

def get_nonce(uid):
    r = requests.get(f"{BASE_URL}/api/nonce", params={"uid": uid}, timeout=6)
    r.raise_for_status()
    data = r.json()
    return data["sessionId"], binascii.unhexlify(data["nonce"])

def post_verify(uid, session_id, hmac_bytes):
    body = {"uid": uid, "sessionId": session_id, "hmac": binascii.hexlify(hmac_bytes).decode()}
    r = requests.post(f"{BASE_URL}/api/verify", json=body, timeout=8)
    return r.json()

def make_hmac(uid_hex, nonce_bytes):
    uid_bytes = binascii.unhexlify(uid_hex)
    return hmac.new(SECRET_KEY, uid_bytes + nonce_bytes, hashlib.sha256).digest()

if __name__ == "__main__":
    success = 0
    fail = 0
    for i in range(1, MAX_ATTEMPTS + 1):
        try:
            sid, nonce = get_nonce(UID)
            hm = make_hmac(UID, nonce)
            resp = post_verify(UID, sid, hm)
            print(f"[{i:04d}] -> {resp}")
            if resp.get("result") == "OK":
                success += 1
            else:
                fail += 1
        except requests.exceptions.HTTPError as he:
            print(f"[{i:04d}] HTTP ERROR: {he}")
            fail += 1
        except Exception as e:
            print(f"[{i:04d}] ERROR: {e}")
            fail += 1
        time.sleep(SLEEP_BETWEEN)

    print(f"\nFinal: {success} OK, {fail} NO-OK de {MAX_ATTEMPTS} intentos.")
