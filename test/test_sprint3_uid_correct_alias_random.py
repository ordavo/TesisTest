# test_sprint3_uid_correct_alias_random.py
import requests, binascii, hmac, hashlib, time, random

BASE_URL = "http://localhost:8000"
UID = "C59B3706"                 # UID registrado (el correcto que quieres usar)
SECRET_KEY = b"MiEjemplo"

# Alias autorizado conocido (fallback) - úsalo solo si /api/nonce rechaza el alias aleatorio
AUTHORIZED_ALIAS_FOR_NONCE = "E9989D1C88EB2CA3"

MAX_ATTEMPTS = 500 
SLEEP_BETWEEN = 0.05
VERIFY_NO_ALIAS_ENDPOINT = "/api/verify_no_alias"  # endpoint "sin rotación"

HEX_CHARS = "0123456789ABCDEF"

def random_alias_hex(length_bytes=8):
    """Genera un alias aleatorio de `length_bytes` bytes (hex string de 2*length_bytes chars)."""
    return ''.join(random.choice(HEX_CHARS) for _ in range(length_bytes*2))

def get_nonce_for_alias(alias):
    """Pide nonce/SessionId para el alias indicado. Devuelve (sessionId, nonce_bytes)."""
    r = requests.get(f"{BASE_URL}/api/nonce", params={"uid": alias}, timeout=6)
    r.raise_for_status()
    data = r.json()
    return data["sessionId"], binascii.unhexlify(data["nonce"])

def post_verify_no_alias(uid, session_id, hmac_bytes):
    """Llama al endpoint verify_no_alias (verifica HMAC/UID pero no altera alias)."""
    body = {"uid": uid, "sessionId": session_id, "hmac": binascii.hexlify(hmac_bytes).decode()}
    r = requests.post(f"{BASE_URL}{VERIFY_NO_ALIAS_ENDPOINT}", json=body, timeout=8)
    r.raise_for_status()
    return r.json()

if __name__ == "__main__":
    success = 0
    fail = 0
    for i in range(1, MAX_ATTEMPTS + 1):
        try:
            # 1) intentamos crear sesión usando un alias aleatorio (distinto del registrado)
            alias_try = random_alias_hex(8)  # 8 bytes -> 16 hex pairs (Ej: A1B2C3...)
            try:
                sid, nonce = get_nonce_for_alias(alias_try)
                used_alias = alias_try
            except requests.exceptions.HTTPError as he:
                # Si el servidor rechaza el alias aleatorio, hacemos fallback usando alias autorizado
                # (esto evita que el script se detenga; quita el fallback si quieres forzar el rechazo)
                sid, nonce = get_nonce_for_alias(AUTHORIZED_ALIAS_FOR_NONCE)
                used_alias = AUTHORIZED_ALIAS_FOR_NONCE

            # 2) calculamos HMAC con el UID correcto + nonce
            hm = hmac.new(SECRET_KEY, binascii.unhexlify(UID) + nonce, hashlib.sha256).digest()

            # 3) enviamos la verificación (sin rotar alias)
            resp = post_verify_no_alias(UID, sid, hm)
            print(f"[{i:04d}] alias_used={used_alias} UID={UID} -> {resp}")

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
