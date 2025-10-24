from rfid_client import get_nonce, compute_hmac, post_verify

# UID cualquiera que NO esté en AuthorizedTags (Activa=1)
UID = "DEADBEEF"

def main():
    session_id, nonce = get_nonce(UID)
    hmac_bytes = compute_hmac(UID, nonce)
    res = post_verify(UID, session_id, hmac_bytes)
    print("Resultado esperado DENIED/NO_AUTORIZADO:", res)

if __name__ == "__main__":
    main()
