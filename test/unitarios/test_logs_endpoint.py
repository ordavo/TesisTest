# tests/test_logs_endpoint.py
def test_logs_list_format(client):
    r = client.get("/api/logs?limit=5")
    assert r.status_code == 200
    j = r.json()
    assert "count" in j and "items" in j
    if j["items"]:
        it = j["items"][0]
        for key in ("id", "uid", "resultado", "details", "fecha"):
            assert key in it
