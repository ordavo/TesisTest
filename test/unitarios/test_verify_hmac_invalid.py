# test/unitarios/test_verify_ok_and_rotate_alias.py
import os, binascii, hmac, hashlib
from main import SECRET_KEY

def make_hmac(uid_hex, nonce_bytes):
    uid_b = binascii.unhexlify(uid_hex)
    # intenta ambos órdenes
    cand = [
        uid_b + nonce_bytes,
        nonce_bytes + uid_b,
    ]
    for payload in cand:
        yield hmac.new(SECRET_KEY, payload, hashlib.sha256).hexdigest()

def test_verify_ok_and_alias_rotation(client, monkeypatch):
    uid = "C59B3706"
    r = client.get("/api/nonce", params={"uid": uid})
    data = r.json()
    sid = data["sessionId"]
    nonce = binascii.unhexlify(data["nonce"])

    monkeypatch.setattr("main.gen_alias_hex", lambda n=8: "DEADBEEFCAFEBABE")

    # intenta con ambos HMAC hasta obtener OK
    for hm_hex in make_hmac(uid, nonce):
        r2 = client.post("/api/verify", json={"uid": uid, "sessionId": sid, "hmac": hm_hex})
        j = r2.json()
        if j.get("result") == "OK":
            assert j["alias"] == "DEADBEEFCAFEBABE"
            break
    else:
        raise AssertionError(f"No se obtuvo OK; respuesta final: {j}")
