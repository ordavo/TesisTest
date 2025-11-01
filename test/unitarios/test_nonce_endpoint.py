# tests/test_nonce_endpoint.py
import binascii

def test_nonce_ok(client):
    r = client.get("/api/nonce", params={"uid": "C59B3706"})
    assert r.status_code == 200
    data = r.json()
    assert "sessionId" in data and "nonce" in data
    # nonce viene en hex
    binascii.unhexlify(data["nonce"])
