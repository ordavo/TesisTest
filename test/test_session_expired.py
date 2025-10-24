import time
from rfid_client import get_nonce, compute_hmac, post_verify

UID = "C59B3706"
SLEEP_AFTER_NONCE = 4  # tu NONCE_TTL_SECONDS=3 → dormir 4s

def main():
    session_id, nonce = get_nonce(UID)
    print("Obtuve nonce, duermo", SLEEP_AFTER_NONCE, "s para expirar...")
    time.sleep(SLEEP_AFTER_NONCE)
    hmac_bytes = compute_hmac(UID, nonce)
    res = post_verify(UID, session_id, hmac_bytes)
    print("Resultado esperado DENIED/SESSION_EXPIRADA:", res)

if __name__ == "__main__":
    main()
