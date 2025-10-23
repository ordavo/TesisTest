# test_sprint2_2400_alias_random_uid.py
import requests, binascii, hmac, hashlib, time, random

BASE_URL = "http://localhost:8000"
AUTHORIZED_UID_FOR_NONCE = "E9989D1C88EB2CA3"  # alias válido registrado
SECRET_KEY = b"MiEjemplo"

MAX_ATTEMPTS = 500   
SLEEP_BETWEEN = 0.05

def random_uid():
    """Genera un UID aleatorio de 8 bytes (16 caracteres hex) distinto del autorizado"""
    return ''.join(random.choice('0123456789ABCDEF') for _ in range(8))

def get_nonce_for_any(uid_hint):
    """Solicita nonce para un UID válido"""
    r = requests.get(f"{BASE_URL}/api/nonce", params={"uid": uid_hint}, timeout=6)
    r.raise_for_status()
    data = r.json()
    return data["sessionId"], binascii.unhexlify(data["nonce"])

def post_verify(uid, session_id, hmac_bytes):
    """Envía verificación usando UID arbitrario"""
    body = {"uid": uid, "sessionId": session_id, "hmac": binascii.hexlify(hmac_bytes).decode()}
    r = requests.post(f"{BASE_URL}/api/verify", json=body, timeout=8)
    return r.json()

if __name__ == "__main__":
    success = 0
    fail = 0
    for i in range(1, MAX_ATTEMPTS + 1):
        try:
            sid, nonce = get_nonce_for_any(AUTHORIZED_UID_FOR_NONCE)
            
            # Genera un UID aleatorio diferente del real
            wrong_uid = random_uid()
            
            # Calcula el HMAC con el UID aleatorio + nonce
            hm = hmac.new(SECRET_KEY, binascii.unhexlify(wrong_uid) + nonce, hashlib.sha256).digest()
            
            resp = post_verify(wrong_uid, sid, hm)
            print(f"[{i:04d}] UID={wrong_uid} -> {resp}")
            
            # En teoría, todos deben ser NO_AUTORIZADO
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
