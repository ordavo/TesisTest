import time
from rfid_client import get_nonce, compute_hmac, post_verify

UID = "C59B3706"
N = 20
SLEEP_BETWEEN = 0.05  # 50 ms

def main():
    oks = 0
    for i in range(N):
        try:
            session_id, nonce = get_nonce(UID)
            hmac_bytes = compute_hmac(UID, nonce)
            res = post_verify(UID, session_id, hmac_bytes)
            if res.get("result") == "OK":
                oks += 1
            print(f"[{i+1}/{N}] {res}")
            time.sleep(SLEEP_BETWEEN)
        except Exception as e:
            print(f"[{i+1}/{N}] ERROR:", e)
    print(f"Total OK: {oks}/{N}")

if __name__ == "__main__":
    main()
