import requests, binascii, hmac, hashlib, time

BASE_URL = "http://localhost:8000"
SECRET_KEY = b"MiEjemplo"

def hex_to_bytes(s: str) -> bytes:
    s = s.strip().replace(" ", "")
    if s.lower().startswith("0x"):
        s = s[2:]
    return binascii.unhexlify(s)

def get_nonce(uid: str):
    """Devuelve (sessionId, nonce_bytes)"""
    r = requests.get(f"{BASE_URL}/api/nonce", params={"uid": uid}, timeout=6)
    r.raise_for_status()
    data = r.json()
    return data["sessionId"], binascii.unhexlify(data["nonce"])

def compute_hmac(uid_hex: str, nonce_bytes: bytes) -> bytes:
    """HMAC-SHA256(SECRET_KEY, uid_bytes || nonce)"""
    uid_bytes = hex_to_bytes(uid_hex)
    return hmac.new(SECRET_KEY, uid_bytes + nonce_bytes, hashlib.sha256).digest()

def post_verify(uid: str, session_id: str, hmac_bytes: bytes):
    body = {
        "uid": uid,
        "sessionId": session_id,
        "hmac": binascii.hexlify(hmac_bytes).decode()
    }
    r = requests.post(f"{BASE_URL}/api/verify", json=body, timeout=6)
    r.raise_for_status()
    return r.json()

def get_logs(uid: str | None = None, limit: int = 20):
    params = {"limit": limit}
    if uid:
        params["uid"] = uid
    r = requests.get(f"{BASE_URL}/api/logs", params=params, timeout=6)
    r.raise_for_status()
    return r.json()
