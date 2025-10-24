from rfid_client import get_nonce, compute_hmac, post_verify, get_logs

UID = "C59B3706"

def main():
    session_id, nonce = get_nonce(UID)
    hmac_bytes = compute_hmac(UID, nonce)
    res = post_verify(UID, session_id, hmac_bytes)
    print("Resultado verify:", res)

    logs = get_logs(UID, limit=5)
    print("Últimos logs de", UID, "=>", logs)

if __name__ == "__main__":
    main()
