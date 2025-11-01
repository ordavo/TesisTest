# tests/test_verify_ok_and_rotate_alias.py
import os, binascii, hmac, hashlib
from main import SECRET_KEY

def test_verify_ok_and_alias_rotation(client, monkeypatch):
    # 1) nonce
    uid = "C59B3706"
    r = client.get("/api/nonce", params={"uid": uid})
    data = r.json()
    sid = data["sessionId"]
    nonce = binascii.unhexlify(data["nonce"])

    # 2) HMAC correcto
    hm = hmac.new(SECRET_KEY, binascii.unhexlify(uid) + nonce, hashlib.sha256).digest()
    hm_hex = binascii.hexlify(hm).decode()

    # 3) Forzamos un alias determinista para validar respuesta
    monkeypatch.setattr("main.gen_alias_hex", lambda n=8: "DEADBEEFCAFEBABE")

    r2 = client.post("/api/verify", json={"uid": uid, "sessionId": sid, "hmac": hm_hex})
    j = r2.json()
    assert j["result"] == "OK"
    assert j["alias"] == "DEADBEEFCAFEBABE"
